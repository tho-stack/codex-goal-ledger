#!/usr/bin/env python3
"""Validate a Codex Goal Ledger's schema, state, assets, and dashboard."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import re
import sys

from ledger_common import (
    CUSTODY_STATES,
    EVIDENCE_RESULTS,
    EXECUTION_HEALTH,
    GOAL_STATUSES,
    PHASE_STATES,
    Document,
    LedgerError,
    code_fences_balanced,
    escape_markdown_text,
    gate_items,
    get_section,
    ledger_digest,
    list_items,
    load_document,
    normalize_key,
    normalize_state,
    parse_table,
    project_root_for,
    strip_markdown,
)
from render_goal import ASSET_ROOT, SHARED_ASSETS, build_dashboard
from generate_closeout_prompts import (
    CODEX_REVIEW_OPTION,
    FABLE_FEEDBACK_OPTION,
    FABLE_RESCUE_OPTION,
    PRO_REVIEW_OPTION,
    closeout_option_labels,
    closeout_prompt_problems,
)
from run_fable_feedback import fable_feedback_problems, fable_review_rounds
from run_fable_rescue import fable_rescue_problems
from run_pro_review import (
    pro_plan_gate_problem,
    pro_review_delivery,
    pro_review_gate,
    pro_review_problems,
    pro_review_rounds,
    pro_review_stage,
)


GOAL_METADATA = (
    "ledger_version",
    "title",
    "slug",
    "status",
    "created",
    "updated",
    "mode",
    "allowed_skipped_phases",
    "allowed_skipped_verifications",
)
PROGRESS_METADATA = ("ledger_version", "goal_slug", "status", "execution_health", "updated")
GOAL_SECTIONS = (
    "Why",
    "Outcome",
    "Success criteria",
    "Scope",
    "Non-goals",
    "Execution profile",
    "Closeout options",
    "Authorization",
    "Completion contract",
)
V4_GOAL_SECTIONS = ("Planning input assessment",)
V5_GOAL_METADATA = (
    "fable_rescue_max_incidents",
    "fable_rescue_rounds_per_incident",
    "fable_rescue_effort",
    "fable_rescue_lineage",
)
V6_GOAL_METADATA = V5_GOAL_METADATA + (
    "pro_review_rounds",
    "pro_review_stage",
    "pro_review_delivery",
    "pro_review_gate",
)
PROGRESS_SECTIONS = (
    "At a glance",
    "Phase tracker",
    "Current focus",
    "Work log",
    "Decision log",
    "Verification",
    "Custody",
    "Open gates",
    "Recovery capsule",
    "Next action",
)
TABLE_SCHEMAS = {
    "Closeout options": ("Option", "Choice", "Artifact or action"),
    "Phase tracker": ("Phase", "State", "Evidence", "Next gate"),
    "Decision log": ("Decision", "Why", "Status"),
    "Verification": ("Check", "Result", "Evidence"),
    "Custody": ("Work item", "Owner", "State", "Recovery action"),
}
EXECUTION_PROFILE_SCHEMAS = {
    "2": ("Layer", "Requested profile", "Effective profile", "Rule"),
    "3": ("Layer", "Requested profile", "Effective profile", "Rule"),
    "4": (
        "Layer",
        "Requested profile",
        "Invoked profile",
        "Effective profile",
        "Evidence",
    ),
    "5": (
        "Layer",
        "Requested profile",
        "Invoked profile",
        "Effective profile",
        "Evidence",
    ),
    "6": (
        "Layer",
        "Requested profile",
        "Invoked profile",
        "Effective profile",
        "Evidence",
    ),
    "7": (
        "Layer",
        "Requested profile",
        "Invoked profile",
        "Effective profile",
        "Evidence",
    ),
}
V4_EXECUTION_LAYERS = (
    "Planning and architecture",
    "Implementation",
    "Claude Fable planning peer",
    "Final adversarial review",
)
CLOSEOUT_CHOICES = {"ask", "yes", "no"}
CURRENT_STATE_SECTIONS = (
    "At a glance",
    "Phase tracker",
    "Current focus",
    "Open gates",
    "Recovery capsule",
    "Next action",
)


class Problems:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def add(self, message: str) -> None:
        if message not in self.errors:
            self.errors.append(message)


class DashboardAudit(HTMLParser):
    """Collect the small set of structural facts required for accessible output."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.declarations: list[str] = []
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.ids: list[str] = []
        self.fragments: list[str] = []
        self.labelledby: list[str] = []
        self.roles: Counter[str] = Counter()
        self.heading_levels: list[int] = []

    def handle_decl(self, decl: str) -> None:
        self.declarations.append(decl.casefold())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        identifier = attributes.get("id")
        if identifier:
            self.ids.append(identifier)
        href = attributes.get("href")
        if href and href.startswith("#") and len(href) > 1:
            self.fragments.append(href[1:])
        labelledby = attributes.get("aria-labelledby")
        if labelledby:
            self.labelledby.extend(labelledby.split())
        role = attributes.get("role")
        if role:
            self.roles[role] += 1
        if re.fullmatch(r"h[1-6]", tag):
            self.heading_levels.append(int(tag[1]))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def _redundant_execution_approval_gate(progress: Document) -> str | None:
    """Return a live-state line that re-gates already-authorized local execution."""
    authorization = re.compile(
        r"\b(?:explicit(?:ly)?\s+)?(?:owner\s+)?"
        r"(?:authorize|authorization|authority|approval|approve)\b"
    )
    waiting = re.compile(
        r"\b(?:await|awaiting|waiting|wait|need|needs|require|requires|required|"
        r"request|requested|reply|resume|not granted|before|do not)\b"
    )
    ordinary_execution = re.compile(
        r"\b(?:plant blind|qualification|benchmark|validation|test|testing|"
        r"implementation|build|simulation|solver|experiment|campaign|research|"
        r"literature|hardware|component|download|dependency setup|installation|"
        r"browser|local (?:run|compute|execution)|replacement run|retry|rerun|re run)\b"
    )
    real_boundary = re.compile(
        r"\b(?:external (?:transmission|write|export)|data export|destructive|"
        r"purchase|public (?:publish|publishing|message)|secret disclosure|"
        r"unsafe physical|account access|material scope expansion|"
        r"outside (?:the )?(?:accepted |recorded )?(?:goal )?(?:scope|envelope)|"
        r"not authorized by (?:the )?(?:goal|contract))\b"
    )

    for section in CURRENT_STATE_SECTIONS:
        for raw_line in get_section(progress, section).splitlines():
            line = normalize_key(strip_markdown(raw_line))
            if (
                line
                and authorization.search(line)
                and waiting.search(line)
                and ordinary_execution.search(line)
                and not real_boundary.search(line)
            ):
                return line
    return None


def _metadata(document: Document, fields: tuple[str, ...], problems: Problems) -> None:
    for field in fields:
        if not document.metadata.get(field, "").strip():
            problems.add(f"{document.path}: missing required frontmatter field: {field}")


def _sections(document: Document, names: tuple[str, ...], problems: Problems) -> None:
    headings = [
        normalize_key(match.group(1))
        for match in re.finditer(r"^\s*##\s+(.+?)\s*$", document.body, flags=re.MULTILINE)
    ]
    duplicates = sorted(name for name, count in Counter(headings).items() if count > 1)
    for name in duplicates:
        problems.add(f"{document.path}: duplicate level-two section: {name}")
    for name in names:
        if not get_section(document, name).strip():
            problems.add(f"{document.path}: missing or empty section: {name}")


def _fenced_code(document: Document, problems: Problems) -> None:
    if not code_fences_balanced(document.body):
        problems.add(f"{document.path}: unbalanced fenced code block")
    for section, markdown in document.sections.items():
        if not code_fences_balanced(markdown):
            problems.add(
                f"{document.path}: section {section!r} has an unbalanced fenced code block; "
                "fences may not cross section boundaries"
            )


def _h1(document: Document, expected: str, problems: Problems) -> None:
    headings = re.findall(r"^\s*#\s+(.+?)\s*$", document.body, flags=re.MULTILINE)
    expected_heading = escape_markdown_text(expected)
    if len(headings) != 1:
        problems.add(f"{document.path}: expected exactly one level-one heading, found {len(headings)}")
    elif headings[0] != expected_heading:
        problems.add(
            f"{document.path}: level-one heading must be literal title text "
            f"{expected_heading!r}, found {headings[0]!r}"
        )


def _date_field(document: Document, field: str, problems: Problems) -> date | None:
    raw = document.metadata.get(field, "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        problems.add(f"{document.path}: {field} must use YYYY-MM-DD, found {raw!r}")
        return None
    if parsed.isoformat() != raw:
        problems.add(f"{document.path}: {field} must use canonical YYYY-MM-DD, found {raw!r}")
        return None
    return parsed


def _canonical_state(
    document: Document,
    field: str,
    allowed: set[str],
    problems: Problems,
) -> str:
    raw = document.metadata.get(field, "").strip()
    state = normalize_state(raw)
    if raw != state or state not in allowed:
        problems.add(
            f"{document.path}: invalid {field} {raw!r}; allowed: {', '.join(sorted(allowed))}"
        )
    return state


def _contract_allowlist(document: Document, field: str, problems: Problems) -> set[str]:
    raw = document.metadata.get(field, "").strip()
    if not raw:
        return set()
    if raw == "none":
        return set()
    labels = [strip_markdown(label).strip() for label in raw.split(";")]
    if any(not label for label in labels):
        problems.add(
            f"{document.path}: {field} must be 'none' or semicolon-separated exact row labels"
        )
        return set()
    normalized = [normalize_key(label) for label in labels]
    if len(normalized) != len(set(normalized)):
        problems.add(f"{document.path}: {field} contains duplicate row labels")
    return set(normalized)


def _validate_skip_permissions(
    document: Document,
    section: str,
    rows: list[list[str]],
    state_column: int,
    allowed: set[str],
    field: str,
    problems: Problems,
) -> None:
    row_labels = {
        normalize_key(strip_markdown(row[0])): strip_markdown(row[0]).strip()
        for row in rows
        if row and strip_markdown(row[0]).strip()
    }
    for allowed_label in sorted(allowed - set(row_labels)):
        problems.add(
            f"{document.path}: {field} names no matching {section} row: {allowed_label!r}"
        )
    for index, row in enumerate(rows, 1):
        if len(row) <= state_column:
            continue
        if normalize_state(strip_markdown(row[state_column])) != "skipped":
            continue
        label = strip_markdown(row[0]).strip()
        if normalize_key(label) not in allowed:
            problems.add(
                f"{document.path}: {section} row {index} {label!r} is skipped but "
                f"{field} does not authorize it"
            )


def _table(
    document: Document,
    section: str,
    problems: Problems,
) -> list[list[str]]:
    headers, rows = parse_table(get_section(document, section))
    expected = (
        EXECUTION_PROFILE_SCHEMAS.get(document.metadata.get("ledger_version", ""), ())
        if section == "Execution profile"
        else TABLE_SCHEMAS[section]
    )
    normalized = tuple(normalize_key(header) for header in headers)
    expected_normalized = tuple(normalize_key(header) for header in expected)
    if normalized != expected_normalized:
        found = " | ".join(headers) if headers else "no parseable table"
        problems.add(
            f"{document.path}: {section} table headers must be "
            f"{' | '.join(expected)}; found {found}"
        )
        return []
    if not rows:
        problems.add(f"{document.path}: {section} table must contain at least one row")
    for row_number, row in enumerate(rows, 1):
        if len(row) != len(expected):
            problems.add(
                f"{document.path}: {section} row {row_number} must contain exactly "
                f"{len(expected)} cells; found {len(row)}. Escape literal pipes as \\|"
            )
    return rows


def _cell_state(
    document: Document,
    section: str,
    row_number: int,
    raw: str,
    allowed: set[str],
    problems: Problems,
) -> str:
    visible = strip_markdown(raw).strip()
    state = normalize_state(visible)
    if visible != state or state not in allowed:
        problems.add(
            f"{document.path}: {section} row {row_number} has invalid state {raw!r}; "
            f"allowed: {', '.join(sorted(allowed))}"
        )
    return state


def _required_cells(
    document: Document,
    section: str,
    rows: list[list[str]],
    problems: Problems,
) -> None:
    for row_number, row in enumerate(rows, 1):
        for column, value in enumerate(row, 1):
            if not strip_markdown(value).strip():
                problems.add(
                    f"{document.path}: {section} row {row_number}, column {column} must not be empty"
                )


def _validate_markdown(goal_dir: Path, problems: Problems) -> tuple[Document, Document] | None:
    goal_path = goal_dir / "goal.md"
    progress_path = goal_dir / "progress.md"
    try:
        goal = load_document(goal_path)
        progress = load_document(progress_path)
    except LedgerError as exc:
        problems.add(str(exc))
        return None

    _metadata(
        goal,
        GOAL_METADATA
        + (
            V6_GOAL_METADATA
            if goal.metadata.get("ledger_version") in {"6", "7"}
            else V5_GOAL_METADATA
            if goal.metadata.get("ledger_version") == "5"
            else ()
        ),
        problems,
    )
    _metadata(progress, PROGRESS_METADATA, problems)
    _fenced_code(goal, problems)
    _fenced_code(progress, problems)
    goal_version = goal.metadata.get("ledger_version", "").strip()
    progress_version = progress.metadata.get("ledger_version", "").strip()
    _sections(
        goal,
        GOAL_SECTIONS + (V4_GOAL_SECTIONS if goal_version in {"4", "5", "6", "7"} else ()),
        problems,
    )
    _sections(progress, PROGRESS_SECTIONS, problems)

    title = goal.metadata.get("title", "").strip()
    _h1(goal, title, problems)
    _h1(progress, f"Progress: {title}", problems)

    if goal_version not in {"2", "3", "4", "5", "6", "7"}:
        problems.add(
            f"{goal.path}: ledger_version must be 2, 3, 4, 5, 6, or 7, found {goal_version!r}"
        )
    if progress_version not in {"2", "3", "4", "5", "6", "7"}:
        problems.add(
            f"{progress.path}: ledger_version must be 2, 3, 4, 5, 6, or 7, found {progress_version!r}"
        )
    if goal_version != progress_version:
        problems.add("goal.md and progress.md ledger_version values must agree")
    try:
        fable_review_rounds(goal)
    except LedgerError as exc:
        problems.add(f"{goal.path}: {exc}")
    if goal_version in {"6", "7"}:
        for parser in (
            pro_review_rounds,
            pro_review_stage,
            pro_review_delivery,
            pro_review_gate,
        ):
            try:
                parser(goal)
            except LedgerError as exc:
                problems.add(f"{goal.path}: {exc}")

    slug = goal.metadata.get("slug", "").strip()
    goal_slug = progress.metadata.get("goal_slug", "").strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        problems.add(f"{goal.path}: slug must be lowercase hyphenated text, found {slug!r}")
    if slug != goal_dir.name:
        problems.add(f"{goal.path}: slug {slug!r} must match directory name {goal_dir.name!r}")
    if slug != goal_slug:
        problems.add("goal.md slug and progress.md goal_slug must agree")

    goal_status = _canonical_state(goal, "status", GOAL_STATUSES, problems)
    progress_status = _canonical_state(progress, "status", GOAL_STATUSES, problems)
    health = _canonical_state(progress, "execution_health", EXECUTION_HEALTH, problems)
    if goal_status != progress_status:
        problems.add("goal.md and progress.md status values must agree")

    created = _date_field(goal, "created", problems)
    goal_updated = _date_field(goal, "updated", problems)
    progress_updated = _date_field(progress, "updated", problems)
    if created and goal_updated and goal_updated < created:
        problems.add(f"{goal.path}: updated date must not precede created date")
    if created and progress_updated and progress_updated < created:
        problems.add(f"{progress.path}: updated date must not precede the goal's created date")

    success_criteria = list_items(get_section(goal, "Success criteria"))
    if not success_criteria:
        problems.add(f"{goal.path}: Success criteria must contain at least one list item")

    if goal_version in {"4", "5", "6", "7"}:
        assessment = normalize_key(strip_markdown(get_section(goal, "Planning input assessment")))
        if "required before execution" not in assessment:
            problems.add(
                f"{goal.path}: Planning input assessment must state Required before execution"
            )
        if "optional improves result" not in assessment:
            problems.add(
                f"{goal.path}: Planning input assessment must state Optional, improves result"
            )
        if (
            "no additional information would materially improve this plan" not in assessment
            and "default if omitted" not in assessment
        ):
            problems.add(
                f"{goal.path}: optional planning inputs must state Default if omitted, or say "
                "that no additional information would materially improve the plan"
            )

    execution_rows = _table(goal, "Execution profile", problems)
    closeout_rows = _table(goal, "Closeout options", problems)
    phase_rows = _table(progress, "Phase tracker", problems)
    decision_rows = _table(progress, "Decision log", problems)
    verification_rows = _table(progress, "Verification", problems)
    custody_rows = _table(progress, "Custody", problems)
    for document, section, rows in (
        (goal, "Execution profile", execution_rows),
        (goal, "Closeout options", closeout_rows),
        (progress, "Phase tracker", phase_rows),
        (progress, "Decision log", decision_rows),
        (progress, "Verification", verification_rows),
        (progress, "Custody", custody_rows),
    ):
        _required_cells(document, section, rows, problems)

    if goal_version in {"4", "5", "6", "7"}:
        actual_layers = tuple(strip_markdown(row[0]).strip() for row in execution_rows if row)
        if actual_layers != V4_EXECUTION_LAYERS:
            problems.add(
                f"{goal.path}: ledger v4 Execution profile rows must be exactly, in order: "
                + "; ".join(V4_EXECUTION_LAYERS)
            )
        for index, row in enumerate(execution_rows, 1):
            if len(row) != 5:
                continue
            invoked = normalize_key(strip_markdown(row[2]))
            effective = normalize_key(strip_markdown(row[3]))
            if invoked == "not invoked" and effective != "unconfirmed":
                problems.add(
                    f"{goal.path}: Execution profile row {index} cannot claim an effective "
                    "profile before invocation"
                )

    closeout_choices: dict[str, str] = {}
    try:
        expected_closeout_labels = closeout_option_labels(goal)
    except LedgerError as exc:
        problems.add(str(exc))
        expected_closeout_labels = ()
    actual_closeout_labels: list[str] = []
    for index, row in enumerate(closeout_rows, 1):
        if len(row) < 2:
            continue
        label = strip_markdown(row[0]).strip()
        choice = normalize_key(strip_markdown(row[1]))
        actual_closeout_labels.append(label)
        if choice not in CLOSEOUT_CHOICES:
            problems.add(
                f"{goal.path}: Closeout options row {index} has invalid choice "
                f"{choice!r}; expected ask, yes, or no"
            )
        closeout_choices[label] = choice
    if tuple(actual_closeout_labels) != expected_closeout_labels:
        problems.add(
            f"{goal.path}: Closeout options must contain these exact ordered rows: "
            + "; ".join(expected_closeout_labels)
        )

    redundant_execution_gate = _redundant_execution_approval_gate(progress)
    if redundant_execution_gate:
        problems.add(
            f"{progress.path}: remove the repeated in-scope execution approval gate; "
            "starting the goal authorizes the entire accepted execution envelope in Scope and "
            "Authorization, while manifests, hashes, and resource caps are custody evidence"
        )

    if (
        closeout_choices.get(FABLE_FEEDBACK_OPTION) == "yes"
        or closeout_choices.get(FABLE_RESCUE_OPTION) == "yes"
    ):
        current_state = normalize_key(
            strip_markdown(
                "\n".join(
                    get_section(progress, section)
                    for section in ("At a glance", "Current focus", "Open gates", "Next action")
                )
            )
        )
        duplicate_approval = (
            "approve sending" in current_state
            or re.search(
                r"(?:await|waiting|wait|need|require|request|reply|resume).{0,160}"
                r"(?:approve|approval).{0,160}(?:claude|fable)",
                current_state,
            )
            or re.search(
                r"(?:claude|fable).{0,160}(?:approve|approval).{0,160}"
                r"(?:await|waiting|wait|need|require|request|reply|resume)",
                current_state,
            )
        )
        if duplicate_approval:
            problems.add(
                f"{progress.path}: remove the conversational Claude Fable approval gate; "
                "lane authorization permits manifest preparation, while exact transmission "
                "approval must use the owner-facing native Codex checkbox"
            )

    if closeout_choices.get(PRO_REVIEW_OPTION) == "yes":
        current_state = normalize_key(
            strip_markdown(
                "\n".join(
                    get_section(progress, section)
                    for section in ("At a glance", "Current focus", "Open gates", "Next action")
                )
            )
        )
        duplicate_pro_approval = (
            re.search(
                r"(?:await|waiting|wait|need|require|request|reply|resume).{0,160}"
                r"(?:approve|approval).{0,160}(?:gpt pro|chatgpt pro|pro review)",
                current_state,
            )
            or re.search(
                r"(?:gpt pro|chatgpt pro|pro review).{0,160}(?:approve|approval).{0,160}"
                r"(?:await|waiting|wait|need|require|request|reply|resume)",
                current_state,
            )
        )
        if duplicate_pro_approval:
            problems.add(
                f"{progress.path}: remove the conversational GPT Pro approval gate; use the "
                "recorded selection and exact generated packet under the action-time UI policy"
            )

    phase_states = [
        _cell_state(progress, "Phase tracker", index, row[1], PHASE_STATES, problems)
        for index, row in enumerate(phase_rows, 1)
        if len(row) > 1
    ]
    if phase_states.count("active") > 1:
        problems.add(f"{progress.path}: Phase tracker may contain at most one active phase")

    verification_states = [
        _cell_state(progress, "Verification", index, row[1], EVIDENCE_RESULTS, problems)
        for index, row in enumerate(verification_rows, 1)
        if len(row) > 1
    ]
    for index, row in enumerate(verification_rows, 1):
        if len(row) > 2 and "fable-rescue" in normalize_key(strip_markdown(row[2])):
            problems.add(
                f"{progress.path}: Verification row {index} cites a Fable rescue artifact; "
                "rescue is advisory and may not be completion evidence"
            )
    custody_states = [
        _cell_state(progress, "Custody", index, row[2], CUSTODY_STATES, problems)
        for index, row in enumerate(custody_rows, 1)
        if len(row) > 2
    ]

    allowed_skipped_phases = _contract_allowlist(
        goal, "allowed_skipped_phases", problems
    )
    allowed_skipped_verifications = _contract_allowlist(
        goal, "allowed_skipped_verifications", problems
    )
    _validate_skip_permissions(
        progress,
        "Phase tracker",
        phase_rows,
        1,
        allowed_skipped_phases,
        "allowed_skipped_phases",
        problems,
    )
    _validate_skip_permissions(
        progress,
        "Verification",
        verification_rows,
        1,
        allowed_skipped_verifications,
        "allowed_skipped_verifications",
        problems,
    )

    for index, row in enumerate(custody_rows, 1):
        if len(row) < 4:
            continue
        state = normalize_state(strip_markdown(row[2]))
        recovery = normalize_key(strip_markdown(row[3]))
        if state != "complete" and recovery in {"", "none", "n a", "not applicable"}:
            problems.add(
                f"{progress.path}: Custody row {index} is {state!r} and needs a recovery action"
            )

    recovery = normalize_key(strip_markdown(get_section(progress, "Recovery capsule")))
    for field in (
        "last verified truth",
        "current layer",
        "resume at",
        "do not assume",
        "canonical files",
    ):
        if field not in recovery:
            problems.add(f"{progress.path}: Recovery capsule is missing {field!r}")

    if goal_status == "complete":
        unresolved_closeout = [
            label
            for label in expected_closeout_labels
            if closeout_choices.get(label) == "ask"
        ]
        if unresolved_closeout:
            problems.add(
                "complete goals must resolve every Closeout options choice to yes or no; "
                "still ask: " + "; ".join(unresolved_closeout)
            )
        verification_results = {
            strip_markdown(row[0]).strip(): normalize_state(strip_markdown(row[1]))
            for row in verification_rows
            if len(row) > 1
        }
        if closeout_choices.get(CODEX_REVIEW_OPTION) == "yes":
            if verification_results.get(CODEX_REVIEW_OPTION) != "pass":
                problems.add(
                    "complete goals that select Additional Codex review require a passing "
                    "Verification row with that exact label"
                )
        if closeout_choices.get(FABLE_FEEDBACK_OPTION) == "yes":
            if verification_results.get(FABLE_FEEDBACK_OPTION) != "pass":
                problems.add(
                    "complete goals that select Claude Fable peer feedback require a passing "
                    "Verification row with that exact label"
                )
        if closeout_choices.get(PRO_REVIEW_OPTION) == "yes":
            if verification_results.get(PRO_REVIEW_OPTION) != "pass":
                problems.add(
                    "complete goals that select GPT Pro review require a passing "
                    "Verification row with that exact label"
                )
        if health != "inactive":
            problems.add("complete goals require execution_health: inactive")
        unresolved_phases = [state for state in phase_states if state not in {"complete", "skipped"}]
        if unresolved_phases:
            problems.add(
                "complete goals require every phase to be complete or skipped; unresolved: "
                + ", ".join(unresolved_phases)
            )
        unresolved_checks = [state for state in verification_states if state not in {"pass", "skipped"}]
        if unresolved_checks:
            problems.add(
                "complete goals cannot retain pending, fail, or blocked verification; unresolved: "
                + ", ".join(unresolved_checks)
            )
        unresolved_custody = [state for state in custody_states if state != "complete"]
        if unresolved_custody:
            problems.add(
                "complete goals require every custody row to be complete; unresolved: "
                + ", ".join(unresolved_custody)
            )
        gates = gate_items(get_section(progress, "Open gates"))
        if gates:
            problems.add("complete goals cannot retain open gates: " + "; ".join(gates))

    return goal, progress


def _tags(audit: DashboardAudit, name: str) -> list[dict[str, str | None]]:
    return [attributes for tag, attributes in audit.tags if tag == name]


def _validate_dashboard(
    goal_dir: Path,
    documents: tuple[Document, Document] | None,
    problems: Problems,
) -> None:
    index_path = goal_dir / "index.html"
    if not index_path.is_file():
        problems.add(f"missing generated dashboard: {index_path}")
        return
    try:
        raw = index_path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        problems.add(f"{index_path}: must be readable UTF-8 HTML: {exc}")
        return
    if re.search(r'''(?i)href\s*=\s*["']file://''', text):
        problems.add(f"{index_path}: generated dashboard must not link to a file:// URL")

    # With valid canonical documents, exact deterministic comparison below proves
    # that every shipped template field was resolved. Only use a raw-token check
    # as a fallback when the Markdown is too broken to derive expected bytes;
    # literal {{TOKENS}} are valid user-authored Markdown and must round-trip.
    if documents is None and re.search(r"\{\{[A-Z0-9_]+\}\}", text):
        problems.add(f"{index_path}: unresolved template token detected")

    audit = DashboardAudit()
    try:
        audit.feed(text)
        audit.close()
    except Exception as exc:  # HTMLParser failures should become a normal validation error.
        problems.add(f"{index_path}: HTML parsing failed: {exc}")
        return

    if "doctype html" not in audit.declarations:
        problems.add(f"{index_path}: missing <!doctype html>")
    html_tags = _tags(audit, "html")
    if len(html_tags) != 1 or not html_tags[0].get("lang"):
        problems.add(f"{index_path}: expected one <html> element with a lang attribute")
    main_tags = _tags(audit, "main")
    if len(main_tags) != 1 or main_tags[0].get("id") != "main-content":
        problems.add(f"{index_path}: expected one <main id=\"main-content\">")
    h1_tags = _tags(audit, "h1")
    if len(h1_tags) != 1 or h1_tags[0].get("id") != "goal-title":
        problems.add(f"{index_path}: expected one <h1 id=\"goal-title\">")

    duplicate_ids = sorted(identifier for identifier, count in Counter(audit.ids).items() if count > 1)
    if duplicate_ids:
        problems.add(f"{index_path}: duplicate id values: {', '.join(duplicate_ids)}")
    known_ids = set(audit.ids)
    missing_targets = sorted(set(audit.fragments + audit.labelledby) - known_ids)
    if missing_targets:
        problems.add(
            f"{index_path}: fragment or aria-labelledby targets do not exist: {', '.join(missing_targets)}"
        )

    skip_links = [
        attrs
        for attrs in _tags(audit, "a")
        if "skip-link" in (attrs.get("class") or "").split()
    ]
    if len(skip_links) != 1 or skip_links[0].get("href") != "#main-content":
        problems.add(f"{index_path}: expected a skip link to #main-content")

    meta = {
        attrs.get("name"): attrs.get("content")
        for attrs in _tags(audit, "meta")
        if attrs.get("name")
    }
    if not meta.get("viewport"):
        problems.add(f"{index_path}: missing viewport metadata")
    if not meta.get("description"):
        problems.add(f"{index_path}: missing description metadata")
    if not meta.get("ledger-digest"):
        problems.add(f"{index_path}: missing ledger-digest metadata")

    stylesheets = [
        attrs
        for attrs in _tags(audit, "link")
        if "stylesheet" in (attrs.get("rel") or "").split()
    ]
    if not any(attrs.get("href") == "../../assets/goal-ledger.css" for attrs in stylesheets):
        problems.add(f"{index_path}: missing shared goal-ledger.css reference")
    scripts = _tags(audit, "script")
    if not any(
        attrs.get("src") == "../../assets/goal-ledger.js" and "defer" in attrs
        for attrs in scripts
    ):
        problems.add(f"{index_path}: shared goal-ledger.js must be loaded with defer")

    buttons = _tags(audit, "button")
    if any(attrs.get("type") != "button" for attrs in buttons):
        problems.add(f"{index_path}: every dashboard button must use type=\"button\"")
    images = _tags(audit, "img")
    if any("alt" not in attrs for attrs in images):
        problems.add(f"{index_path}: every image must provide alt text")
    if not any(attrs.get("aria-live") for attrs in _tags(audit, "output")):
        problems.add(f"{index_path}: filtered result count must expose an aria-live region")
    if not any(attrs.get("aria-label") for attrs in _tags(audit, "nav")):
        problems.add(f"{index_path}: navigation needs an accessible label")
    if audit.roles["table"] < 1 or audit.roles["columnheader"] < 1 or audit.roles["cell"] < 1:
        problems.add(f"{index_path}: operational record needs table, columnheader, and cell roles")
    for _, attrs in audit.tags:
        if any(name.casefold().startswith("on") for name in attrs):
            problems.add(f"{index_path}: inline event handlers are not allowed")
            break
    for previous, current in zip(audit.heading_levels, audit.heading_levels[1:]):
        if current > previous + 1:
            problems.add(
                f"{index_path}: heading hierarchy jumps from h{previous} to h{current}"
            )
            break

    if documents is not None:
        goal, progress = documents
        expected_digest = ledger_digest(goal.path, progress.path)
        if meta.get("ledger-digest") != expected_digest:
            problems.add(
                f"{index_path}: ledger digest is stale; run scripts/render_goal.py {goal_dir}"
            )
        body_tags = _tags(audit, "body")
        if len(body_tags) == 1:
            expected_status = normalize_state(goal.metadata.get("status", ""))
            expected_health = normalize_state(progress.metadata.get("execution_health", ""))
            if body_tags[0].get("data-goal-status") != expected_status:
                problems.add(f"{index_path}: body goal status does not match goal.md")
            if body_tags[0].get("data-execution-health") != expected_health:
                problems.add(f"{index_path}: body execution health does not match progress.md")
        try:
            expected = build_dashboard(goal_dir)
        except (LedgerError, OSError) as exc:
            problems.add(f"cannot derive deterministic dashboard: {exc}")
        else:
            if raw != expected:
                problems.add(
                    f"{index_path}: generated bytes do not match the canonical Markdown and template"
                )


def _validate_assets(goal_dir: Path, problems: Problems) -> None:
    try:
        project_root = project_root_for(goal_dir)
    except LedgerError as exc:
        problems.add(str(exc))
        return
    destination = project_root / "docs" / "assets"
    for name in SHARED_ASSETS:
        source = ASSET_ROOT / name
        target = destination / name
        if not source.is_file():
            problems.add(f"missing shipped asset: {source}")
        elif not target.is_file():
            problems.add(f"missing shared asset: {target}")
        elif target.read_bytes() != source.read_bytes():
            problems.add(
                f"stale shared asset: {target}; run scripts/render_goal.py --sync-assets {goal_dir}"
            )


def _validate_closeout_prompts(
    goal_dir: Path,
    documents: tuple[Document, Document] | None,
    problems: Problems,
) -> None:
    if documents is None:
        return
    goal, _ = documents
    complete = normalize_state(goal.metadata.get("status", "")) == "complete"
    try:
        prompt_problems = closeout_prompt_problems(goal_dir, goal=goal)
    except (LedgerError, OSError) as exc:
        problems.add(f"cannot validate closeout prompts: {exc}")
        return
    for problem in prompt_problems:
        if not complete and problem.startswith("missing selected closeout prompt:"):
            continue
        problems.add(f"{goal_dir}: {problem}")
    try:
        feedback_problems = fable_feedback_problems(goal_dir)
    except (LedgerError, OSError) as exc:
        problems.add(f"cannot validate Fable feedback: {exc}")
        return
    for problem in feedback_problems:
        if not complete and problem.startswith("missing selected Fable feedback"):
            continue
        problems.add(f"{goal_dir}: {problem}")
    try:
        rescue_problems = fable_rescue_problems(goal_dir, require_closed=complete)
    except (LedgerError, OSError) as exc:
        problems.add(f"cannot validate Fable scientific rescue: {exc}")
        return
    for problem in rescue_problems:
        problems.add(f"{goal_dir}: {problem}")
    try:
        pro_problems = pro_review_problems(goal_dir, require_closed=complete)
    except (LedgerError, OSError) as exc:
        problems.add(f"cannot validate GPT Pro review: {exc}")
        return
    for problem in pro_problems:
        problems.add(f"{goal_dir}: {problem}")

    try:
        plan_gate = pro_plan_gate_problem(goal_dir, goal, documents[1])
    except (LedgerError, OSError) as exc:
        problems.add(f"cannot validate GPT Pro plan gate: {exc}")
    else:
        if plan_gate:
            problems.add(f"{goal_dir}: {plan_gate}")


def validate(goal_dir: Path) -> list[str]:
    problems = Problems()
    goal_dir = goal_dir.expanduser().resolve()
    try:
        project_root_for(goal_dir)
    except LedgerError as exc:
        problems.add(str(exc))
        return problems.errors
    documents = _validate_markdown(goal_dir, problems)
    _validate_dashboard(goal_dir, documents, problems)
    _validate_assets(goal_dir, problems)
    _validate_closeout_prompts(goal_dir, documents, problems)
    return problems.errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a docs/goals/<slug> ledger and its generated dashboard."
    )
    parser.add_argument("goal_dir", type=Path, help="Path to docs/goals/<slug>")
    parser.add_argument("--quiet", action="store_true", help="Print nothing on success.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        errors = validate(args.goal_dir)
    except OSError as exc:
        errors = [str(exc)]
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"FAILED: {len(errors)} validation error(s)", file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"OK: valid goal ledger: {args.goal_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
