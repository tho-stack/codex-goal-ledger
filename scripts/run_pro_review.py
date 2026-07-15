#!/usr/bin/env python3
"""Prepare, preserve, reconcile, and validate native Goal Ledger GPT Pro reviews."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
import platform
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Mapping
import zipfile

from generate_closeout_prompts import parse_closeout_options
from ledger_common import (
    Document,
    LedgerError,
    get_section,
    load_document,
    normalize_state,
    parse_table,
    project_root_for,
    strip_markdown,
)


PRO_REVIEW_OPTION = "GPT Pro review"
PRO_REVIEW_ROOT = Path("evidence/pro-review")
VALID_STAGES = ("plan", "implementation")
VALID_STAGE_SELECTIONS = ("plan", "implementation", "both")
VALID_DELIVERIES = (
    "auto-ui",
    "safari-assisted",
    "chrome-assisted",
    "chatgpt-desktop",
    "owner-handoff",
)
ASSISTED_SURFACES = ("safari-assisted", "chrome-assisted", "chatgpt-desktop")
SUBMISSION_TRANSPORTS = ASSISTED_SURFACES + ("owner-handoff",)
TRANSPORT_RESULTS = (
    "unavailable",
    "not-authenticated",
    "pro-unavailable",
    "ready",
    "failed",
)
VALID_GATES = ("required", "advisory")
VALID_CLASSIFICATIONS = ("FIX", "DEFER", "DISMISS", "QUESTION")
MAX_PRO_ROUNDS = 3
MAX_CONTEXT_FILE_BYTES = 8 * 1024 * 1024
MAX_PACKET_BYTES = 32 * 1024 * 1024
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FORBIDDEN_PARTS = frozenset(
    {
        ".git",
        ".ssh",
        ".aws",
        ".gnupg",
        "node_modules",
        "credentials",
        "secrets",
    }
)
FORBIDDEN_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        "id_rsa",
        "id_ed25519",
        "credentials.json",
        "service-account.json",
    }
)


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_immutable(path: Path, data: bytes) -> bool:
    """Write a custody artifact once, or reuse it only when the bytes are identical."""
    if path.exists():
        if not path.is_file():
            raise LedgerError(f"custody artifact is not a regular file: {path}")
        if path.read_bytes() != data:
            raise LedgerError(
                f"immutable Pro review artifact differs: {path}; preserve this round and "
                "prepare a new round"
            )
        return False
    _atomic_write(path, data)
    return True


def _single_line(name: str, value: str) -> str:
    value = value.strip()
    if not value:
        raise LedgerError(f"{name} must not be empty")
    if "\n" in value or "\r" in value:
        raise LedgerError(f"{name} must be a single line")
    return value


def pro_review_rounds(goal: Document) -> int:
    raw = goal.metadata.get("pro_review_rounds", "1").strip()
    try:
        rounds = int(raw)
    except ValueError as exc:
        raise LedgerError("pro_review_rounds must be an integer from 1 to 3") from exc
    if not 1 <= rounds <= MAX_PRO_ROUNDS or str(rounds) != raw:
        raise LedgerError("pro_review_rounds must be an integer from 1 to 3")
    return rounds


def pro_review_stage(goal: Document) -> str:
    stage = goal.metadata.get("pro_review_stage", "plan").strip()
    if stage not in VALID_STAGE_SELECTIONS:
        raise LedgerError("pro_review_stage must be plan, implementation, or both")
    return stage


def pro_review_delivery(goal: Document) -> str:
    delivery = goal.metadata.get("pro_review_delivery", "safari-assisted").strip()
    if delivery not in VALID_DELIVERIES:
        raise LedgerError(
            "pro_review_delivery must be auto-ui, safari-assisted, chrome-assisted, "
            "chatgpt-desktop, or owner-handoff"
        )
    return delivery


def delivery_candidates(delivery: str, host_platform: str | None = None) -> tuple[str, ...]:
    """Return the platform-aware ordered UI route for one configured delivery."""
    if delivery != "auto-ui":
        return (delivery,)
    system = (host_platform or platform.system()).strip().casefold()
    if system in {"darwin", "mac", "macos"}:
        return ("safari-assisted", "chrome-assisted", "chatgpt-desktop", "owner-handoff")
    return ("chrome-assisted", "chatgpt-desktop", "owner-handoff")


def _delivery_plan(goal: Document) -> dict[str, Any]:
    configured = pro_review_delivery(goal)
    return {
        "schema_version": 1,
        "configured_delivery": configured,
        "host_platform": platform.system() or "unknown",
        "candidates": list(delivery_candidates(configured)),
        "readiness_contract": [
            "Computer Use can inspect the surface.",
            "ChatGPT is authenticated.",
            "GPT Pro or Pro Extended is visibly selectable.",
            "File upload and text input are available.",
        ],
        "attempt_results": list(TRANSPORT_RESULTS),
    }


def _manual_handoff_markdown(
    goal_dir: Path,
    *,
    stage: str,
    round_number: int,
    packet_sha256: str,
) -> bytes:
    project_root = project_root_for(goal_dir)
    round_dir = _review_dir(goal_dir, stage, round_number)
    request = (round_dir / "request.md").relative_to(project_root).as_posix()
    packet = (round_dir / "context-packet.zip").relative_to(project_root).as_posix()
    return (
        "# Manual GPT Pro handoff\n\n"
        "No supported assisted ChatGPT surface was ready. Continue manually with the exact "
        "prepared packet; do not rebuild or substitute files.\n\n"
        f"- Request: `{request}`\n"
        f"- ZIP: `{packet}`\n"
        f"- ZIP SHA-256: `{packet_sha256}`\n"
        "- Required model: a visibly selected GPT Pro or Pro Extended mode\n\n"
        "## Submit\n\n"
        "1. Open an authenticated ChatGPT client or browser.\n"
        "2. Select GPT Pro or Pro Extended and verify the model label is visible.\n"
        f"3. Upload `{packet}` and paste only `{request}`.\n"
        "4. Submit once and keep that conversation open until the full response is captured.\n"
        "5. Record the observed submission with:\n\n"
        "```bash\n"
        f"python3 scripts/run_pro_review.py record-submission {goal_dir.relative_to(project_root).as_posix()} \\\n"
        f"  --stage {stage} --round {round_number} \\\n"
        "  --model-visible \"Pro Extended\" --transport owner-handoff \\\n"
        "  --thread \"<visible conversation title or URL>\"\n"
        "```\n"
    ).encode("utf-8")


def pro_review_gate(goal: Document) -> str:
    gate = goal.metadata.get("pro_review_gate", "required").strip()
    if gate not in VALID_GATES:
        raise LedgerError("pro_review_gate must be required or advisory")
    return gate


def configured_stages(goal: Document) -> tuple[str, ...]:
    selected = pro_review_stage(goal)
    return VALID_STAGES if selected == "both" else (selected,)


def configured_reviews(goal: Document) -> tuple[tuple[str, int], ...]:
    return tuple(
        (stage, round_number)
        for stage in configured_stages(goal)
        for round_number in range(1, pro_review_rounds(goal) + 1)
    )


def _review_dir(goal_dir: Path, stage: str, round_number: int) -> Path:
    return goal_dir / PRO_REVIEW_ROOT / stage / f"round-{round_number:03d}"


def _load_selected(goal_dir: Path) -> tuple[Path, Document]:
    goal_dir = goal_dir.expanduser().resolve()
    project_root_for(goal_dir)
    goal = load_document(goal_dir / "goal.md")
    choices = parse_closeout_options(goal)
    if PRO_REVIEW_OPTION not in choices:
        raise LedgerError(
            f"{goal.path}: {PRO_REVIEW_OPTION} requires ledger_version 6 or newer"
        )
    if choices[PRO_REVIEW_OPTION] != "yes":
        raise LedgerError(
            f"{goal.path}: {PRO_REVIEW_OPTION} must be yes before preparing or recording a review"
        )
    pro_review_rounds(goal)
    pro_review_stage(goal)
    pro_review_delivery(goal)
    pro_review_gate(goal)
    return goal_dir, goal


def _validate_review_selection(goal: Document, stage: str, round_number: int) -> None:
    if stage not in configured_stages(goal):
        raise LedgerError(
            f"stage {stage!r} is not selected by pro_review_stage={pro_review_stage(goal)!r}"
        )
    if not 1 <= round_number <= pro_review_rounds(goal):
        raise LedgerError(
            f"round must be within the configured 1-{pro_review_rounds(goal)} range"
        )


def _relative_source(project_root: Path, raw: str | Path) -> tuple[Path, str]:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise LedgerError(f"context file does not exist: {raw}") from exc
    try:
        relative = resolved.relative_to(project_root).as_posix()
    except ValueError as exc:
        raise LedgerError(f"context file is outside the project root: {resolved}") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise LedgerError(f"context path must be a regular non-symlink file: {resolved}")
    path_parts = {part.casefold() for part in PurePosixPath(relative).parts}
    if path_parts & FORBIDDEN_PARTS or resolved.name.casefold() in FORBIDDEN_NAMES:
        raise LedgerError(f"refusing likely secret or dependency path in Pro packet: {relative}")
    if resolved.stat().st_size > MAX_CONTEXT_FILE_BYTES:
        raise LedgerError(
            f"context file exceeds {MAX_CONTEXT_FILE_BYTES} bytes: {relative}"
        )
    return resolved, relative


def _context_reasons(values: Iterable[str]) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise LedgerError("--context-reason must use PATH=REASON")
        path, reason = value.split("=", 1)
        path = path.strip()
        reason = _single_line("context reason", reason)
        if not path:
            raise LedgerError("context reason path must not be empty")
        reasons[path] = reason
    return reasons


def _git_output(project_root: Path, *arguments: str) -> str:
    try:
        process = subprocess.run(
            ["git", *arguments],
            cwd=project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unavailable"
    if process.returncode != 0:
        return "unavailable"
    return process.stdout.rstrip() or "none"


def _repo_state(project_root: Path, *, excluded_prefix: str) -> bytes:
    branch = _git_output(project_root, "branch", "--show-current")
    head = _git_output(project_root, "rev-parse", "HEAD")
    status = _git_output(project_root, "status", "--short")
    if status not in {"none", "unavailable"}:
        status_lines = [
            line for line in status.splitlines() if excluded_prefix not in line
        ]
        status = (
            f"{len(status_lines)} changed or untracked entries; unrelated paths omitted."
            if status_lines
            else "none"
        )
    diff_stat = _git_output(project_root, "diff", "--stat")
    if diff_stat not in {"none", "unavailable"}:
        diff_stat = diff_stat.splitlines()[-1]
    return (
        "# Repository state at packet preparation\n\n"
        f"Branch: {branch}\n"
        f"HEAD: {head}\n\n"
        "## Working-tree summary\n\n"
        f"{status}\n\n"
        "## Diff summary\n\n"
        f"{diff_stat}\n"
    ).encode("utf-8")


def _request_markdown(
    goal: Document,
    *,
    stage: str,
    round_number: int,
    decision: str,
    questions: tuple[str, ...],
    context_paths: tuple[str, ...],
) -> bytes:
    title = goal.metadata.get("title", goal.metadata.get("slug", "Goal Ledger review"))
    outcome = strip_markdown(get_section(goal, "Outcome")).strip()
    criteria = strip_markdown(get_section(goal, "Success criteria")).strip()
    scope = strip_markdown(get_section(goal, "Scope")).strip()
    authorization = strip_markdown(get_section(goal, "Authorization")).strip()
    question_rows = "\n".join(f"- {question}" for question in questions) or (
        "- Identify any blocking gap, weak assumption, missing test, or unsafe inference.\n"
        "- State whether the reviewed decision is ready to proceed."
    )
    evidence_rows = "\n".join(f"- `{path}`" for path in context_paths)
    return (
        f"# GPT Pro review: {title}\n\n"
        "## Role\n\n"
        f"Act as an independent GPT Pro reviewer for the {stage} decision in Goal Ledger "
        f"round {round_number}. Use only the attached packet. Separate verified facts from "
        "inference and name missing evidence instead of inventing it.\n\n"
        "## Decision\n\n"
        f"{decision}\n\n"
        "## Success criteria\n\n"
        f"Goal outcome: {outcome or 'See goal.md.'}\n\n"
        f"Completion criteria: {criteria or 'See goal.md.'}\n\n"
        "## Constraints\n\n"
        f"Scope: {scope or 'See goal.md.'}\n\n"
        f"Authorization: {authorization or 'See goal.md.'}\n\n"
        "Treat feature or architecture expansions as optional proposals, not required changes, "
        "unless they are necessary to make the stated decision correct.\n\n"
        "## Evidence received\n\n"
        "The ZIP contains `START-HERE.md`, `packet-index.json`, `repo-state.txt`, and these "
        "explicitly selected repository files:\n\n"
        f"{evidence_rows}\n\n"
        "Do not claim access to local paths, tools, files, or test state outside this packet.\n\n"
        "## Review questions\n\n"
        f"{question_rows}\n\n"
        "## Output\n\n"
        "Respond with the complete review in exactly this top-level shape:\n\n"
        "```text\n"
        "Verdict: SIGNED OFF | BLOCKED\n\n"
        "Required changes:\n"
        "- ...\n\n"
        "Risks:\n"
        "- ...\n\n"
        "Tests or verification:\n"
        "- ...\n\n"
        "Reasoning notes:\n"
        "- ...\n"
        "```\n\n"
        "`SIGNED OFF` means no blocking issue remains for this exact decision and packet. "
        "`BLOCKED` means at least one required change or unresolved question should stop it.\n\n"
        "## Stop rules\n\n"
        "Do not implement, browse, or assume omitted repository state. Stop after one complete "
        "review. If evidence is insufficient, return `BLOCKED` and identify the smallest missing "
        "evidence.\n"
    ).encode("utf-8")


def _zip_bytes(members: Mapping[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, members[name])
    return stream.getvalue()


def _packet_manifest_markdown(manifest: Mapping[str, Any]) -> bytes:
    rows = "\n".join(
        f"| `{item['path']}` | {item['bytes']} | `{item['sha256']}` | "
        f"{str(item['reason']).replace('|', r'\|')} |"
        for item in manifest["source_files"]
    )
    exclusions = "\n".join(f"- {item}" for item in manifest["exclusions"])
    return (
        "# GPT Pro packet manifest\n\n"
        f"- Stage: `{manifest['stage']}`\n"
        f"- Round: `{manifest['round']}`\n"
        f"- Archive: `{manifest['archive']}`\n"
        f"- Archive bytes: `{manifest['archive_bytes']}`\n"
        f"- Archive SHA-256: `{manifest['archive_sha256']}`\n"
        f"- Request SHA-256: `{manifest['request_sha256']}`\n\n"
        "## Included source files\n\n"
        "| Path | Bytes | SHA-256 | Inclusion reason |\n"
        "| --- | ---: | --- | --- |\n"
        f"{rows}\n\n"
        "## Explicit exclusions\n\n"
        f"{exclusions}\n"
    ).encode("utf-8")


def _state_bytes(
    *,
    status: str,
    stage: str,
    round_number: int,
    packet_sha256: str,
    next_action: str,
    response_sha256: str | None = None,
    verdict: str | None = None,
) -> bytes:
    value: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "stage": stage,
        "round": round_number,
        "packet_sha256": packet_sha256,
        "next_action": next_action,
    }
    if response_sha256 is not None:
        value["response_sha256"] = response_sha256
    if verdict is not None:
        value["verdict"] = verdict
    return _canonical_json(value)


def prepare_review(
    goal_dir: Path,
    *,
    stage: str,
    round_number: int,
    decision: str,
    questions: tuple[str, ...],
    context_files: tuple[str, ...],
    context_reasons: Mapping[str, str],
) -> tuple[Path, tuple[Path, ...]]:
    goal_dir, goal = _load_selected(goal_dir)
    _validate_review_selection(goal, stage, round_number)
    decision = _single_line("decision", decision)
    questions = tuple(_single_line("review question", value) for value in questions)
    project_root = project_root_for(goal_dir)

    automatic = {
        (goal_dir / "goal.md").resolve(): "Canonical goal contract and decision boundary.",
        (goal_dir / "progress.md").resolve(): "Current execution, custody, evidence, and gates.",
    }
    selected: dict[Path, tuple[str, str]] = {}
    for path, reason in automatic.items():
        relative = path.relative_to(project_root).as_posix()
        selected[path] = (relative, reason)
    for raw in context_files:
        path, relative = _relative_source(project_root, raw)
        reason = (
            context_reasons.get(raw)
            or context_reasons.get(relative)
            or "Explicitly selected decision-relevant context."
        )
        selected[path] = (relative, _single_line("context reason", reason))

    unused_reasons = sorted(
        key
        for key in context_reasons
        if key not in context_files and key not in {relative for relative, _ in selected.values()}
    )
    if unused_reasons:
        raise LedgerError("context reasons do not match selected files: " + ", ".join(unused_reasons))

    source_files: list[dict[str, Any]] = []
    context_members: dict[str, bytes] = {}
    total = 0
    for path, (relative, reason) in sorted(selected.items(), key=lambda item: item[1][0]):
        data = path.read_bytes()
        total += len(data)
        source_files.append(
            {
                "path": relative,
                "bytes": len(data),
                "sha256": _sha(data),
                "reason": reason,
            }
        )
        context_members[f"context/{relative}"] = data
    if total > MAX_PACKET_BYTES:
        raise LedgerError(f"selected context exceeds {MAX_PACKET_BYTES} bytes")

    context_paths = tuple(item["path"] for item in source_files)
    request = _request_markdown(
        goal,
        stage=stage,
        round_number=round_number,
        decision=decision,
        questions=questions,
        context_paths=context_paths,
    )
    review_root_relative = (goal_dir / PRO_REVIEW_ROOT).relative_to(project_root).as_posix()
    repo_state = _repo_state(project_root, excluded_prefix=review_root_relative)
    packet_index = {
        "schema_version": 1,
        "goal_slug": goal.metadata.get("slug", goal_dir.name),
        "stage": stage,
        "round": round_number,
        "decision": decision,
        "request_sha256": _sha(request),
        "source_files": source_files,
        "generated_members": ["START-HERE.md", "packet-index.json", "repo-state.txt"],
        "exclusions": [
            "No repository file is included unless listed above.",
            "Secrets, credentials, dependency trees, VCS internals, and the Pro review evidence tree are excluded.",
            "Local paths are not evidence; Pro receives only ZIP members.",
        ],
    }
    members = dict(context_members)
    members["START-HERE.md"] = request
    members["packet-index.json"] = _canonical_json(packet_index)
    members["repo-state.txt"] = repo_state
    packet = _zip_bytes(members)
    if len(packet) > MAX_PACKET_BYTES:
        raise LedgerError(f"compressed packet exceeds {MAX_PACKET_BYTES} bytes")

    round_dir = _review_dir(goal_dir, stage, round_number)
    archive_name = "context-packet.zip"
    delivery_plan = _delivery_plan(goal)
    configured_delivery = pro_review_delivery(goal)
    manifest = {
        "schema_version": 1,
        "stage": stage,
        "round": round_number,
        "decision": decision,
        "archive": archive_name,
        "archive_bytes": len(packet),
        "archive_sha256": _sha(packet),
        "request_sha256": _sha(request),
        "source_files": source_files,
        "zip_members": [
            {"path": name, "bytes": len(data), "sha256": _sha(data)}
            for name, data in sorted(members.items())
        ],
        "exclusions": packet_index["exclusions"],
    }
    artifacts = {
        round_dir / "request.md": request,
        round_dir / archive_name: packet,
        round_dir / "packet-manifest.json": _canonical_json(manifest),
        round_dir / "packet-manifest.md": _packet_manifest_markdown(manifest),
        round_dir / "delivery-plan.json": _canonical_json(delivery_plan),
        round_dir / "state.json": _state_bytes(
            status=(
                "manual-handoff-ready"
                if configured_delivery == "owner-handoff"
                else "packet-ready"
            ),
            stage=stage,
            round_number=round_number,
            packet_sha256=_sha(packet),
            next_action=(
                "Give request.md and context-packet.zip to the owner for manual Pro submission."
                if configured_delivery == "owner-handoff"
                else "Probe the next delivery-plan.json surface with Computer Use and record its result."
            ),
        ),
    }
    if configured_delivery == "owner-handoff":
        artifacts[round_dir / "manual-handoff.md"] = _manual_handoff_markdown(
            goal_dir,
            stage=stage,
            round_number=round_number,
            packet_sha256=_sha(packet),
        )
    changed = tuple(path for path, data in artifacts.items() if _write_immutable(path, data))
    return round_dir, changed


def _load_manifest(round_dir: Path) -> dict[str, Any]:
    path = round_dir / "packet-manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LedgerError(f"missing prepared Pro packet manifest: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(f"invalid Pro packet manifest JSON: {path}") from exc
    if not isinstance(value, dict):
        raise LedgerError(f"Pro packet manifest must be an object: {path}")
    return value


def record_transport_attempt(
    goal_dir: Path,
    *,
    stage: str,
    round_number: int,
    surface: str,
    result: str,
    detail: str,
) -> tuple[Path, str]:
    """Record one Computer Use surface probe and advance or fall back safely."""
    goal_dir, goal = _load_selected(goal_dir)
    _validate_review_selection(goal, stage, round_number)
    if surface not in ASSISTED_SURFACES:
        raise LedgerError("surface must be safari-assisted, chrome-assisted, or chatgpt-desktop")
    if result not in TRANSPORT_RESULTS:
        raise LedgerError("result must be " + ", ".join(TRANSPORT_RESULTS))
    detail = _single_line("attempt detail", detail)
    round_dir = _review_dir(goal_dir, stage, round_number)
    manifest = _load_manifest(round_dir)
    configured = pro_review_delivery(goal)
    ordered = tuple(
        candidate
        for candidate in delivery_candidates(configured)
        if candidate in ASSISTED_SURFACES
    )
    if not ordered:
        raise LedgerError("configured owner-handoff delivery has no assisted surface to probe")
    attempts_path = round_dir / "transport-attempts.json"
    attempts_value = _json_object(attempts_path, []) if attempts_path.exists() else None
    attempts = list(attempts_value.get("attempts", [])) if attempts_value else []
    if any(isinstance(item, dict) and item.get("result") == "ready" for item in attempts):
        raise LedgerError("a ready Pro surface is already recorded; submit once or inspect state")
    attempted_surfaces = [
        str(item.get("surface")) for item in attempts if isinstance(item, dict)
    ]
    remaining = [candidate for candidate in ordered if candidate not in attempted_surfaces]
    if not remaining:
        raise LedgerError("all configured assisted Pro surfaces were already attempted")
    if surface != remaining[0]:
        raise LedgerError(
            f"next configured Pro surface is {remaining[0]!r}; received {surface!r}"
        )
    attempts.append(
        {
            "attempted_at": datetime.now(timezone.utc).isoformat(),
            "surface": surface,
            "result": result,
            "detail": detail,
        }
    )
    record = {
        "schema_version": 1,
        "configured_delivery": configured,
        "attempts": attempts,
    }
    _atomic_write(attempts_path, _canonical_json(record))

    if result == "ready":
        status = "ui-ready"
        next_action = f"Submit the prepared request and ZIP once through {surface}."
    else:
        remaining_after = [candidate for candidate in ordered if candidate != surface and candidate not in attempted_surfaces]
        if remaining_after:
            status = "packet-ready"
            next_action = f"Probe the next configured Pro surface: {remaining_after[0]}."
        else:
            status = "manual-handoff-ready"
            next_action = "Give manual-handoff.md and the exact packet paths to the owner."
            _write_immutable(
                round_dir / "manual-handoff.md",
                _manual_handoff_markdown(
                    goal_dir,
                    stage=stage,
                    round_number=round_number,
                    packet_sha256=str(manifest["archive_sha256"]),
                ),
            )
    _atomic_write(
        round_dir / "state.json",
        _state_bytes(
            status=status,
            stage=stage,
            round_number=round_number,
            packet_sha256=str(manifest["archive_sha256"]),
            next_action=next_action,
        ),
    )
    return attempts_path, status


def record_submission(
    goal_dir: Path,
    *,
    stage: str,
    round_number: int,
    model_visible: str,
    transport: str,
    thread: str,
) -> Path:
    goal_dir, goal = _load_selected(goal_dir)
    _validate_review_selection(goal, stage, round_number)
    model_visible = _single_line("visible model", model_visible)
    normalized_model = " ".join(re.sub(r"[^a-z0-9]+", " ", model_visible.casefold()).split())
    if not (
        normalized_model.startswith("pro")
        or normalized_model.startswith("extended pro")
        or "gpt pro" in normalized_model
        or "chatgpt pro" in normalized_model
    ):
        raise LedgerError(
            "visible model evidence must identify a Pro mode; do not record another model"
        )
    if transport not in SUBMISSION_TRANSPORTS:
        raise LedgerError(
            "transport must be safari-assisted, chrome-assisted, chatgpt-desktop, or owner-handoff"
        )
    configured = pro_review_delivery(goal)
    if configured != "auto-ui" and transport != configured:
        raise LedgerError(
            f"recorded transport {transport!r} does not match configured delivery {configured!r}"
        )
    round_dir = _review_dir(goal_dir, stage, round_number)
    manifest = _load_manifest(round_dir)
    packet = (round_dir / "context-packet.zip").read_bytes()
    if _sha(packet) != manifest.get("archive_sha256"):
        raise LedgerError("prepared Pro packet hash does not match its manifest")
    submission_path = round_dir / "submission.json"
    if submission_path.exists():
        raise LedgerError(
            f"submission already recorded: {submission_path}; inspect state instead of resubmitting"
        )
    attempts_path = round_dir / "transport-attempts.json"
    if goal.metadata.get("ledger_version") == "7":
        attempts = (
            json.loads(attempts_path.read_text(encoding="utf-8")).get("attempts", [])
            if attempts_path.is_file()
            else []
        )
        if transport in ASSISTED_SURFACES and not any(
            isinstance(item, dict)
            and item.get("surface") == transport
            and item.get("result") == "ready"
            for item in attempts
        ):
            raise LedgerError("ledger v7 requires a ready transport attempt for this assisted surface")
        if (
            transport == "owner-handoff"
            and configured == "auto-ui"
            and not (round_dir / "manual-handoff.md").is_file()
        ):
            raise LedgerError(
                "auto-ui owner handoff requires exhausted assisted routing and manual-handoff.md"
            )
    record = {
        "schema_version": 1,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "round": round_number,
        "transport": transport,
        "model_visible": model_visible,
        "thread": _single_line("thread", thread),
        "evidence_received": ["request.md", "context-packet.zip"],
        "packet_sha256": manifest["archive_sha256"],
        "request_sha256": manifest["request_sha256"],
        "scope_basis": "Recorded Goal Ledger GPT Pro choice and exact packet manifest.",
    }
    _write_immutable(submission_path, _canonical_json(record))
    _atomic_write(
        round_dir / "state.json",
        _state_bytes(
            status="submitted-waiting-response",
            stage=stage,
            round_number=round_number,
            packet_sha256=manifest["archive_sha256"],
            next_action="Wait for the existing Pro response; do not submit the packet again.",
        ),
    )
    return submission_path


def _response_verdict(text: str) -> str:
    match = re.match(r"\ufeff?\s*Verdict:\s*(SIGNED OFF|BLOCKED)\s*$", text, re.MULTILINE)
    if not match:
        raise LedgerError("Pro response must begin with Verdict: SIGNED OFF or Verdict: BLOCKED")
    return match.group(1)


def record_response(
    goal_dir: Path,
    *,
    stage: str,
    round_number: int,
    response_file: Path,
) -> tuple[Path, str]:
    goal_dir, goal = _load_selected(goal_dir)
    _validate_review_selection(goal, stage, round_number)
    round_dir = _review_dir(goal_dir, stage, round_number)
    if not (round_dir / "submission.json").is_file():
        raise LedgerError("record the actual Pro submission before recording its response")
    raw = response_file.expanduser().read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LedgerError("Pro response must be UTF-8 text") from exc
    verdict = _response_verdict(text)
    response_path = round_dir / "response.md"
    _write_immutable(response_path, raw)
    metadata = {
        "schema_version": 1,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "bytes": len(raw),
        "sha256": _sha(raw),
        "verdict": verdict,
    }
    metadata_path = round_dir / "response-metadata.json"
    if not metadata_path.exists():
        _write_immutable(metadata_path, _canonical_json(metadata))
    else:
        existing = json.loads(metadata_path.read_text(encoding="utf-8"))
        if existing.get("bytes") != len(raw) or existing.get("sha256") != _sha(raw) or existing.get("verdict") != verdict:
            raise LedgerError("stored Pro response metadata conflicts with the raw response")
    manifest = _load_manifest(round_dir)
    _atomic_write(
        round_dir / "state.json",
        _state_bytes(
            status="response-received",
            stage=stage,
            round_number=round_number,
            packet_sha256=manifest["archive_sha256"],
            response_sha256=_sha(raw),
            verdict=verdict,
            next_action="Verify the response against current repository evidence and record reconciliation.",
        ),
    )
    return response_path, verdict


def _string_list(name: str, value: Any) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise LedgerError(f"{name} must be a list of non-empty strings")
    return [item.strip() for item in value]


def _reconciliation_markdown(value: Mapping[str, Any], response_sha256: str) -> bytes:
    items = value["items"]
    rows = []
    for item in items:
        evidence = "; ".join(item["evidence"]) or "None recorded."
        rows.append(
            f"- **{item['classification']} — {item['finding']}**\n"
            f"  - Disposition: {item['disposition']}\n"
            f"  - Evidence: {evidence}"
        )
    item_text = "\n".join(rows) if rows else "- No actionable findings."
    verification = "\n".join(f"- {item}" for item in value["local_verification"])
    return (
        "# GPT Pro review reconciliation\n\n"
        f"- Pro verdict: `{value['pro_verdict']}`\n"
        f"- Raw response SHA-256: `{response_sha256}`\n\n"
        "## Reconciled actions\n\n"
        f"{item_text}\n\n"
        "## Local verification\n\n"
        f"{verification or '- None recorded.'}\n\n"
        "## Next action\n\n"
        f"{value['next_action']}\n"
    ).encode("utf-8")


def _reconciliation_structure_problems(
    value: Mapping[str, Any], *, verdict: str, response_sha256: str
) -> list[str]:
    problems: list[str] = []
    if value.get("schema_version") != 1:
        problems.append("reconciliation schema_version must be 1")
    if value.get("pro_verdict") != verdict:
        problems.append("reconciliation verdict does not match raw response")
    if value.get("response_sha256") != response_sha256:
        problems.append("reconciliation is not bound to the raw response hash")
    items = value.get("items")
    if not isinstance(items, list):
        problems.append("reconciliation items must be a list")
        items = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            problems.append(f"reconciliation item {index} must be an object")
            continue
        if item.get("classification") not in VALID_CLASSIFICATIONS:
            problems.append(f"reconciliation item {index} has an invalid classification")
        for field in ("finding", "disposition"):
            field_value = item.get(field)
            if not isinstance(field_value, str) or not field_value.strip() or "\n" in field_value:
                problems.append(f"reconciliation item {index} {field} must be one non-empty line")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or any(
            not isinstance(entry, str) or not entry.strip() for entry in evidence
        ):
            problems.append(f"reconciliation item {index} evidence must be a string list")
    if verdict == "BLOCKED" and not any(
        isinstance(item, dict) and item.get("classification") in {"FIX", "QUESTION"}
        for item in items
    ):
        problems.append("a BLOCKED reconciliation needs at least one FIX or QUESTION")
    local_verification = value.get("local_verification")
    if not isinstance(local_verification, list) or any(
        not isinstance(entry, str) or not entry.strip() for entry in local_verification
    ):
        problems.append("local_verification must be a string list")
    next_action = value.get("next_action")
    if not isinstance(next_action, str) or not next_action.strip() or "\n" in next_action:
        problems.append("next_action must be one non-empty line")
    return problems


def record_reconciliation(
    goal_dir: Path,
    *,
    stage: str,
    round_number: int,
    reconciliation_file: Path,
) -> tuple[Path, str]:
    goal_dir, goal = _load_selected(goal_dir)
    _validate_review_selection(goal, stage, round_number)
    round_dir = _review_dir(goal_dir, stage, round_number)
    response = (round_dir / "response.md").read_bytes()
    verdict = _response_verdict(response.decode("utf-8"))
    try:
        value = json.loads(reconciliation_file.expanduser().read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LedgerError("reconciliation must be valid JSON") from exc
    if not isinstance(value, dict):
        raise LedgerError("reconciliation must be a JSON object")
    if value.get("pro_verdict") != verdict:
        raise LedgerError("reconciliation pro_verdict must match the raw Pro response")
    items = value.get("items")
    if not isinstance(items, list):
        raise LedgerError("reconciliation items must be a list")
    normalized_items: list[dict[str, Any]] = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise LedgerError(f"reconciliation item {index} must be an object")
        classification = item.get("classification")
        if classification not in VALID_CLASSIFICATIONS:
            raise LedgerError(
                f"reconciliation item {index} classification must be one of "
                + ", ".join(VALID_CLASSIFICATIONS)
            )
        normalized_items.append(
            {
                "classification": classification,
                "finding": _single_line("finding", str(item.get("finding", ""))),
                "disposition": _single_line("disposition", str(item.get("disposition", ""))),
                "evidence": _string_list("item evidence", item.get("evidence", [])),
            }
        )
    if verdict == "BLOCKED" and not any(
        item["classification"] in {"FIX", "QUESTION"} for item in normalized_items
    ):
        raise LedgerError("a BLOCKED review needs at least one FIX or QUESTION disposition")
    normalized = {
        "schema_version": 1,
        "pro_verdict": verdict,
        "response_sha256": _sha(response),
        "items": normalized_items,
        "local_verification": _string_list(
            "local_verification", value.get("local_verification", [])
        ),
        "next_action": _single_line("next_action", str(value.get("next_action", ""))),
    }
    json_path = round_dir / "reconciliation.json"
    md_path = round_dir / "reconciliation.md"
    _write_immutable(json_path, _canonical_json(normalized))
    _write_immutable(md_path, _reconciliation_markdown(normalized, _sha(response)))
    manifest = _load_manifest(round_dir)
    status = "reconciled-signed-off" if verdict == "SIGNED OFF" else "reconciled-blocked"
    _atomic_write(
        round_dir / "state.json",
        _state_bytes(
            status=status,
            stage=stage,
            round_number=round_number,
            packet_sha256=manifest["archive_sha256"],
            response_sha256=_sha(response),
            verdict=verdict,
            next_action=normalized["next_action"],
        ),
    )
    return md_path, verdict


def _json_object(path: Path, problems: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        problems.append(f"missing Pro review artifact: {path.name}")
        return None
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"invalid Pro review JSON {path.name}: {exc}")
        return None
    if not isinstance(value, dict):
        problems.append(f"Pro review JSON must be an object: {path.name}")
        return None
    return value


def _review_problems(round_dir: Path, *, require_closed: bool) -> list[str]:
    problems: list[str] = []
    manifest = _json_object(round_dir / "packet-manifest.json", problems)
    request_path = round_dir / "request.md"
    packet_path = round_dir / "context-packet.zip"
    if not request_path.is_file():
        problems.append("missing Pro review artifact: request.md")
    if not packet_path.is_file():
        problems.append("missing Pro review artifact: context-packet.zip")
    if manifest is not None and request_path.is_file() and packet_path.is_file():
        request = request_path.read_bytes()
        packet = packet_path.read_bytes()
        if manifest.get("request_sha256") != _sha(request):
            problems.append("Pro request hash does not match packet manifest")
        if manifest.get("archive_sha256") != _sha(packet):
            problems.append("Pro packet hash does not match packet manifest")
        try:
            with zipfile.ZipFile(io.BytesIO(packet)) as archive:
                members = {name: archive.read(name) for name in archive.namelist()}
        except (zipfile.BadZipFile, KeyError, OSError) as exc:
            problems.append(f"invalid Pro context packet ZIP: {exc}")
        else:
            if members.get("START-HERE.md") != request:
                problems.append("Pro packet START-HERE.md does not match request.md")
            for item in manifest.get("zip_members", []):
                if not isinstance(item, dict) or item.get("path") not in members:
                    problems.append("Pro packet manifest names a missing ZIP member")
                    continue
                data = members[item["path"]]
                if item.get("bytes") != len(data) or item.get("sha256") != _sha(data):
                    problems.append(f"Pro ZIP member hash mismatch: {item['path']}")

    delivery_plan = None
    if (round_dir / "delivery-plan.json").exists():
        delivery_plan = _json_object(round_dir / "delivery-plan.json", problems)
        if delivery_plan is not None:
            candidates = delivery_plan.get("candidates")
            if not isinstance(candidates, list) or not candidates or any(
                candidate not in SUBMISSION_TRANSPORTS for candidate in candidates
            ):
                problems.append("Pro delivery plan has invalid candidates")

    attempts = None
    if (round_dir / "transport-attempts.json").exists():
        attempts = _json_object(round_dir / "transport-attempts.json", problems)
        if attempts is not None:
            attempt_rows = attempts.get("attempts")
            if not isinstance(attempt_rows, list):
                problems.append("Pro transport attempts must be a list")
            else:
                seen: set[str] = set()
                for item in attempt_rows:
                    if not isinstance(item, dict):
                        problems.append("Pro transport attempt must be an object")
                        continue
                    surface = item.get("surface")
                    if surface not in ASSISTED_SURFACES or surface in seen:
                        problems.append("Pro transport attempts contain an invalid or duplicate surface")
                    seen.add(str(surface))
                    if item.get("result") not in TRANSPORT_RESULTS:
                        problems.append("Pro transport attempt has an invalid result")

    submission = _json_object(round_dir / "submission.json", problems) if require_closed or (round_dir / "submission.json").exists() else None
    if submission is not None and manifest is not None:
        if submission.get("packet_sha256") != manifest.get("archive_sha256"):
            problems.append("Pro submission packet hash does not match manifest")
        if "pro" not in str(submission.get("model_visible", "")).casefold():
            problems.append("Pro submission does not record a visible Pro model")
        if submission.get("transport") not in SUBMISSION_TRANSPORTS:
            problems.append("Pro submission has an invalid transport")

    response_path = round_dir / "response.md"
    response_metadata = None
    if require_closed or response_path.exists() or (round_dir / "response-metadata.json").exists():
        if not response_path.is_file():
            problems.append("missing Pro review artifact: response.md")
        response_metadata = _json_object(round_dir / "response-metadata.json", problems)
    verdict = None
    response = None
    if response_path.is_file():
        response = response_path.read_bytes()
        try:
            verdict = _response_verdict(response.decode("utf-8"))
        except (UnicodeDecodeError, LedgerError) as exc:
            problems.append(f"invalid raw Pro response: {exc}")
        if response_metadata is not None:
            if response_metadata.get("sha256") != _sha(response):
                problems.append("Pro response metadata hash does not match raw response")
            if response_metadata.get("bytes") != len(response):
                problems.append("Pro response metadata byte count does not match raw response")
            if verdict and response_metadata.get("verdict") != verdict:
                problems.append("Pro response metadata verdict does not match raw response")

    reconciliation = None
    if require_closed or (round_dir / "reconciliation.json").exists() or (round_dir / "reconciliation.md").exists():
        reconciliation = _json_object(round_dir / "reconciliation.json", problems)
        if not (round_dir / "reconciliation.md").is_file():
            problems.append("missing Pro review artifact: reconciliation.md")
    if reconciliation is not None and response is not None:
        if verdict:
            structure = _reconciliation_structure_problems(
                reconciliation, verdict=verdict, response_sha256=_sha(response)
            )
            problems.extend(f"Pro {problem}" for problem in structure)
            if not structure:
                expected_md = _reconciliation_markdown(reconciliation, _sha(response))
                md_path = round_dir / "reconciliation.md"
                if md_path.is_file() and md_path.read_bytes() != expected_md:
                    problems.append("Pro reconciliation Markdown does not match reconciliation JSON")

    state = _json_object(round_dir / "state.json", problems)
    if state is not None and manifest is not None:
        expected_status = "packet-ready"
        if (round_dir / "manual-handoff.md").is_file():
            expected_status = "manual-handoff-ready"
        if attempts is not None and isinstance(attempts.get("attempts"), list):
            if any(
                isinstance(item, dict) and item.get("result") == "ready"
                for item in attempts["attempts"]
            ):
                expected_status = "ui-ready"
        if submission is not None:
            expected_status = "submitted-waiting-response"
        if response is not None:
            expected_status = "response-received"
        if reconciliation is not None and verdict:
            expected_status = (
                "reconciled-signed-off" if verdict == "SIGNED OFF" else "reconciled-blocked"
            )
        if state.get("status") != expected_status:
            problems.append(
                f"Pro state status must be {expected_status}; found {state.get('status')!r}"
            )
        if state.get("packet_sha256") != manifest.get("archive_sha256"):
            problems.append("Pro state packet hash does not match manifest")
        if response is not None and state.get("response_sha256") != _sha(response):
            problems.append("Pro state response hash does not match raw response")
        if verdict and response is not None and state.get("verdict") != verdict:
            problems.append("Pro state verdict does not match raw response")
    return problems


def latest_reconciled_verdict(goal_dir: Path, goal: Document, stage: str) -> str | None:
    for round_number in range(pro_review_rounds(goal), 0, -1):
        path = _review_dir(goal_dir, stage, round_number) / "reconciliation.json"
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        verdict = value.get("pro_verdict")
        return verdict if verdict in {"SIGNED OFF", "BLOCKED"} else None
    return None


def pro_review_problems(
    goal_dir: Path,
    *,
    require_closed: bool = False,
) -> list[str]:
    goal_dir = goal_dir.resolve()
    goal = load_document(goal_dir / "goal.md")
    choices = parse_closeout_options(goal)
    if PRO_REVIEW_OPTION not in choices:
        return []
    problems: list[str] = []
    try:
        configured = configured_reviews(goal)
        gate = pro_review_gate(goal)
        pro_review_delivery(goal)
    except LedgerError as exc:
        return [str(exc)]
    root = goal_dir / PRO_REVIEW_ROOT
    for stage, round_number in configured:
        round_dir = _review_dir(goal_dir, stage, round_number)
        if choices[PRO_REVIEW_OPTION] == "yes" and require_closed:
            if not round_dir.is_dir():
                problems.append(
                    f"missing selected GPT Pro review: {stage} round {round_number}"
                )
                continue
            problems.extend(
                f"{stage} round {round_number}: {problem}"
                for problem in _review_problems(round_dir, require_closed=True)
            )
        elif round_dir.exists():
            problems.extend(
                f"{stage} round {round_number}: {problem}"
                for problem in _review_problems(round_dir, require_closed=False)
            )
    if choices[PRO_REVIEW_OPTION] == "yes" and require_closed and gate == "required":
        for stage in configured_stages(goal):
            if latest_reconciled_verdict(goal_dir, goal, stage) != "SIGNED OFF":
                problems.append(f"required GPT Pro {stage} review is not signed off")
    if root.exists() and not root.is_dir():
        problems.append(f"Pro review evidence root is not a directory: {root}")
    return problems


def pro_plan_gate_problem(goal_dir: Path, goal: Document, progress: Document) -> str | None:
    choices = parse_closeout_options(goal)
    if choices.get(PRO_REVIEW_OPTION) != "yes":
        return None
    if "plan" not in configured_stages(goal) or pro_review_gate(goal) != "required":
        return None
    _, rows = parse_table(get_section(progress, "Phase tracker"))
    build_state = next(
        (
            normalize_state(strip_markdown(row[1]))
            for row in rows
            if len(row) > 1 and strip_markdown(row[0]).strip() == "Build"
        ),
        "pending",
    )
    if build_state in {"active", "complete"} and latest_reconciled_verdict(goal_dir, goal, "plan") != "SIGNED OFF":
        return "Build cannot be active or complete before the required GPT Pro plan review is reconciled and signed off"
    return None


def _add_review_positionals(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("goal_dir", type=Path)
    parser.add_argument("--stage", required=True, choices=VALID_STAGES)
    parser.add_argument("--round", dest="round_number", type=int, default=1)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Build an immutable prompt and scoped ZIP.")
    _add_review_positionals(prepare)
    prepare.add_argument("--decision", required=True)
    prepare.add_argument("--review-question", action="append", default=[])
    prepare.add_argument("--context-file", action="append", default=[])
    prepare.add_argument("--context-reason", action="append", default=[])

    attempt = subparsers.add_parser(
        "record-attempt", help="Record one platform-aware assisted UI readiness probe."
    )
    _add_review_positionals(attempt)
    attempt.add_argument("--surface", choices=ASSISTED_SURFACES, required=True)
    attempt.add_argument("--result", choices=TRANSPORT_RESULTS, required=True)
    attempt.add_argument("--detail", required=True)

    submission = subparsers.add_parser("record-submission", help="Record an observed Pro submission.")
    _add_review_positionals(submission)
    submission.add_argument("--model-visible", required=True)
    submission.add_argument("--transport", choices=SUBMISSION_TRANSPORTS, required=True)
    submission.add_argument("--thread", required=True)

    response = subparsers.add_parser("record-response", help="Preserve the full raw Pro response.")
    _add_review_positionals(response)
    response.add_argument("--response-file", required=True, type=Path)

    reconcile = subparsers.add_parser("reconcile", help="Record typed local reconciliation.")
    _add_review_positionals(reconcile)
    reconcile.add_argument("--reconciliation-file", required=True, type=Path)

    check = subparsers.add_parser("check", help="Validate native GPT Pro custody artifacts.")
    check.add_argument("goal_dir", type=Path)
    check.add_argument("--require-closed", action="store_true")
    return parser.parse_args(argv)


def _display(path: Path, goal_dir: Path) -> str:
    return path.resolve().relative_to(project_root_for(goal_dir.resolve())).as_posix()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "prepare":
            round_dir, changed = prepare_review(
                args.goal_dir,
                stage=args.stage,
                round_number=args.round_number,
                decision=args.decision,
                questions=tuple(args.review_question),
                context_files=tuple(args.context_file),
                context_reasons=_context_reasons(args.context_reason),
            )
            for path in changed:
                print(f"Wrote: {_display(path, args.goal_dir)}")
            if not changed:
                print(f"Pro packet already current: {_display(round_dir, args.goal_dir)}")
            return 0
        if args.command == "record-submission":
            path = record_submission(
                args.goal_dir,
                stage=args.stage,
                round_number=args.round_number,
                model_visible=args.model_visible,
                transport=args.transport,
                thread=args.thread,
            )
            print(f"Recorded: {_display(path, args.goal_dir)}")
            return 0
        if args.command == "record-attempt":
            path, status = record_transport_attempt(
                args.goal_dir,
                stage=args.stage,
                round_number=args.round_number,
                surface=args.surface,
                result=args.result,
                detail=args.detail,
            )
            print(f"Recorded: {_display(path, args.goal_dir)}")
            print(f"State: {status}")
            return 0
        if args.command == "record-response":
            path, verdict = record_response(
                args.goal_dir,
                stage=args.stage,
                round_number=args.round_number,
                response_file=args.response_file,
            )
            print(f"Recorded full Pro response: {_display(path, args.goal_dir)}")
            print(f"Verdict: {verdict}")
            return 0
        if args.command == "reconcile":
            path, verdict = record_reconciliation(
                args.goal_dir,
                stage=args.stage,
                round_number=args.round_number,
                reconciliation_file=args.reconciliation_file,
            )
            print(f"Recorded reconciliation: {_display(path, args.goal_dir)}")
            print(f"Verdict: {verdict}")
            return 0
        problems = pro_review_problems(args.goal_dir, require_closed=args.require_closed)
        if problems:
            for problem in problems:
                print(f"error: {problem}", file=sys.stderr)
            return 1
        print("GPT Pro review custody is valid.")
        return 0
    except (LedgerError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
