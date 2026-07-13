#!/usr/bin/env python3
"""Initialize a durable Codex Goal Ledger without replacing existing artifacts."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sys

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


def _valid_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD")
    return value


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
    parser.add_argument("--planning-profile", default="current available runtime")
    parser.add_argument("--implementation-profile", default="current available runtime")
    parser.add_argument("--review-profile", default="current available runtime")
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
    planning = _single_line("planning profile", args.planning_profile, forbid_pipe=True)
    implementation = _single_line(
        "implementation profile", args.implementation_profile, forbid_pipe=True
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
        "PLANNING_PROFILE": planning,
        "IMPLEMENTATION_PROFILE": implementation,
        "REVIEW_PROFILE": review,
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
