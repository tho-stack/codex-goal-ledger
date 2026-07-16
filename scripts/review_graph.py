#!/usr/bin/env python3
"""Derive dashboard review circuits and truthful progress tracks from ledger evidence."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Iterable, Mapping

from generate_closeout_prompts import (
    CODEX_REVIEW_OPTION,
    FABLE_FEEDBACK_OPTION,
    PRO_REVIEW_OPTION,
    parse_closeout_options,
)
from ledger_common import Document, normalize_state, strip_markdown
from run_fable_feedback import fable_artifact, fable_review_rounds, load_fable_artifact
from run_pro_review import configured_reviews


@dataclass(frozen=True)
class ReviewNode:
    key: str
    label: str
    detail: str
    state: str
    href: str | None = None
    current: bool = False


@dataclass(frozen=True)
class ReviewEdge:
    label: str
    state: str = "pending"
    direction: str = "forward"


@dataclass(frozen=True)
class ReviewLane:
    key: str
    label: str
    nodes: tuple[ReviewNode, ...]
    edges: tuple[ReviewEdge, ...]


@dataclass(frozen=True)
class ProgressTrack:
    key: str
    label: str
    resolved: int
    total: int
    summary: str
    kind: str = "ratio"


def _safe_json(path: Path) -> Mapping[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _verification_map(rows: Iterable[list[str]]) -> dict[str, str]:
    return {
        strip_markdown(row[0]).strip(): normalize_state(strip_markdown(row[1]))
        for row in rows
        if len(row) > 1
    }


def _phase_map(rows: Iterable[list[str]]) -> dict[str, str]:
    return {
        normalize_state(strip_markdown(row[0])): normalize_state(strip_markdown(row[1]))
        for row in rows
        if len(row) > 1
    }


def _resolved(state: str) -> bool:
    return normalize_state(state) in {"pass", "complete", "completed", "skipped", "signed-off"}


def _edge_for_state(state: str) -> ReviewEdge:
    if state in {"blocked", "revise", "reconciled-blocked"}:
        return ReviewEdge("return for revision", "blocked", "return")
    if state in {"pass", "ready", "reconciled-signed-off", "complete"}:
        return ReviewEdge("advance", "pass", "forward")
    return ReviewEdge("not yet run", "pending", "forward")


def _fable_nodes(goal_dir: Path, goal: Document, selected: bool) -> list[ReviewNode]:
    if not selected:
        return []
    nodes: list[ReviewNode] = []
    round_count = fable_review_rounds(goal)
    for number in range(1, round_count + 1):
        relative = fable_artifact(number)
        path = goal_dir / relative
        state = "pending"
        detail = f"Planning peer round {number} of {round_count}"
        try:
            payload = load_fable_artifact(
                path, expected_round=number, expected_round_count=round_count
            )
        except Exception:
            href = None
        else:
            verdict = str(payload.get("verdict", "")).upper()
            state = "ready" if verdict == "READY" else "revise"
            detail = f"Fable verdict: {verdict.title()}"
            href = relative.as_posix()
        nodes.append(ReviewNode(f"fable-{number}", f"Fable R{number}", detail, state, href))
    return nodes


def _pro_nodes(goal_dir: Path, goal: Document, selected: bool, stage: str) -> list[ReviewNode]:
    if not selected:
        return []
    nodes: list[ReviewNode] = []
    for configured_stage, number in configured_reviews(goal):
        if configured_stage != stage:
            continue
        relative = Path("evidence/pro-review") / stage / f"round-{number:03d}"
        state_value = _safe_json(goal_dir / relative / "state.json")
        status = str(state_value.get("status", "pending")) if state_value else "pending"
        verdict = str(state_value.get("verdict", "")) if state_value else ""
        state = {
            "reconciled-signed-off": "pass",
            "reconciled-blocked": "blocked",
            "response-received": "active",
            "submitted-waiting-response": "active",
            "ui-ready": "active",
            "manual-handoff-ready": "active",
            "packet-ready": "pending",
        }.get(status, "pending")
        detail = verdict.title() if verdict else status.replace("-", " ").title()
        href_path = relative / (
            "reconciliation.md"
            if (goal_dir / relative / "reconciliation.md").is_file()
            else "request.md"
        )
        href = href_path.as_posix() if (goal_dir / href_path).is_file() else None
        nodes.append(ReviewNode(f"pro-{stage}-{number}", f"GPT Pro R{number}", detail, state, href))
    return nodes


def _rescue_nodes(goal_dir: Path) -> list[ReviewNode]:
    root = goal_dir / "evidence/fable-rescue"
    if not root.is_dir():
        return []
    nodes: list[ReviewNode] = []
    for incident in sorted(root.glob("rescue-[0-9][0-9][0-9]")):
        number = incident.name.rsplit("-", 1)[-1].lstrip("0") or "0"
        relative = incident.relative_to(goal_dir)
        if (incident / "outcome.json").is_file():
            state, detail, href = "complete", "Outcome recorded", relative / "outcome.json"
        elif (incident / "reconciliation.json").is_file():
            state, detail, href = "active", "Experiment pending", relative / "reconciliation.json"
        elif (incident / "response.json").is_file():
            state, detail, href = "active", "Response awaiting reconciliation", relative / "response.json"
        else:
            state, detail, href = "pending", "Qualified incident prepared", relative / "request.json"
        nodes.append(ReviewNode(f"rescue-{number}", f"Fable rescue {number}", detail, state, href.as_posix()))
    return nodes


def _sequence_edges(nodes: list[ReviewNode]) -> tuple[ReviewEdge, ...]:
    return tuple(_edge_for_state(node.state) for node in nodes[:-1])


def _mark_current(nodes: list[ReviewNode], key: str | None) -> list[ReviewNode]:
    return [replace(node, current=node.key == key) for node in nodes]


def _fable_reconciled(goal_dir: Path, node: ReviewNode) -> bool:
    try:
        number = int(node.key.rsplit("-", 1)[-1])
    except ValueError:
        return False
    return (goal_dir / "evidence" / f"fable-round-{number}-reconciliation.md").is_file()


def _planning_current_key(
    goal_dir: Path,
    *,
    fable_selected: bool,
    fable_nodes: list[ReviewNode],
    fable_verification: str,
    pro_nodes: list[ReviewNode],
    define_phase: str,
    build_phase: str,
) -> str | None:
    if fable_selected and not _resolved(fable_verification):
        unreconciled = [
            node
            for node in fable_nodes
            if node.state != "pending" and not _fable_reconciled(goal_dir, node)
        ]
        if unreconciled:
            return unreconciled[-1].key
        pending = next((node for node in fable_nodes if node.state == "pending"), None)
        if pending is not None:
            return pending.key

    active_pro = next((node for node in reversed(pro_nodes) if node.state == "active"), None)
    if active_pro is not None:
        return active_pro.key
    pending_pro = next((node for node in pro_nodes if node.state == "pending"), None)
    if pending_pro is not None:
        return pending_pro.key
    if define_phase == "active":
        return "define-gate"
    if build_phase == "active":
        return "build"
    return None


def build_review_lanes(
    goal_dir: Path,
    goal: Document,
    phase_rows: Iterable[list[str]],
    verification_rows: Iterable[list[str]],
) -> tuple[ReviewLane, ...]:
    choices = parse_closeout_options(goal)
    fable_selected = choices.get(FABLE_FEEDBACK_OPTION) == "yes"
    pro_selected = choices.get(PRO_REVIEW_OPTION) == "yes"
    codex_selected = choices.get(CODEX_REVIEW_OPTION) == "yes"
    verification = _verification_map(verification_rows)
    phases = _phase_map(phase_rows)
    define_phase = phases.get("define", "pending")
    build_phase = phases.get("build", "pending")

    planning = [ReviewNode("plan", "Plan", "Canonical contract", "complete", "#source")]
    fable = _fable_nodes(goal_dir, goal, fable_selected)
    pro_plan = _pro_nodes(goal_dir, goal, pro_selected, "plan")
    planning.extend(fable)
    planning.extend(pro_plan)
    planning_current = _planning_current_key(
        goal_dir,
        fable_selected=fable_selected,
        fable_nodes=fable,
        fable_verification=verification.get(FABLE_FEEDBACK_OPTION, "pending"),
        pro_nodes=pro_plan,
        define_phase=define_phase,
        build_phase=build_phase,
    )
    if planning_current == "define-gate":
        planning.append(ReviewNode("define-gate", "Define gate", "Current focus", "active", "#briefing"))
    planning.append(
        ReviewNode(
            "build",
            "Build",
            "Implementation gate",
            "active" if build_phase == "active" else "pending",
            "#activity",
        )
    )
    planning = _mark_current(planning, planning_current)

    rescue = [ReviewNode("build-rescue", "Build", "Scientific work", build_phase, "#activity")]
    rescue.extend(_rescue_nodes(goal_dir))
    rescue.append(ReviewNode("experiment", "Experiment", "Prediction-bound outcome", "pending", "#activity"))
    rescue.append(ReviewNode("return-build", "Return to build", "Apply verified learning", "pending", "#activity"))

    closeout = [ReviewNode("verify", "Verify", "Evidence gate", "pending", "#activity")]
    closeout.extend(_pro_nodes(goal_dir, goal, pro_selected, "implementation"))
    if codex_selected:
        codex_state = verification.get("Additional Codex review", "pending")
        closeout.append(
            ReviewNode(
                "codex-review",
                "Codex review",
                "Independent closeout review",
                "pass" if _resolved(codex_state) else codex_state,
                "#session-kit",
            )
        )
    closeout.append(ReviewNode("close", "Close", "Completion bar", "pending", "#source"))

    return (
        ReviewLane("planning", "Planning circuit", tuple(planning), _sequence_edges(planning)),
        ReviewLane("rescue", "Scientific rescue", tuple(rescue), _sequence_edges(rescue)),
        ReviewLane("closeout", "Verification circuit", tuple(closeout), _sequence_edges(closeout)),
    )


def progress_tracks(
    goal: Document,
    phase_rows: Iterable[list[str]],
    verification_rows: Iterable[list[str]],
    gate_count: int,
    lanes: Iterable[ReviewLane],
) -> tuple[ProgressTrack, ...]:
    phases = list(phase_rows)
    checks = list(verification_rows)
    phase_resolved = sum(
        1 for row in phases if len(row) > 1 and normalize_state(strip_markdown(row[1])) in {"complete", "skipped"}
    )
    evidence_resolved = sum(
        1 for row in checks if len(row) > 1 and _resolved(strip_markdown(row[1]))
    )
    choices = parse_closeout_options(goal)
    selected_options = {
        FABLE_FEEDBACK_OPTION,
        PRO_REVIEW_OPTION,
        CODEX_REVIEW_OPTION,
    }
    selected = sum(1 for name in selected_options if choices.get(name) == "yes")
    reconciled = 0
    lane_nodes = [node for lane in lanes for node in lane.nodes]
    if choices.get(FABLE_FEEDBACK_OPTION) == "yes":
        fable = [node for node in lane_nodes if node.key.startswith("fable-")]
        reconciled += int(bool(fable) and fable[-1].state == "ready")
    if choices.get(PRO_REVIEW_OPTION) == "yes":
        pro = [node for node in lane_nodes if node.key.startswith("pro-")]
        latest_by_stage: dict[str, ReviewNode] = {}
        for node in pro:
            parts = node.key.split("-")
            if len(parts) >= 3:
                latest_by_stage[parts[1]] = node
        reconciled += int(
            bool(latest_by_stage)
            and all(node.state == "pass" for node in latest_by_stage.values())
        )
    if choices.get(CODEX_REVIEW_OPTION) == "yes":
        codex = next((node for node in lane_nodes if node.key == "codex-review"), None)
        reconciled += int(codex is not None and codex.state == "pass")
    return (
        ProgressTrack("run", "Run", phase_resolved, len(phases), f"{phase_resolved} / {len(phases)} phases resolved"),
        ProgressTrack("evidence", "Evidence", evidence_resolved, len(checks), f"{evidence_resolved} / {len(checks)} checks passed"),
        ProgressTrack("reviews", "Reviews", reconciled, selected, f"{reconciled} / {selected} selected lanes reconciled"),
        ProgressTrack("gates", "Gates", 0 if gate_count else 1, 1, f"{gate_count} open", "gate"),
    )
