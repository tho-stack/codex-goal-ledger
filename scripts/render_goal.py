#!/usr/bin/env python3
"""Render a Codex Goal Ledger dashboard from its canonical Markdown."""

from __future__ import annotations

import argparse
from hashlib import sha256
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
    FABLE_FEEDBACK_OPTION,
    FABLE_RESCUE_OPTION,
    PRO_REVIEW_OPTION,
    build_closeout_prompt_artifacts,
    parse_closeout_options,
)
from run_fable_feedback import fable_artifacts, fable_feedback_problems, fable_review_rounds
from run_fable_rescue import fable_rescue_problems
from run_pro_review import pro_review_problems, pro_review_rounds, pro_review_stage
from review_graph import build_review_lanes, progress_tracks
from preview_common import load_preview_state


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
ASSET_ROOT = PACKAGE_ROOT / "assets"
TEMPLATE_PATH = ASSET_ROOT / "templates" / "index.html"
SHARED_ASSETS = ("goal-ledger.css", "goal-ledger.js")


def _asset_version(name: str) -> str:
    """Return a short content hash for deterministic browser cache busting."""
    return sha256((ASSET_ROOT / name).read_bytes()).hexdigest()[:12]


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


def _preview_values(goal_dir: Path) -> dict[str, str]:
    state = load_preview_state(goal_dir)
    if state is None:
        return {
            "PREVIEW_STATE_ATTR": "not-started",
            "PREVIEW_STATE_LABEL": "Not started",
            "PREVIEW_TRANSPORT": "HTTP server required",
            "PREVIEW_LAST_CHECK": "No health check recorded",
            "PREVIEW_LINK_HTML": '<span class="preview-unavailable">Not started</span>',
        }
    label = state_label(state.state)
    link = (
        f'<a href="{escape(state.url, quote=True)}" rel="noopener">'
        f"{escape(state.display_host)}:{state.port}</a>"
    )
    last_check = (
        f"Checked {state.last_health_check}"
        if state.last_health_check
        else "No successful health check recorded"
    )
    return {
        "PREVIEW_STATE_ATTR": escape(state.state, quote=True),
        "PREVIEW_STATE_LABEL": escape(label),
        "PREVIEW_TRANSPORT": escape(state.transport.title()),
        "PREVIEW_LAST_CHECK": escape(last_check),
        "PREVIEW_LINK_HTML": link,
    }


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


def _phase_rail(rows: list[list[str]]) -> str:
    rendered: list[str] = []
    for row in rows:
        phase = row[0].strip() if row else "Unnamed phase"
        raw_state = row[1].strip() if len(row) > 1 else "unknown"
        state = normalize_state(strip_markdown(raw_state))
        current = ' aria-current="step"' if state == "active" else ""
        rendered.append(
            f'<li data-state="{escape(state, quote=True)}">'
            f'<a href="#{_phase_target(phase)}"{current}>'
            f"<strong>{inline_html(phase)}</strong>"
            f"<span>{escape(state_label(state))}</span>"
            "</a></li>"
        )
    return "\n".join(rendered)


def _review_graph_html(lanes: tuple[object, ...]) -> str:
    rendered: list[str] = []
    for lane in lanes:
        sequence: list[str] = []
        for index, node in enumerate(lane.nodes):
            current_attr = ' aria-current="step"' if node.current else ""
            completed_mark = (
                '<span class="review-node-check" aria-label="Completed review" '
                'title="Completed review">✓</span>'
                if node.completed
                else ""
            )
            content = (
                f'<span class="review-node-order" aria-hidden="true">{index + 1:02d}</span>'
                f"{completed_mark}"
                f'<span class="review-node-title">{escape(node.label)}</span>'
                f'<span class="review-node-detail">{escape(node.detail)}</span>'
            )
            if node.href:
                node_html = (
                    f'<a class="review-node" href="{escape(node.href, quote=True)}" '
                    f'data-state="{escape(node.state, quote=True)}"{current_attr}>{content}</a>'
                )
            else:
                node_html = (
                    f'<span class="review-node" data-state="{escape(node.state, quote=True)}"'
                    f'{current_attr}>{content}</span>'
                )
            current_data = ' data-current="true"' if node.current else ""
            completed_data = ' data-completed="true"' if node.completed else ""
            edge_html = ""
            if index < len(lane.edges):
                edge = lane.edges[index]
                arrow = "↩" if edge.direction == "return" else "→"
                edge_html = (
                    f'<div class="review-edge" data-state="{escape(edge.state, quote=True)}" '
                    f'data-direction="{escape(edge.direction, quote=True)}">'
                    f'<span aria-hidden="true">{arrow}</span><small>{escape(edge.label)}</small></div>'
                )
            sequence.append(
                f'<li class="review-step" data-node="{escape(node.key, quote=True)}" '
                f'data-state="{escape(node.state, quote=True)}"{completed_data}{current_data}>'
                f"{node_html}{edge_html}</li>"
            )
        rendered.append(
            f'<section class="review-lane" data-layout="flow" '
            f'aria-labelledby="review-lane-{escape(lane.key, quote=True)}">'
            f'<h3 id="review-lane-{escape(lane.key, quote=True)}">{escape(lane.label)}</h3>'
            f'<ol>{"".join(sequence)}</ol></section>'
        )
    return "\n".join(rendered)


def _progress_tracks_html(tracks: tuple[object, ...]) -> str:
    rendered: list[str] = []
    for track in tracks:
        total = track.total if track.total > 0 else 1
        segments = []
        for index in range(total):
            state = "complete" if index < track.resolved else "pending"
            segments.append(f'<i data-state="{state}"></i>')
        rendered.append(
            f'<div class="progress-track" data-track="{escape(track.key, quote=True)}" '
            f'data-kind="{escape(track.kind, quote=True)}">'
            '<div class="progress-track-heading">'
            f'<strong>{escape(track.label)}</strong><span>{escape(track.summary)}</span></div>'
            f'<span class="progress-segments" aria-hidden="true">{"".join(segments)}</span>'
            "</div>"
        )
    return "\n".join(rendered)


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
    """Render planning choices and any current generated review artifacts."""
    choices = parse_closeout_options(goal)
    fable_round_count = fable_review_rounds(goal)
    fable_round_artifacts = fable_artifacts(goal)
    expected = build_closeout_prompt_artifacts(goal_dir, goal=goal, choices=choices)
    verification = {
        strip_markdown(row[0]).strip(): normalize_state(strip_markdown(row[1]))
        for row in verification_rows
        if len(row) > 1
    }
    all_specs = (
        (
            FABLE_FEEDBACK_OPTION,
            "Claude Fable",
            "Planning critique and opportunities",
            "Read-only plan review with grounded feature ideas and science or research hypotheses.",
            (
                fable_round_artifacts[0].as_posix()
                if fable_round_count == 1
                else f"{fable_round_count} round artifacts"
            ),
            "fable-feedback",
        ),
        (
            FABLE_RESCUE_OPTION,
            "Claude Fable",
            "Scientific rescue",
            "A bounded, falsifiable diagnosis and highest-information experiment for a qualified scientific impasse.",
            None,
            None,
        ),
        (
            PRO_REVIEW_OPTION,
            "GPT Pro",
            "Native high-context review",
            "A GPT-5.6-shaped prompt plus scoped ZIP, visible Pro submission, full raw response, and typed reconciliation without another skill.",
            "evidence/pro-review/",
            None,
        ),
        (
            EXTERNAL_REVIEW_OPTION,
            "Claude / other LLM",
            "Independent completion review",
            "A findings-first, read-only review brief grounded in the canonical ledger and repository evidence.",
            "review-prompt.md",
            "closeout-review-prompt",
        ),
        (
            CODEX_REVIEW_OPTION,
            "Codex closeout",
            "Additional Codex review",
            "An optional advisory code-review pass whose findings must be verified before any fix is accepted.",
            None,
            None,
        ),
        (
            CLEAN_HANDOFF_OPTION,
            "Fresh GPT context",
            "Clean-session handoff",
            "A compact restart brief that points a new session back to repository truth before it acts.",
            "handoff-prompt.md",
            "closeout-handoff-prompt",
        ),
    )
    specs = tuple(spec for spec in all_specs if spec[0] in choices)
    rows: list[str] = []
    for sequence, spec in enumerate(specs, 1):
        option, eyebrow, title, description, artifact_name, target_id = spec
        index = f"K{sequence:02d}"
        choice = choices[option]
        details = ""
        action = ""
        if option == FABLE_FEEDBACK_OPTION:
            checked = " checked" if choice == "yes" else ""
            action = (
                '<label class="kit-choice" title="Recorded in goal.md">'
                f'<input type="checkbox" disabled{checked} '
                'aria-label="Claude Fable peer feedback selection">'
                f'<span>Ask Fable · {fable_round_count} round'
                f'{"" if fable_round_count == 1 else "s"}</span></label>'
            )
        elif option == FABLE_RESCUE_OPTION:
            checked = " checked" if choice == "yes" else ""
            action = (
                '<label class="kit-choice" title="Recorded in goal.md">'
                f'<input type="checkbox" disabled{checked} '
                'aria-label="Claude Fable scientific rescue selection">'
                '<span>Enable scientific rescue</span></label>'
            )
        elif option == PRO_REVIEW_OPTION:
            checked = " checked" if choice == "yes" else ""
            action = (
                '<label class="kit-choice" title="Recorded in goal.md">'
                f'<input type="checkbox" disabled{checked} '
                'aria-label="GPT Pro review selection">'
                f'<span>Ask GPT Pro · {pro_review_stage(goal)} · '
                f'{pro_review_rounds(goal)} round'
                f'{"" if pro_review_rounds(goal) == 1 else "s"}</span></label>'
            )
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
        elif option == FABLE_FEEDBACK_OPTION:
            ready = (
                not fable_feedback_problems(goal_dir, choices=choices)
                and verification.get(FABLE_FEEDBACK_OPTION) == "pass"
            )
            state = "complete" if ready else "pending"
            state_label_text = "Complete" if ready else "Selected"
            available_artifacts = [
                path for path in fable_round_artifacts if (goal_dir / path).is_file()
            ]
            if available_artifacts and target_id is not None:
                feedback = "\n\n---\n\n".join(
                    (goal_dir / path).read_text(encoding="utf-8")
                    for path in available_artifacts
                )
                details = (
                    f'<details><summary>Preview {len(available_artifacts)} of '
                    f'{fable_round_count} Fable rounds</summary>'
                    f'<pre id="{escape(target_id, quote=True)}" data-prompt-content>'
                    f"{escape(feedback)}</pre></details>"
                )
                action += (
                    '<button class="quiet-button js-only" type="button" '
                    f'data-copy-prompt data-copy-target="{escape(target_id, quote=True)}" '
                    'aria-label="Copy Claude Fable feedback">'
                    '<span aria-hidden="true">⧉</span><span data-copy-label>Copy feedback</span>'
                    "</button>"
                )
        elif option == FABLE_RESCUE_OPTION:
            problems = fable_rescue_problems(goal_dir)
            incidents_root = goal_dir / "evidence" / "fable-rescue"
            incident_count = (
                len(list(incidents_root.glob("rescue-[0-9][0-9][0-9]/response.json")))
                if incidents_root.is_dir()
                else 0
            )
            state = "blocked" if problems else ("complete" if incident_count else "pending")
            state_label_text = (
                "Needs attention" if problems else (f"{incident_count} incident(s)" if incident_count else "Armed")
            )
            if problems:
                details = (
                    '<details><summary>Rescue validation</summary><pre>'
                    + escape("\n".join(problems))
                    + "</pre></details>"
                )
        elif option == PRO_REVIEW_OPTION:
            problems = pro_review_problems(goal_dir, require_closed=True)
            passed = verification.get(PRO_REVIEW_OPTION) == "pass"
            ready = not problems and passed
            state = "complete" if ready else "pending"
            state_label_text = "Complete" if ready else "Selected"
            if problems and (goal_dir / "evidence" / "pro-review").exists():
                details = (
                    '<details><summary>GPT Pro custody status</summary><pre>'
                    + escape("\n".join(problems))
                    + "</pre></details>"
                )
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
                action += (
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
    phase_html = _phase_rail(phase_rows)
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
    review_lanes = build_review_lanes(goal_dir, goal, phase_rows, verification_rows)
    tracks = progress_tracks(
        goal, phase_rows, verification_rows, len(gates), review_lanes
    )

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    values = {
            "DIGEST": digest,
            "CSS_VERSION": _asset_version("goal-ledger.css"),
            "JS_VERSION": _asset_version("goal-ledger.js"),
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
            "PROGRESS_TRACKS_HTML": _progress_tracks_html(tracks),
            "REVIEW_GRAPH_HTML": _review_graph_html(review_lanes),
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
        }
    values.update(_preview_values(goal_dir))
    rendered = replace_template(template, values)
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
