#!/usr/bin/env python3
"""Initialize a durable Codex Goal Ledger without replacing existing artifacts."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sys

from agent_profiles import DEFAULT_IMPLEMENTER, IMPLEMENTER_BY_NAME, IMPLEMENTER_NAMES
from ledger_common import (
    LedgerError,
    code_fences_balanced,
    escape_markdown_text,
    replace_template,
    slugify,
)
from render_goal import ASSET_ROOT, SHARED_ASSETS, build_dashboard


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = PACKAGE_ROOT / "assets" / "templates"
DEFAULT_CRITERIA = (
    "The stated outcome exists at stable project paths and is directly inspectable.",
    "Required validation checks pass and their evidence is recorded in `progress.md`.",
    "Canonical Markdown and the generated dashboard carry the same current digest.",
)
DEFAULT_PLANNING_INPUT_ASSESSMENT = (
    "- **Required before execution:** None.\n"
    "- **Optional, improves result:** No additional information would materially improve this plan."
)
MAX_FABLE_ROUNDS = 10
MAX_PRO_ROUNDS = 3


def _valid_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD")
    return value


def _fable_rounds(value: str) -> int:
    try:
        rounds = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Fable review rounds must be an integer from 1 to 10") from exc
    if not 1 <= rounds <= MAX_FABLE_ROUNDS or str(rounds) != value:
        raise argparse.ArgumentTypeError("Fable review rounds must be an integer from 1 to 10")
    return rounds


def _rescue_incidents(value: str) -> int:
    try:
        incidents = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Fable rescue incidents must be an integer from 1 to 10") from exc
    if not 1 <= incidents <= 10 or str(incidents) != value:
        raise argparse.ArgumentTypeError("Fable rescue incidents must be an integer from 1 to 10")
    return incidents


def _rescue_rounds(value: str) -> int:
    try:
        rounds = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Fable rescue rounds per incident must be 1") from exc
    if rounds != 1 or str(rounds) != value:
        raise argparse.ArgumentTypeError(
            "Fable rescue rounds per incident must be 1; use a delta-gated second incident"
        )
    return rounds


def _pro_rounds(value: str) -> int:
    try:
        rounds = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("GPT Pro review rounds must be an integer from 1 to 3") from exc
    if not 1 <= rounds <= MAX_PRO_ROUNDS or str(rounds) != value:
        raise argparse.ArgumentTypeError("GPT Pro review rounds must be an integer from 1 to 3")
    return rounds


def _single_line(name: str, value: str, *, forbid_pipe: bool = False) -> str:
    value = value.strip()
    if not value:
        raise LedgerError(f"{name} must not be empty")
    if "\n" in value or "\r" in value:
        raise LedgerError(f"{name} must be a single line")
    if forbid_pipe and "|" in value:
        raise LedgerError(f"{name} must not contain a table separator (|)")
    return value


def _markdown_block(name: str, value: str) -> str:
    """Accept narrative Markdown without allowing it to replace template structure."""
    value = value.strip()
    if not value:
        raise LedgerError(f"{name} must not be empty")
    if re.search(r"^\s*#{1,2}\s+", value, flags=re.MULTILINE):
        raise LedgerError(
            f"{name} must not contain level-one or level-two headings; "
            "the ledger template owns those headings"
        )
    if not code_fences_balanced(value):
        raise LedgerError(f"{name} contains an unbalanced fenced code block")
    return value


def _write_new(path: Path, data: bytes) -> bool:
    """Create path exclusively; return False when another artifact already owns it."""
    try:
        with path.open("xb") as stream:
            stream.write(data)
        return True
    except FileExistsError:
        return False


def _read_template(name: str) -> str:
    path = TEMPLATE_ROOT / name
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise LedgerError(f"missing shipped template: {path}") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create docs/goals/<slug> and shared ledger assets without overwriting files."
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--why", required=True)
    parser.add_argument("--outcome", required=True)
    parser.add_argument(
        "--success-criterion",
        action="append",
        default=[],
        help="Observable completion criterion; repeat for multiple criteria.",
    )
    parser.add_argument("--mode", default="overnight-capable")
    parser.add_argument(
        "--planning-input-assessment",
        default=DEFAULT_PLANNING_INPUT_ASSESSMENT,
        help=(
            "Planning assessment Markdown recorded after bounded discovery; include required "
            "inputs and at most three optional inputs with benefit and default."
        ),
    )
    parser.add_argument("--planning-profile", default="gpt-5.6-sol xhigh")
    parser.add_argument(
        "--implementation-agent",
        choices=IMPLEMENTER_NAMES,
        default=DEFAULT_IMPLEMENTER.name,
        help="Owned implementation-agent preset recorded in the execution contract.",
    )
    parser.add_argument(
        "--implementation-profile",
        default=None,
        help="Requested implementation model and effort; defaults to the selected agent preset.",
    )
    parser.add_argument(
        "--swarm-implementer",
        action="append",
        choices=IMPLEMENTER_NAMES,
        default=[],
        help=(
            "Additional owned implementation preset for an independently partitioned mixed "
            "swarm; repeat as needed."
        ),
    )
    parser.add_argument("--fable-profile", default="claude-fable-5 high")
    parser.add_argument("--review-profile", default="gpt-5.6-sol xhigh")
    parser.add_argument(
        "--fable-feedback",
        choices=("ask", "yes", "no"),
        default="ask",
        help="Whether planning should request read-only Claude Fable feedback (default: ask).",
    )
    parser.add_argument(
        "--fable-review-rounds",
        type=_fable_rounds,
        default=1,
        help="Number of sequential Fable review rounds selected by a yes choice (1-10).",
    )
    parser.add_argument(
        "--fable-rescue",
        choices=("ask", "yes", "no"),
        default="ask",
        help="Whether hard scientific impasses may use bounded Fable rescue (default: ask).",
    )
    parser.add_argument(
        "--fable-rescue-max-incidents",
        type=_rescue_incidents,
        default=2,
        help="Maximum rescue incidents shared by a goal lineage (default: 2).",
    )
    parser.add_argument(
        "--fable-rescue-rounds-per-incident",
        type=_rescue_rounds,
        default=1,
        help="Rescue rounds per incident (fixed at 1; use a delta-gated second incident).",
    )
    parser.add_argument(
        "--fable-rescue-effort",
        choices=("high", "xhigh"),
        default="xhigh",
    )
    parser.add_argument(
        "--fable-rescue-lineage",
        default=None,
        help="Shared incident-budget lineage; defaults to the goal slug.",
    )
    parser.add_argument(
        "--pro-review",
        choices=("ask", "yes", "no"),
        default="ask",
        help="Whether to run native GPT Pro review with a prompt plus scoped ZIP (default: ask).",
    )
    parser.add_argument(
        "--pro-review-rounds",
        type=_pro_rounds,
        default=1,
        help="Number of GPT Pro rounds for each selected stage (1-3).",
    )
    parser.add_argument(
        "--pro-review-stage",
        choices=("plan", "implementation", "both"),
        default="plan",
        help="Review the plan, implementation, or both (default: plan).",
    )
    parser.add_argument(
        "--pro-review-delivery",
        choices=(
            "auto-ui",
            "mcp-app",
            "native-chat",
            "safari-assisted",
            "chrome-assisted",
            "owner-handoff",
        ),
        default="auto-ui",
        help=(
            "Use MCP-first automatic routing, native ChatGPT Pro handoff, one explicit "
            "browser surface, or owner handoff (default: auto-ui)."
        ),
    )
    parser.add_argument(
        "--pro-review-gate",
        choices=("required", "advisory"),
        default="required",
        help="Whether signed-off reconciliation is a hard gate or advisory.",
    )
    parser.add_argument(
        "--external-review-prompt",
        choices=("ask", "yes", "no"),
        default="ask",
        help="Whether closeout should generate review-prompt.md (default: ask).",
    )
    parser.add_argument(
        "--codex-review",
        choices=("ask", "yes", "no"),
        default="ask",
        help="Whether closeout should run the optional Codex review contract (default: ask).",
    )
    parser.add_argument(
        "--clean-session-handoff",
        choices=("ask", "yes", "no"),
        default="ask",
        help="Whether closeout should generate handoff-prompt.md (default: ask).",
    )
    parser.add_argument(
        "--date",
        dest="ledger_date",
        type=_valid_date,
        default=datetime.now(timezone.utc).date().isoformat(),
        help="Ledger date in YYYY-MM-DD (defaults to the current UTC date).",
    )
    return parser.parse_args(argv)


def initialize(args: argparse.Namespace) -> tuple[Path, list[Path], list[Path]]:
    slug = args.slug.strip()
    if slug != slugify(slug) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise LedgerError("slug must be lowercase words or numbers separated by single hyphens")

    title = _single_line("title", args.title)
    why = _markdown_block("why", args.why)
    outcome = _markdown_block("outcome", args.outcome)

    mode = _single_line("mode", args.mode)
    planning_input_assessment = _markdown_block(
        "planning input assessment", args.planning_input_assessment
    )
    planning = _single_line("planning profile", args.planning_profile, forbid_pipe=True)
    implementation_agent = _single_line(
        "implementation agent", args.implementation_agent, forbid_pipe=True
    )
    implementation_value = (
        args.implementation_profile
        if args.implementation_profile is not None
        else IMPLEMENTER_BY_NAME[implementation_agent].requested_profile
    )
    implementation = _single_line(
        "implementation profile", implementation_value, forbid_pipe=True
    )
    swarm_names = tuple(
        dict.fromkeys(
            name for name in args.swarm_implementer if name != implementation_agent
        )
    )
    implementation_swarm = (
        ", ".join(
            f"`{name}` ({IMPLEMENTER_BY_NAME[name].requested_profile})"
            for name in swarm_names
        )
        if swarm_names
        else "none"
    )
    fable = _single_line("Fable profile", args.fable_profile, forbid_pipe=True)
    fable_rounds = args.fable_review_rounds
    fable_authorization = (
        f"{fable_rounds} sequential read-only Claude review round"
        + ("" if fable_rounds == 1 else "s")
    )
    pro_stage_label = {
        "plan": "planning",
        "implementation": "implementation",
        "both": "planning and implementation",
    }[args.pro_review_stage]
    pro_authorization = (
        f"{args.pro_review_rounds} native GPT Pro round"
        + ("" if args.pro_review_rounds == 1 else "s")
        + f" for {pro_stage_label}"
    )
    review = _single_line("review profile", args.review_profile, forbid_pipe=True)
    criteria = [
        _single_line("success criterion", criterion)
        for criterion in args.success_criterion
        if criterion.strip()
    ]
    if not criteria:
        criteria = list(DEFAULT_CRITERIA)
    criteria_markdown = "\n".join(f"- {criterion}" for criterion in criteria)

    project_root = args.project_root.expanduser().resolve()
    goal_dir = project_root / "docs" / "goals" / slug
    asset_dir = project_root / "docs" / "assets"
    evidence_dir = goal_dir / "evidence"
    goal_path = goal_dir / "goal.md"
    progress_path = goal_dir / "progress.md"
    index_path = goal_dir / "index.html"

    canonical_exists = {
        goal_path: goal_path.exists(),
        progress_path: progress_path.exists(),
        index_path: index_path.exists(),
    }
    if any(canonical_exists.values()) and not (
        canonical_exists[goal_path] and canonical_exists[progress_path]
    ):
        found = ", ".join(path.name for path, exists in canonical_exists.items() if exists)
        raise LedgerError(
            f"partial existing ledger ({found}); no files changed. "
            "Recover goal.md and progress.md together before initializing."
        )

    goal_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    values = {
        "TITLE": title,
        "TITLE_MD": escape_markdown_text(title),
        "TITLE_YAML": json.dumps(title, ensure_ascii=False),
        "SLUG": slug,
        "DATE": args.ledger_date,
        "MODE_YAML": json.dumps(mode, ensure_ascii=False),
        "WHY": why,
        "OUTCOME": outcome,
        "SUCCESS_CRITERIA": criteria_markdown,
        "PLANNING_INPUT_ASSESSMENT": planning_input_assessment,
        "PLANNING_PROFILE": planning,
        "IMPLEMENTATION_AGENT": implementation_agent,
        "IMPLEMENTATION_PROFILE": implementation,
        "IMPLEMENTATION_SWARM": implementation_swarm,
        "FABLE_PROFILE": fable,
        "FABLE_REVIEW_ROUNDS": str(fable_rounds),
        "FABLE_RESCUE_MAX_INCIDENTS": str(args.fable_rescue_max_incidents),
        "FABLE_RESCUE_ROUNDS": str(args.fable_rescue_rounds_per_incident),
        "FABLE_RESCUE_EFFORT": args.fable_rescue_effort,
        "FABLE_RESCUE_LINEAGE": _single_line(
            "Fable rescue lineage", args.fable_rescue_lineage or slug
        ),
        "PRO_REVIEW_ROUNDS": str(args.pro_review_rounds),
        "PRO_REVIEW_STAGE": args.pro_review_stage,
        "PRO_REVIEW_DELIVERY": args.pro_review_delivery,
        "PRO_REVIEW_GATE": args.pro_review_gate,
        "PRO_REVIEW_AUTHORIZATION": pro_authorization,
        "FABLE_AUTHORIZATION": fable_authorization,
        "REVIEW_PROFILE": review,
        "FABLE_FEEDBACK": args.fable_feedback,
        "FABLE_RESCUE": args.fable_rescue,
        "PRO_REVIEW": args.pro_review,
        "EXTERNAL_REVIEW_PROMPT": args.external_review_prompt,
        "CODEX_REVIEW": args.codex_review,
        "CLEAN_SESSION_HANDOFF": args.clean_session_handoff,
    }
    goal_bytes = (replace_template(_read_template("goal.md"), values).rstrip() + "\n").encode(
        "utf-8"
    )
    progress_bytes = (
        replace_template(_read_template("progress.md"), values).rstrip() + "\n"
    ).encode("utf-8")

    created: list[Path] = []
    preserved: list[Path] = []
    for path, data in (
        (goal_path, goal_bytes),
        (progress_path, progress_bytes),
    ):
        (created if _write_new(path, data) else preserved).append(path)

    drifted_assets: list[Path] = []
    for name in SHARED_ASSETS:
        source = ASSET_ROOT / name
        if not source.is_file():
            raise LedgerError(f"missing shipped asset: {source}")
        target = asset_dir / name
        if target.is_file() and target.read_bytes() != source.read_bytes():
            drifted_assets.append(target)
        (created if _write_new(target, source.read_bytes()) else preserved).append(target)

    if index_path.exists():
        preserved.append(index_path)
        expected = build_dashboard(goal_dir)
        if index_path.read_bytes() != expected:
            raise LedgerError(
                f"preserved stale dashboard: {index_path}. "
                "Run render_goal.py after reviewing the canonical Markdown."
            )
    else:
        dashboard = build_dashboard(goal_dir)
        (created if _write_new(index_path, dashboard) else preserved).append(index_path)

    if drifted_assets:
        paths = ", ".join(str(path) for path in drifted_assets)
        raise LedgerError(
            f"preserved shared assets differ from this skill: {paths}. "
            "Run render_goal.py --sync-assets after reviewing the changes."
        )

    return goal_dir, created, preserved


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        goal_dir, created, preserved = initialize(args)
        for path in created:
            print(f"Created: {path}")
        for path in preserved:
            print(f"Preserved: {path}")
        print(f"Goal ledger ready: {goal_dir}")
        return 0
    except (LedgerError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
