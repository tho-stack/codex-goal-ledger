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
MCP_READ_RECEIPTS_ROOT = Path("packet-read-receipts")
VALID_STAGES = ("plan", "implementation")
VALID_STAGE_SELECTIONS = ("plan", "implementation", "both")
VALID_DELIVERIES = (
    "auto-ui",
    "mcp-app",
    "native-chat",
    "safari-assisted",
    "chrome-assisted",
    "owner-handoff",
)
ROUTED_SURFACES = (
    "mcp-app",
    "native-chat",
    "safari-assisted",
    "chrome-assisted",
)
COMPUTER_USE_SURFACES = ("safari-assisted", "chrome-assisted")
SUBMISSION_TRANSPORTS = ROUTED_SURFACES + ("owner-handoff",)
LEGACY_EVIDENCE_TRANSPORTS = ("chatgpt-desktop",)
EVIDENCE_TRANSPORTS = SUBMISSION_TRANSPORTS + LEGACY_EVIDENCE_TRANSPORTS
TRANSPORT_RESULTS = (
    "unavailable",
    "not-authenticated",
    "pro-unavailable",
    "ready",
    "failed",
)
VALID_GATES = ("required", "advisory")
VALID_CLASSIFICATIONS = ("FIX", "DEFER", "DISMISS", "QUESTION")
RESPONSE_SECTIONS = (
    "Required changes",
    "Risks",
    "Tests or verification",
    "Reasoning notes",
)
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
    def reuse_existing() -> bool:
        if not path.is_file():
            raise LedgerError(f"custody artifact is not a regular file: {path}")
        if path.read_bytes() != data:
            raise LedgerError(
                f"immutable Pro review artifact differs: {path}; preserve this round and "
                "prepare a new round"
            )
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return reuse_existing()
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            return reuse_existing()
        return True
    finally:
        temporary.unlink(missing_ok=True)


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
    delivery = goal.metadata.get("pro_review_delivery", "auto-ui").strip()
    if delivery not in VALID_DELIVERIES:
        raise LedgerError(
            "pro_review_delivery must be auto-ui, mcp-app, native-chat, "
            "safari-assisted, chrome-assisted, or owner-handoff"
        )
    return delivery


def delivery_candidates(delivery: str, host_platform: str | None = None) -> tuple[str, ...]:
    """Return the platform-aware ordered UI route for one configured delivery."""
    if delivery != "auto-ui":
        return (delivery,)
    system = (host_platform or platform.system()).strip().casefold()
    if system in {"darwin", "mac", "macos"}:
        return (
            "mcp-app",
            "native-chat",
            "safari-assisted",
            "chrome-assisted",
            "owner-handoff",
        )
    return ("mcp-app", "native-chat", "chrome-assisted", "owner-handoff")


def _delivery_plan(goal: Document) -> dict[str, Any]:
    configured = pro_review_delivery(goal)
    return {
        "schema_version": 4,
        "configured_delivery": configured,
        "host_platform": platform.system() or "unknown",
        "candidates": list(delivery_candidates(configured)),
        "transport_drivers": {
            "mcp-app": "goal-ledger-restricted-mcp-app",
            "native-chat": "user-operated-chatgpt-in-codex",
            "browser": "computer-use-mcp",
        },
        "computer_use_surfaces": list(COMPUTER_USE_SURFACES),
        "automatic_submission": True,
        "submission_authority": (
            "Recorded GPT Pro yes authorizes the exact generated request and hashed ZIP; "
            "native Computer Use and platform confirmations remain binding."
        ),
        "excluded_surfaces": {
            "computer-use-chatgpt-host": (
                "Computer Use cannot safely inspect or operate its own ChatGPT desktop host; "
                "native Chat remains an explicit user-operated route."
            ),
            "in-app-browser": (
                "The built-in Browser cannot automate the required ZIP file upload."
            ),
        },
        "mcp_app_contract": {
            "packet_source": "immutable-context-packet-zip",
            "live_repository_access": False,
            "shell_access": False,
            "arbitrary_write_access": False,
            "response_sink": "immutable-response.md",
        },
        "readiness_contracts": {
            "mcp-app": [
                "The manifest-bound local MCP server passes its integrity preflight.",
                "The Secure MCP Tunnel and ChatGPT developer-mode app are connected.",
                "The owner confirms a visible GPT Pro or Pro Extended mode in the app control.",
            ],
            "native-chat": [
                "The owner can open Chat in the ChatGPT/Codex app.",
                "GPT Pro or Pro Extended is visibly selected.",
                "The exact ZIP can be attached and request.md can be submitted once.",
                "The completed conversation exposes Add to task for return to Codex.",
            ],
            "browser": [
                "Computer Use can inspect the surface.",
                "ChatGPT is authenticated.",
                "GPT Pro or Pro Extended is visibly selectable.",
                "File upload and text input are available.",
            ],
        },
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


def _native_chat_handoff_markdown(
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
    goal_relative = goal_dir.relative_to(project_root).as_posix()
    return (
        "# Native ChatGPT Pro handoff\n\n"
        "Use the Chat surface built into the ChatGPT/Codex app. This is a user-operated "
        "subscription route; Computer Use must not control the host app and no private "
        "ChatGPT session API may be replayed.\n\n"
        f"- Request: `{request}`\n"
        f"- ZIP: `{packet}`\n"
        f"- ZIP SHA-256: `{packet_sha256}`\n"
        "- Required model: a visibly selected GPT Pro or Pro Extended mode\n\n"
        "## Submit and return\n\n"
        "1. Click **Chat** in the left rail and start a clean conversation.\n"
        "2. Select GPT Pro or Pro Extended and verify the visible model label.\n"
        f"3. Attach exactly `{packet}` and paste exactly `{request}`.\n"
        "4. Submit once and wait for the complete answer.\n"
        "5. Click **Add to task** to return that Chat conversation to the current Codex task.\n"
        "6. In Codex, verify the imported content includes the response beginning and final "
        "section before recording it. If the import is incomplete, capture the full answer "
        "from the same conversation without resubmitting.\n"
        "7. Record the observed submission with:\n\n"
        "```bash\n"
        f"python3 scripts/run_pro_review.py record-submission {goal_relative} \\\n"
        f"  --stage {stage} --round {round_number} \\\n"
        "  --model-visible \"Pro Extended\" --transport native-chat \\\n"
        "  --thread \"<visible Chat conversation title>\"\n"
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
                else "Use native-chat-handoff.md and record the observed native Chat readiness."
                if configured_delivery == "native-chat"
                else "Check the next delivery-plan.json surface and record its result."
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
    if "native-chat" in delivery_candidates(configured_delivery):
        artifacts[round_dir / "native-chat-handoff.md"] = (
            _native_chat_handoff_markdown(
                goal_dir,
                stage=stage,
                round_number=round_number,
                packet_sha256=_sha(packet),
            )
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
    """Record one routed Pro surface check and advance or fall back safely."""
    goal_dir, goal = _load_selected(goal_dir)
    _validate_review_selection(goal, stage, round_number)
    if surface not in ROUTED_SURFACES:
        raise LedgerError(
            "surface must be mcp-app, native-chat, safari-assisted, or chrome-assisted"
        )
    if result not in TRANSPORT_RESULTS:
        raise LedgerError("result must be " + ", ".join(TRANSPORT_RESULTS))
    detail = _single_line("attempt detail", detail)
    round_dir = _review_dir(goal_dir, stage, round_number)
    manifest = _load_manifest(round_dir)
    configured = pro_review_delivery(goal)
    ordered = tuple(
        candidate
        for candidate in delivery_candidates(configured)
        if candidate in ROUTED_SURFACES
    )
    if not ordered:
        raise LedgerError("configured owner-handoff delivery has no routed surface to check")
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
        next_action = (
            "Follow native-chat-handoff.md, submit once in ChatGPT Pro, then click Add to task."
            if surface == "native-chat"
            else f"Submit the prepared request and ZIP once through {surface}."
        )
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
            "transport must be mcp-app, native-chat, safari-assisted, "
            "chrome-assisted, or owner-handoff"
        )
    configured = pro_review_delivery(goal)
    round_dir = _review_dir(goal_dir, stage, round_number)
    submission_path = round_dir / "submission.json"
    if submission_path.exists():
        existing = _json_object(submission_path, [])
        existing_transport = existing.get("transport") if existing else None
        if existing_transport != transport:
            raise LedgerError(
                f"review packet is already claimed through {existing_transport!r}; "
                f"refusing transport mixing with {transport!r}"
            )
        raise LedgerError(
            f"submission already recorded: {submission_path}; inspect state instead of resubmitting"
        )
    exhausted_to_owner = (
        transport == "owner-handoff" and (round_dir / "manual-handoff.md").is_file()
    )
    if configured != "auto-ui" and transport != configured and not exhausted_to_owner:
        raise LedgerError(
            f"recorded transport {transport!r} does not match configured delivery {configured!r}"
        )
    manifest = _load_manifest(round_dir)
    packet = (round_dir / "context-packet.zip").read_bytes()
    if _sha(packet) != manifest.get("archive_sha256"):
        raise LedgerError("prepared Pro packet hash does not match its manifest")
    attempts_path = round_dir / "transport-attempts.json"
    if goal.metadata.get("ledger_version") == "7":
        attempts = (
            json.loads(attempts_path.read_text(encoding="utf-8")).get("attempts", [])
            if attempts_path.is_file()
            else []
        )
        if transport in ROUTED_SURFACES and not any(
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


def record_mcp_submission_claim(
    goal_dir: Path,
    *,
    stage: str,
    round_number: int,
) -> tuple[Path, bool]:
    """Atomically claim one packet for MCP before exposing any member content."""
    goal_dir, goal = _load_selected(goal_dir)
    _validate_review_selection(goal, stage, round_number)
    configured = pro_review_delivery(goal)
    if configured not in {"auto-ui", "mcp-app"}:
        raise LedgerError(
            f"configured delivery {configured!r} does not authorize the mcp-app transport"
        )
    round_dir = _review_dir(goal_dir, stage, round_number)
    manifest = _load_manifest(round_dir)
    packet = (round_dir / "context-packet.zip").read_bytes()
    if _sha(packet) != manifest.get("archive_sha256"):
        raise LedgerError("prepared Pro packet hash does not match its manifest")
    if goal.metadata.get("ledger_version") == "7":
        attempts_path = round_dir / "transport-attempts.json"
        attempts = (
            json.loads(attempts_path.read_text(encoding="utf-8")).get("attempts", [])
            if attempts_path.is_file()
            else []
        )
        if not any(
            isinstance(item, dict)
            and item.get("surface") == "mcp-app"
            and item.get("result") == "ready"
            for item in attempts
        ):
            raise LedgerError("ledger v7 requires a ready mcp-app transport attempt")
    submission_path = round_dir / "submission.json"
    if submission_path.is_file():
        existing = _json_object(submission_path, [])
        if existing is None or existing.get("transport") != "mcp-app":
            raise LedgerError(
                f"review packet is already claimed through "
                f"{None if existing is None else existing.get('transport')!r}; "
                "refusing transport mixing with 'mcp-app'"
            )
        if existing.get("packet_sha256") != manifest["archive_sha256"]:
            raise LedgerError("existing MCP submission claim names a different packet")
        return submission_path, False
    record = {
        "schema_version": 2,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "round": round_number,
        "transport": "mcp-app",
        "submission_kind": "mcp-workspace-claim",
        "model_visible": None,
        "thread": None,
        "evidence_received": ["request.md", "context-packet.zip"],
        "packet_sha256": manifest["archive_sha256"],
        "request_sha256": manifest["request_sha256"],
        "scope_basis": "First manifest-bound MCP workspace access; visible model and thread are unconfirmed.",
    }
    try:
        created = _write_immutable(submission_path, _canonical_json(record))
    except LedgerError:
        existing = _json_object(submission_path, []) if submission_path.is_file() else None
        if existing and existing.get("transport") != "mcp-app":
            raise LedgerError(
                f"review packet is already claimed through {existing.get('transport')!r}; "
                "refusing transport mixing with 'mcp-app'"
            ) from None
        if existing and existing.get("packet_sha256") == manifest["archive_sha256"]:
            return submission_path, False
        raise
    _atomic_write(
        round_dir / "state.json",
        _state_bytes(
            status="submitted-waiting-response",
            stage=stage,
            round_number=round_number,
            packet_sha256=manifest["archive_sha256"],
            next_action="Resume the same MCP workspace and wait for one complete Pro response.",
        ),
    )
    return submission_path, created


def _response_verdict(text: str) -> str:
    match = re.match(
        r"\ufeff?[ \t]*Verdict:[ \t]*(SIGNED OFF|BLOCKED)[ \t]*(?:\r?\n|$)", text
    )
    if not match:
        raise LedgerError("Pro response must begin with Verdict: SIGNED OFF or Verdict: BLOCKED")
    return match.group(1)


def _validated_response_verdict(text: str) -> str:
    verdict = _response_verdict(text)
    heading_pattern = re.compile(
        r"(?m)^(Required changes|Risks|Tests or verification|Reasoning notes):[ \t]*$"
    )
    matches = list(heading_pattern.finditer(text))
    headings = tuple(match.group(1) for match in matches)
    if headings != RESPONSE_SECTIONS:
        raise LedgerError(
            "Pro response must contain exactly these sections in order: "
            + "; ".join(RESPONSE_SECTIONS)
        )
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        if not text[match.end() : end].strip():
            raise LedgerError(f"Pro response section {match.group(1)!r} must not be empty")
    return verdict


def _mcp_receipt_path(round_dir: Path, member_path: str) -> Path:
    name = _sha(member_path.encode("utf-8")) + ".json"
    return round_dir / MCP_READ_RECEIPTS_ROOT / name


def record_mcp_member_read(
    round_dir: Path,
    *,
    packet_sha256: str,
    member_path: str,
    member_sha256: str,
) -> Path:
    """Record one deterministic, packet-bound MCP member read receipt."""
    manifest = _load_manifest(round_dir)
    if manifest.get("archive_sha256") != packet_sha256:
        raise LedgerError("MCP read receipt packet hash does not match the prepared manifest")
    declared = {
        item.get("path"): item
        for item in manifest.get("zip_members", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    expected = declared.get(member_path)
    if expected is None or expected.get("sha256") != member_sha256:
        raise LedgerError("MCP read receipt does not match a declared packet member")
    receipt = {
        "schema_version": 1,
        "packet_sha256": packet_sha256,
        "member_path": member_path,
        "member_sha256": member_sha256,
    }
    path = _mcp_receipt_path(round_dir, member_path)
    _write_immutable(path, _canonical_json(receipt))
    return path


def mcp_read_receipt_problems(round_dir: Path, manifest: Mapping[str, Any]) -> list[str]:
    declared = manifest.get("zip_members")
    if not isinstance(declared, list):
        return ["Pro packet manifest zip_members must be a list before MCP read validation"]
    expected: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    for item in declared:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            problems.append("Pro packet manifest contains an invalid MCP-readable member")
            continue
        expected[item["path"]] = item
    receipt_root = round_dir / MCP_READ_RECEIPTS_ROOT
    expected_files = {_mcp_receipt_path(round_dir, path) for path in expected}
    actual_files = set(receipt_root.glob("*.json")) if receipt_root.is_dir() else set()
    if actual_files - expected_files:
        problems.append("MCP packet read receipts contain an unknown member receipt")
    for member_path, item in expected.items():
        receipt_path = _mcp_receipt_path(round_dir, member_path)
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            problems.append(f"MCP Pro review did not read packet member: {member_path}")
            continue
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"invalid MCP read receipt for {member_path}: {exc}")
            continue
        expected_receipt = {
            "schema_version": 1,
            "packet_sha256": manifest.get("archive_sha256"),
            "member_path": member_path,
            "member_sha256": item.get("sha256"),
        }
        if receipt != expected_receipt:
            problems.append(f"MCP read receipt does not match packet member: {member_path}")
    return problems


def mcp_read_progress(round_dir: Path) -> dict[str, Any]:
    manifest = _load_manifest(round_dir)
    declared = manifest.get("zip_members", [])
    member_paths = [
        item["path"]
        for item in declared
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    ]
    read = [path for path in member_paths if _mcp_receipt_path(round_dir, path).is_file()]
    return {
        "read": len(read),
        "total": len(member_paths),
        "missing": [path for path in member_paths if path not in read],
    }


def record_response_bytes(
    goal_dir: Path,
    *,
    stage: str,
    round_number: int,
    raw: bytes,
) -> tuple[Path, str]:
    """Record one immutable UTF-8 Pro response from any authorized transport."""
    goal_dir, goal = _load_selected(goal_dir)
    _validate_review_selection(goal, stage, round_number)
    round_dir = _review_dir(goal_dir, stage, round_number)
    submission_path = round_dir / "submission.json"
    if not submission_path.is_file():
        raise LedgerError("record the actual Pro submission before recording its response")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LedgerError("Pro response must be UTF-8 text") from exc
    verdict = _validated_response_verdict(text)
    try:
        submission = json.loads(submission_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LedgerError(f"invalid Pro submission custody: {submission_path}: {exc}") from exc
    if not isinstance(submission, dict):
        raise LedgerError("Pro submission custody must be a JSON object")
    manifest = _load_manifest(round_dir)
    if submission.get("transport") == "mcp-app":
        receipt_problems = mcp_read_receipt_problems(round_dir, manifest)
        if receipt_problems:
            raise LedgerError("; ".join(receipt_problems))
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


def record_response(
    goal_dir: Path,
    *,
    stage: str,
    round_number: int,
    response_file: Path,
) -> tuple[Path, str]:
    return record_response_bytes(
        goal_dir,
        stage=stage,
        round_number=round_number,
        raw=response_file.expanduser().read_bytes(),
    )


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
    verdict = _validated_response_verdict(response.decode("utf-8"))
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
                candidate not in EVIDENCE_TRANSPORTS for candidate in candidates
            ):
                problems.append("Pro delivery plan has invalid candidates")
            elif "native-chat" in candidates:
                native_handoff = round_dir / "native-chat-handoff.md"
                if not native_handoff.is_file():
                    problems.append("missing Pro review artifact: native-chat-handoff.md")
                elif manifest is not None and str(
                    manifest.get("archive_sha256", "")
                ) not in native_handoff.read_text(encoding="utf-8"):
                    problems.append(
                        "native Chat handoff does not name the prepared packet hash"
                    )

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
                    if (
                        surface not in ROUTED_SURFACES + LEGACY_EVIDENCE_TRANSPORTS
                        or surface in seen
                    ):
                        problems.append("Pro transport attempts contain an invalid or duplicate surface")
                    seen.add(str(surface))
                    if item.get("result") not in TRANSPORT_RESULTS:
                        problems.append("Pro transport attempt has an invalid result")

    submission = _json_object(round_dir / "submission.json", problems) if require_closed or (round_dir / "submission.json").exists() else None
    if submission is not None and manifest is not None:
        if submission.get("packet_sha256") != manifest.get("archive_sha256"):
            problems.append("Pro submission packet hash does not match manifest")
        if submission.get("transport") not in EVIDENCE_TRANSPORTS:
            problems.append("Pro submission has an invalid transport")
        is_mcp_claim = (
            submission.get("transport") == "mcp-app"
            and submission.get("submission_kind") == "mcp-workspace-claim"
        )
        if is_mcp_claim:
            if submission.get("model_visible") is not None or submission.get("thread") is not None:
                problems.append("MCP workspace claim must not invent model or thread evidence")
        else:
            if "pro" not in str(submission.get("model_visible", "")).casefold():
                problems.append("Pro submission does not record a visible Pro model")
            if not str(submission.get("thread", "")).strip():
                problems.append("Pro submission does not record a visible thread reference")

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
            verdict = _validated_response_verdict(response.decode("utf-8"))
        except (UnicodeDecodeError, LedgerError) as exc:
            problems.append(f"invalid raw Pro response: {exc}")
        if response_metadata is not None:
            if response_metadata.get("sha256") != _sha(response):
                problems.append("Pro response metadata hash does not match raw response")
            if response_metadata.get("bytes") != len(response):
                problems.append("Pro response metadata byte count does not match raw response")
            if verdict and response_metadata.get("verdict") != verdict:
                problems.append("Pro response metadata verdict does not match raw response")
    if (
        submission is not None
        and submission.get("transport") == "mcp-app"
        and manifest is not None
        and (require_closed or response is not None)
    ):
        problems.extend(mcp_read_receipt_problems(round_dir, manifest))

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
    attempt.add_argument("--surface", choices=ROUTED_SURFACES, required=True)
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
