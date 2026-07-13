#!/usr/bin/env python3
"""Render a Codex Goal Ledger dashboard from its canonical Markdown."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import sys

from ledger_common import (
    Document,
    LedgerError,
    gate_items,
    get_section,
    inline_html,
    ledger_digest,
    load_document,
    markdown_to_html,
    normalize_key,
    normalize_state,
    parse_table,
    project_root_for,
    replace_template,
    state_label,
    strip_markdown,
    unique_in_order,
    without_first_h1,
)
from generate_closeout_prompts import (
    CLEAN_HANDOFF_OPTION,
    CODEX_REVIEW_OPTION,
    EXTERNAL_REVIEW_OPTION,
    build_closeout_prompt_artifacts,
    parse_closeout_options,
)


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
ASSET_ROOT = PACKAGE_ROOT / "assets"
TEMPLATE_PATH = ASSET_ROOT / "templates" / "index.html"
SHARED_ASSETS = ("goal-ledger.css", "goal-ledger.js")


def _metadata(document: Document, key: str) -> str:
    value = document.metadata.get(key, "").strip()
    if not value:
        raise LedgerError(f"{document.path}: missing required frontmatter field: {key}")
    return value


def _table_rows(document: Document, section: str) -> list[list[str]]:
    _, rows = parse_table(get_section(document, section))
    return rows


def _section_html(document: Document, section: str, fallback: str) -> str:
    markdown = get_section(document, section).strip()
    return markdown_to_html(markdown) if markdown else f"<p>{escape(fallback)}</p>"


def _source_html(document: Document) -> str:
    return markdown_to_html(without_first_h1(document.body), heading_shift=1)


def _asset_destination(goal_dir: Path) -> Path:
    return project_root_for(goal_dir) / "docs" / "assets"


def asset_status(goal_dir: Path, *, assume_synced: bool = False) -> str:
    """Return a short deterministic label describing shipped asset parity."""
    if assume_synced:
        return "Current"
    destination = _asset_destination(goal_dir)
    missing = False
    drifted = False
    for name in SHARED_ASSETS:
        source = ASSET_ROOT / name
        target = destination / name
        if not target.is_file():
            missing = True
        elif target.read_bytes() != source.read_bytes():
            drifted = True
    if missing:
        return "Assets missing"
    if drifted:
        return "Asset drift"
    return "Current"


def sync_assets(goal_dir: Path) -> list[Path]:
    """Copy the shipped CSS and JavaScript into the project's shared asset path."""
    destination = _asset_destination(goal_dir)
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in SHARED_ASSETS:
        source = ASSET_ROOT / name
        if not source.is_file():
            raise LedgerError(f"missing shipped asset: {source}")
        target = destination / name
        data = source.read_bytes()
        if not target.is_file() or target.read_bytes() != data:
            target.write_bytes(data)
            written.append(target)
    return written


def _phase_target(name: str) -> str:
    return {
        "discover": "source",
        "define": "briefing",
        "build": "activity",
        "verify": "activity",
        "close": "session-kit",
    }.get(normalize_key(name), "activity")


def _phase_rail(rows: list[list[str]]) -> tuple[str, int]:
    rendered: list[str] = []
    resolved = 0
    for row in rows:
        phase = row[0].strip() if row else "Unnamed phase"
        raw_state = row[1].strip() if len(row) > 1 else "unknown"
        state = normalize_state(strip_markdown(raw_state))
        if state in {"complete", "skipped"}:
            resolved += 1
        current = ' aria-current="step"' if state == "active" else ""
        rendered.append(
            f'<li data-state="{escape(state, quote=True)}">'
            f'<a href="#{_phase_target(phase)}"{current}>'
            f"<strong>{inline_html(phase)}</strong>"
            f"<span>{escape(state_label(state))}</span>"
            "</a></li>"
        )
    percentage = round((resolved / len(rows)) * 100) if rows else 0
    percentage = max(0, min(100, percentage))
    return "\n".join(rendered), percentage


def _activity_records(
    phase_rows: list[list[str]],
    decision_rows: list[list[str]],
    closeout_rows: list[list[str]],
    verification_rows: list[list[str]],
    custody_rows: list[list[str]],
) -> list[tuple[str, str, str, str]]:
    records: list[tuple[str, str, str, str]] = []

    for row in phase_rows:
        phase = row[0] if row else "Unnamed phase"
        state = row[1] if len(row) > 1 else "unknown"
        evidence = row[2] if len(row) > 2 else ""
        gate = row[3] if len(row) > 3 else ""
        detail = evidence
        if gate:
            detail = f"{evidence} **Next gate:** {gate}".strip()
        records.append(("Phase", phase, state, detail))

    for row in decision_rows:
        decision = row[0] if row else "Unnamed decision"
        why = row[1] if len(row) > 1 else ""
        state = row[2] if len(row) > 2 else "unknown"
        records.append(("Decision", decision, state, why))

    for row in closeout_rows:
        option = row[0] if row else "Unnamed closeout option"
        choice = normalize_key(strip_markdown(row[1])) if len(row) > 1 else "ask"
        artifact = row[2] if len(row) > 2 else ""
        state = {"yes": "accepted", "no": "skipped", "ask": "pending"}.get(
            choice, "pending"
        )
        records.append(("Closeout", option, state, f"**Choice:** {choice}. {artifact}"))

    for row in verification_rows:
        check = row[0] if row else "Unnamed check"
        result = row[1] if len(row) > 1 else "unknown"
        evidence = row[2] if len(row) > 2 else ""
        records.append(("Evidence", check, result, evidence))

    for row in custody_rows:
        item = row[0] if row else "Unnamed work item"
        owner = row[1] if len(row) > 1 else "unassigned"
        state = row[2] if len(row) > 2 else "unknown"
        recovery = row[3] if len(row) > 3 else ""
        detail = f"**Owner:** {owner}"
        if recovery:
            detail += f" **Recovery:** {recovery}"
        records.append(("Custody", item, state, detail))

    return records


def _closeout_kit_html(
    goal_dir: Path,
    goal: Document,
    verification_rows: list[list[str]],
) -> str:
    """Render the three planning choices and any current generated prompt text."""
    choices = parse_closeout_options(goal)
    expected = build_closeout_prompt_artifacts(goal_dir, goal=goal, choices=choices)
    verification = {
        strip_markdown(row[0]).strip(): normalize_state(strip_markdown(row[1]))
        for row in verification_rows
        if len(row) > 1
    }
    specs = (
        (
            EXTERNAL_REVIEW_OPTION,
            "K01",
            "Claude / other LLM",
            "Independent completion review",
            "A findings-first, read-only review brief grounded in the canonical ledger and repository evidence.",
            "review-prompt.md",
            "closeout-review-prompt",
        ),
        (
            CODEX_REVIEW_OPTION,
            "K02",
            "Codex closeout",
            "Additional Codex review",
            "An optional advisory code-review pass whose findings must be verified before any fix is accepted.",
            None,
            None,
        ),
        (
            CLEAN_HANDOFF_OPTION,
            "K03",
            "Fresh GPT context",
            "Clean-session handoff",
            "A compact restart brief that points a new session back to repository truth before it acts.",
            "handoff-prompt.md",
            "closeout-handoff-prompt",
        ),
    )
    rows: list[str] = []
    for option, index, eyebrow, title, description, artifact_name, target_id in specs:
        choice = choices[option]
        details = ""
        action = ""
        if choice == "ask":
            state = "pending"
            state_label_text = "Choice needed"
        elif choice == "no":
            state = "skipped"
            state_label_text = "Not requested"
        elif option == CODEX_REVIEW_OPTION:
            passed = verification.get(CODEX_REVIEW_OPTION) == "pass"
            state = "complete" if passed else "pending"
            state_label_text = "Complete" if passed else "Selected"
        else:
            artifact_path = goal_dir / str(artifact_name)
            expected_bytes = expected.get(artifact_path)
            ready = (
                expected_bytes is not None
                and artifact_path.is_file()
                and artifact_path.read_bytes() == expected_bytes
            )
            state = "complete" if ready else "pending"
            state_label_text = "Ready" if ready else "Selected"
            if ready and target_id is not None:
                prompt = expected_bytes.decode("utf-8")
                details = (
                    f'<details><summary>Preview {escape(str(artifact_name))}</summary>'
                    f'<pre id="{escape(target_id, quote=True)}" data-prompt-content>'
                    f"{escape(prompt)}</pre></details>"
                )
                action = (
                    '<button class="quiet-button js-only" type="button" '
                    f'data-copy-prompt data-copy-target="{escape(target_id, quote=True)}" '
                    f'aria-label="Copy {escape(str(artifact_name), quote=True)}">'
                    '<span aria-hidden="true">⧉</span><span data-copy-label>Copy prompt</span>'
                    "</button>"
                )
        rows.append(
            '<article class="session-kit-row">'
            f'<span class="kit-index" aria-hidden="true">{index}</span>'
            '<div class="kit-copy">'
            f'<p class="eyebrow">{escape(eyebrow)}</p>'
            f'<h3>{escape(title)}</h3><p>{escape(description)}</p>{details}'
            "</div>"
            '<div class="kit-action">'
            f'<span class="kit-state" data-state="{escape(state, quote=True)}">'
            f"{escape(state_label_text)}</span>{action}</div></article>"
        )
    return "\n".join(rows)


def _activity_html(records: list[tuple[str, str, str, str]]) -> tuple[str, str]:
    rows: list[str] = []
    states: list[str] = []
    for kind, item, raw_state, evidence in records:
        state = normalize_state(strip_markdown(raw_state))
        states.append(state)
        search = " ".join(
            strip_markdown(value) for value in (kind, item, raw_state, evidence)
        ).casefold()
        rows.append(
            '<div class="activity-row" role="row" data-ledger-row '
            f'data-state="{escape(state, quote=True)}" '
            f'data-search="{escape(search, quote=True)}">'
            f'<span class="activity-kind" role="cell">{escape(kind)}</span>'
            f'<span class="activity-item" role="cell">{inline_html(item)}</span>'
            f'<span class="activity-state" role="cell" data-state="{escape(state, quote=True)}">'
            f"{escape(state_label(state))}</span>"
            f'<span class="activity-evidence" role="cell">{inline_html(evidence)}</span>'
            "</div>"
        )

    options = "\n".join(
        f'<option value="{escape(state, quote=True)}">{escape(state_label(state))}</option>'
        for state in unique_in_order(states)
    )
    return "\n".join(rows), options


def build_dashboard(goal_dir: Path, *, assume_synced_assets: bool = False) -> bytes:
    """Build the exact dashboard bytes without mutating the filesystem."""
    goal_dir = goal_dir.resolve()
    project_root_for(goal_dir)
    goal_path = goal_dir / "goal.md"
    progress_path = goal_dir / "progress.md"
    goal = load_document(goal_path)
    progress = load_document(progress_path)

    title = _metadata(goal, "title")
    slug = _metadata(goal, "slug")
    status = normalize_state(_metadata(goal, "status"))
    health = normalize_state(_metadata(progress, "execution_health"))
    mode = _metadata(goal, "mode")
    ledger_version = _metadata(goal, "ledger_version")
    updated = progress.metadata.get("updated", "").strip() or _metadata(goal, "updated")
    digest = ledger_digest(goal_path, progress_path)

    phase_rows = _table_rows(progress, "Phase tracker")
    decision_rows = _table_rows(progress, "Decision log")
    closeout_rows = _table_rows(goal, "Closeout options")
    verification_rows = _table_rows(progress, "Verification")
    custody_rows = _table_rows(progress, "Custody")
    phase_html, completion = _phase_rail(phase_rows)
    records = _activity_records(
        phase_rows, decision_rows, closeout_rows, verification_rows, custody_rows
    )
    rows_html, options_html = _activity_html(records)

    gates_markdown = get_section(progress, "Open gates").strip()
    gates = gate_items(gates_markdown)
    gates_html = (
        markdown_to_html("\n".join(f"- {gate}" for gate in gates))
        if gates
        else "<p>No open gates.</p>"
    )

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = replace_template(
        template,
        {
            "DIGEST": digest,
            "TITLE_ATTR": escape(title, quote=True),
            "TITLE": escape(title),
            "STATUS_ATTR": escape(status, quote=True),
            "HEALTH_ATTR": escape(health, quote=True),
            "SLUG": escape(slug),
            "UPDATED": escape(updated),
            "LEDGER_VERSION": escape(ledger_version),
            "STATUS_LABEL": escape(state_label(status)),
            "OUTCOME_HTML": _section_html(goal, "Outcome", "Outcome not recorded."),
            "AT_GLANCE_HTML": _section_html(
                progress, "At a glance", "Latest verified state not recorded."
            ),
            "HEALTH_LABEL": escape(state_label(health)),
            "MODE": escape(mode),
            "SYNC_LABEL": escape(asset_status(goal_dir, assume_synced=assume_synced_assets)),
            "GENERATED_DATE": escape(updated),
            "DIGEST_SHORT": digest[:12],
            "PHASE_RAIL_HTML": phase_html,
            "COMPLETION_PERCENT": str(completion),
            "CURRENT_FOCUS_HTML": _section_html(
                progress, "Current focus", "No current focus recorded."
            ),
            "NEXT_ACTION_HTML": _section_html(
                progress, "Next action", "No next action recorded."
            ),
            "GATE_COUNT": str(len(gates)),
            "OPEN_GATES_HTML": gates_html,
            "RECOVERY_HTML": _section_html(
                progress, "Recovery capsule", "No recovery capsule recorded."
            ),
            "STATE_OPTIONS_HTML": options_html,
            "LEDGER_ROW_COUNT": str(len(records)),
            "LEDGER_ROWS_HTML": rows_html,
            "CLOSEOUT_KIT_HTML": _closeout_kit_html(
                goal_dir, goal, verification_rows
            ),
            "GOAL_SECTIONS_HTML": _source_html(goal),
            "PROGRESS_SECTIONS_HTML": _source_html(progress),
            "GENERATED_AT": escape(updated),
        },
    )
    return (rendered.rstrip() + "\n").encode("utf-8")


def _check(goal_dir: Path, *, include_assets: bool) -> list[str]:
    errors: list[str] = []
    index_path = goal_dir / "index.html"
    expected = build_dashboard(goal_dir, assume_synced_assets=include_assets)
    if not index_path.is_file():
        errors.append(f"missing generated dashboard: {index_path}")
    elif index_path.read_bytes() != expected:
        errors.append(f"stale generated dashboard: {index_path}")

    if include_assets:
        destination = _asset_destination(goal_dir)
        for name in SHARED_ASSETS:
            source = ASSET_ROOT / name
            target = destination / name
            if not target.is_file():
                errors.append(f"missing shared asset: {target}")
            elif target.read_bytes() != source.read_bytes():
                errors.append(f"stale shared asset: {target}")
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render docs/goals/<slug>/index.html from goal.md and progress.md."
    )
    parser.add_argument("goal_dir", type=Path, help="Path to docs/goals/<slug>")
    parser.add_argument(
        "--sync-assets",
        action="store_true",
        help="Copy shipped CSS and JavaScript to docs/assets before rendering.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare exact expected bytes without modifying any file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    goal_dir = args.goal_dir.resolve()
    try:
        if args.check:
            errors = _check(goal_dir, include_assets=args.sync_assets)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print(f"OK: generated dashboard is current: {goal_dir / 'index.html'}")
            return 0

        changed_assets = sync_assets(goal_dir) if args.sync_assets else []
        output = build_dashboard(goal_dir)
        index_path = goal_dir / "index.html"
        changed = not index_path.is_file() or index_path.read_bytes() != output
        if changed:
            index_path.write_bytes(output)
        for path in changed_assets:
            print(f"Synced {path}")
        verb = "Rendered" if changed else "Current"
        print(f"{verb}: {index_path}")
        return 0
    except (LedgerError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
