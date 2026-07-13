#!/usr/bin/env python3
"""Generate selected closeout prompts from a goal's canonical choices."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Mapping

from ledger_common import (
    Document,
    LedgerError,
    escape_markdown_text,
    get_section,
    load_document,
    parse_table,
    project_root_for,
    replace_template,
)


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = PACKAGE_ROOT / "assets" / "templates"

CLOSEOUT_SECTION = "Closeout options"
CLOSEOUT_HEADERS = ("Option", "Choice", "Artifact or action")
EXTERNAL_REVIEW_OPTION = "External LLM review prompt"
CODEX_REVIEW_OPTION = "Additional Codex review"
CLEAN_HANDOFF_OPTION = "Clean-session handoff prompt"
CLOSEOUT_OPTION_LABELS = (
    EXTERNAL_REVIEW_OPTION,
    CODEX_REVIEW_OPTION,
    CLEAN_HANDOFF_OPTION,
)
VALID_CLOSEOUT_CHOICES = frozenset({"ask", "yes", "no"})

PROMPT_ARTIFACTS = {
    EXTERNAL_REVIEW_OPTION: ("review-prompt.md", "review-prompt.md"),
    CLEAN_HANDOFF_OPTION: ("handoff-prompt.md", "handoff-prompt.md"),
}


@dataclass(frozen=True)
class PromptSyncResult:
    """Observable result of synchronizing generated prompt artifacts."""

    choices: Mapping[str, str]
    changed: tuple[Path, ...]
    removed: tuple[Path, ...]
    problems: tuple[str, ...]


def parse_closeout_options(goal: Document) -> dict[str, str]:
    """Parse and strictly validate the canonical closeout-options table."""
    markdown = get_section(goal, CLOSEOUT_SECTION).strip()
    if not markdown:
        raise LedgerError(f"{goal.path}: missing or empty section: {CLOSEOUT_SECTION}")

    headers, rows = parse_table(markdown)
    if tuple(headers) != CLOSEOUT_HEADERS:
        raise LedgerError(
            f"{goal.path}: {CLOSEOUT_SECTION} table headers must be exactly "
            + " | ".join(CLOSEOUT_HEADERS)
        )

    for number, row in enumerate(rows, 1):
        if len(row) != len(CLOSEOUT_HEADERS):
            raise LedgerError(
                f"{goal.path}: {CLOSEOUT_SECTION} row {number} must have exactly "
                f"{len(CLOSEOUT_HEADERS)} cells; found {len(row)}"
            )

    labels = tuple(row[0].strip() for row in rows)
    if labels != CLOSEOUT_OPTION_LABELS:
        raise LedgerError(
            f"{goal.path}: {CLOSEOUT_SECTION} rows must be exactly, in order: "
            + "; ".join(CLOSEOUT_OPTION_LABELS)
        )

    choices: dict[str, str] = {}
    for label, row in zip(CLOSEOUT_OPTION_LABELS, rows, strict=True):
        raw_choice = row[1].strip()
        choice = raw_choice.casefold()
        if raw_choice != choice or choice not in VALID_CLOSEOUT_CHOICES:
            allowed = ", ".join(sorted(VALID_CLOSEOUT_CHOICES))
            raise LedgerError(
                f"{goal.path}: {label} choice must be one of {allowed}; found {raw_choice!r}"
            )
        choices[label] = choice
    return choices


def load_closeout_options(goal_dir: Path) -> tuple[Document, dict[str, str]]:
    """Load goal.md and return its validated closeout choices."""
    goal_dir = goal_dir.resolve()
    project_root_for(goal_dir)
    goal = load_document(goal_dir / "goal.md")
    return goal, parse_closeout_options(goal)


def _prompt_values(goal_dir: Path, goal: Document) -> dict[str, str]:
    project_root = project_root_for(goal_dir)

    def relative(path: Path) -> str:
        return path.resolve().relative_to(project_root).as_posix()

    title = goal.metadata.get("title", "").strip()
    slug = goal.metadata.get("slug", "").strip()
    if not title:
        raise LedgerError(f"{goal.path}: missing required frontmatter field: title")
    if not slug:
        raise LedgerError(f"{goal.path}: missing required frontmatter field: slug")
    if slug != goal_dir.name:
        raise LedgerError(
            f"{goal.path}: slug {slug!r} does not match goal directory {goal_dir.name!r}"
        )

    return {
        "TITLE_MD": escape_markdown_text(title),
        "GOAL_PATH": relative(goal_dir / "goal.md"),
        "PROGRESS_PATH": relative(goal_dir / "progress.md"),
        "DASHBOARD_PATH": relative(goal_dir / "index.html"),
    }


def build_closeout_prompt_artifacts(
    goal_dir: Path,
    *,
    goal: Document | None = None,
    choices: Mapping[str, str] | None = None,
) -> dict[Path, bytes]:
    """Build exact selected prompt bytes without mutating the filesystem."""
    goal_dir = goal_dir.resolve()
    project_root_for(goal_dir)
    if goal is None:
        goal = load_document(goal_dir / "goal.md")
    parsed = parse_closeout_options(goal)
    if choices is not None and dict(choices) != parsed:
        raise LedgerError("supplied closeout choices do not match the canonical goal contract")
    choices = parsed

    values = _prompt_values(goal_dir, goal)
    artifacts: dict[Path, bytes] = {}
    for option, (artifact_name, template_name) in PROMPT_ARTIFACTS.items():
        if choices[option] != "yes":
            continue
        template_path = TEMPLATE_ROOT / template_name
        try:
            template = template_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise LedgerError(f"missing shipped template: {template_path}") from exc
        rendered = replace_template(template, values)
        if not rendered.endswith("\n"):
            rendered += "\n"
        artifacts[goal_dir / artifact_name] = rendered.encode("utf-8")
    return artifacts


def closeout_prompt_problems(
    goal_dir: Path,
    *,
    goal: Document | None = None,
) -> list[str]:
    """Return exact-byte or selection drift for managed closeout prompts."""
    goal_dir = goal_dir.resolve()
    expected = build_closeout_prompt_artifacts(goal_dir, goal=goal)
    problems: list[str] = []
    for _, (artifact_name, _) in PROMPT_ARTIFACTS.items():
        path = goal_dir / artifact_name
        if path in expected:
            if not path.is_file():
                problems.append(f"missing selected closeout prompt: {artifact_name}")
            elif path.read_bytes() != expected[path]:
                problems.append(f"stale selected closeout prompt: {artifact_name}")
        elif path.exists():
            problems.append(f"unselected closeout prompt must be absent: {artifact_name}")
    return problems


def sync_closeout_prompts(goal_dir: Path, *, check: bool = False) -> PromptSyncResult:
    """Synchronize selected prompt artifacts, or report drift without mutation."""
    goal_dir = goal_dir.resolve()
    goal, choices = load_closeout_options(goal_dir)
    expected = build_closeout_prompt_artifacts(goal_dir, goal=goal, choices=choices)
    problems = tuple(closeout_prompt_problems(goal_dir, goal=goal))
    if check:
        return PromptSyncResult(choices, (), (), problems)

    changed: list[Path] = []
    removed: list[Path] = []
    for _, (artifact_name, _) in PROMPT_ARTIFACTS.items():
        path = goal_dir / artifact_name
        data = expected.get(path)
        if data is not None:
            if not path.is_file() or path.read_bytes() != data:
                path.write_bytes(data)
                changed.append(path)
        elif path.exists() and not path.is_file():
            raise LedgerError(f"managed closeout artifact is not a regular file: {path}")

    remaining = tuple(closeout_prompt_problems(goal_dir, goal=goal))
    return PromptSyncResult(choices, tuple(changed), tuple(removed), remaining)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate selected review and handoff prompts from goal.md."
    )
    parser.add_argument("goal_dir", type=Path, help="Canonical docs/goals/<slug> directory.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check exact selected prompt bytes and absence without modifying files.",
    )
    return parser.parse_args(argv)


def _display(path: Path, goal_dir: Path) -> str:
    return path.resolve().relative_to(project_root_for(goal_dir)).as_posix()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = sync_closeout_prompts(args.goal_dir, check=args.check)
    except (LedgerError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if result.problems:
        for problem in result.problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1

    if args.check:
        print("Closeout prompts are current.")
        return 0

    for path in result.changed:
        print(f"Wrote: {_display(path, args.goal_dir)}")
    if not result.changed and not result.removed:
        print("Closeout prompts already current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
