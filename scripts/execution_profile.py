#!/usr/bin/env python3
"""Inspect and record requested, invoked, and effective Goal Ledger profiles."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import tomllib

from agent_profiles import DEFAULT_IMPLEMENTER, IMPLEMENTER_NAMES
from install_skill import AGENT_NAMES, agent_installation_problems, default_codex_home
from ledger_common import LedgerError, load_document, parse_table, project_root_for, split_table_row


IMPLEMENTATION_LAYER = "Implementation"
FABLE_LAYER = "Claude Fable planning peer"
REVIEW_LAYER = "Final adversarial review"
V4_HEADERS = (
    "Layer",
    "Requested profile",
    "Invoked profile",
    "Effective profile",
    "Evidence",
)


def _cell(value: str) -> str:
    value = value.strip()
    if not value or "\n" in value or "\r" in value:
        raise LedgerError("execution profile values must be non-empty single lines")
    return value.replace("|", r"\|")


def _atomic_text(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False, mode="w", encoding="utf-8"
    ) as stream:
        temporary = Path(stream.name)
        stream.write(text)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def record_profile(
    goal_dir: Path,
    *,
    layer: str,
    invoked: str,
    effective: str,
    evidence: str,
    requested: str | None = None,
) -> None:
    goal_dir = goal_dir.resolve()
    project_root_for(goal_dir)
    goal_path = goal_dir / "goal.md"
    goal = load_document(goal_path)
    if goal.metadata.get("ledger_version") not in {"4", "5", "6", "7"}:
        raise LedgerError("execution profile recording requires ledger_version 4, 5, 6, or 7")
    headers, rows = parse_table(goal.sections.get("execution profile", ""))
    if tuple(headers) != V4_HEADERS:
        raise LedgerError("ledger v4 Execution profile table has invalid headers")
    matches = [row for row in rows if row and row[0].strip() == layer]
    if len(matches) != 1:
        raise LedgerError(f"Execution profile must contain exactly one {layer!r} row")
    previous = matches[0]
    requested_value = requested if requested is not None else previous[1]
    replacement = "| " + " | ".join(
        _cell(value)
        for value in (layer, requested_value, invoked, effective, evidence)
    ) + " |"

    lines = goal_path.read_text(encoding="utf-8").splitlines()
    in_section = False
    replaced = 0
    for index, line in enumerate(lines):
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            in_section = heading.group(1).strip() == "Execution profile"
            continue
        if in_section and line.lstrip().startswith("|"):
            cells = split_table_row(line)
            if cells and cells[0].strip() == layer:
                lines[index] = replacement
                replaced += 1
    if replaced != 1:
        raise LedgerError(f"could not replace exactly one {layer!r} execution profile row")

    today = datetime.now(timezone.utc).date().isoformat()
    updated = False
    for index, line in enumerate(lines):
        if line.startswith("updated:"):
            lines[index] = f"updated: {today}"
            updated = True
            break
    if not updated:
        raise LedgerError("goal.md frontmatter has no updated field")
    _atomic_text(goal_path, "\n".join(lines).rstrip() + "\n")


def preflight(
    codex_home: Path,
    *,
    session_visible: str,
    selected_implementer: str = DEFAULT_IMPLEMENTER.name,
    swarm_implementers: tuple[str, ...] = (),
) -> dict[str, object]:
    codex_home = codex_home.expanduser().resolve()
    problems = agent_installation_problems(codex_home)
    profiles: dict[str, dict[str, str]] = {}
    for name in AGENT_NAMES:
        path = codex_home / "agents" / f"{name}.toml"
        if not path.is_file():
            continue
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        profiles[name] = {
            "model": str(data.get("model", "unconfirmed")),
            "effort": str(data.get("model_reasoning_effort", "unconfirmed")),
        }
    configured = not problems
    selected_names = tuple(
        dict.fromkeys((selected_implementer, *swarm_implementers))
    )
    selected_profiles = []
    for name in selected_names:
        selected = profiles.get(name)
        selected_profiles.append(
            {
                "name": name,
                "configured": selected is not None and configured,
                "model": selected["model"] if selected is not None else "unconfirmed",
                "effort": selected["effort"] if selected is not None else "unconfirmed",
            }
        )
    return {
        "configured": configured,
        "session_visible": session_visible,
        "runtime_confirmed": False,
        "effective_profile": "unconfirmed",
        "profiles": profiles,
        "selected_implementer": selected_profiles[0],
        "selected_implementers": selected_profiles,
        "problems": problems,
        "note": (
            "Open a new Codex task after installation before changing session_visible to yes. "
            "Configuration and session visibility do not prove a worker's runtime profile."
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("preflight")
    check.add_argument("--codex-home", type=Path, default=None)
    check.add_argument(
        "--session-visible", choices=("yes", "no", "unconfirmed"), default="unconfirmed"
    )
    check.add_argument(
        "--implementer",
        choices=IMPLEMENTER_NAMES,
        default=DEFAULT_IMPLEMENTER.name,
        help="Implementation preset to highlight in preflight output.",
    )
    check.add_argument(
        "--swarm-implementer",
        action="append",
        choices=IMPLEMENTER_NAMES,
        default=[],
        help="Additional selected mixed-swarm preset; repeat as needed.",
    )
    check.add_argument("--json", action="store_true")

    record = subparsers.add_parser("record")
    record.add_argument("goal_dir", type=Path)
    record.add_argument("--layer", required=True)
    record.add_argument("--requested")
    record.add_argument("--invoked", required=True)
    record.add_argument("--effective", required=True)
    record.add_argument("--evidence", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight(
                args.codex_home or default_codex_home(),
                session_visible=args.session_visible,
                selected_implementer=args.implementer,
                swarm_implementers=tuple(args.swarm_implementer),
            )
            if args.json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print(f"Configured: {'yes' if result['configured'] else 'no'}")
                print(f"Session visible: {result['session_visible']}")
                print("Runtime confirmed: no")
                for index, selected in enumerate(result["selected_implementers"]):
                    lane = "primary" if index == 0 else "swarm"
                    print(
                        f"Selected implementer ({lane}): {selected['name']} "
                        f"({selected['model']} {selected['effort']}; "
                        f"configured={'yes' if selected['configured'] else 'no'})"
                    )
                for problem in result["problems"]:
                    print(f"Problem: {problem}")
                print(result["note"])
            return 0 if result["configured"] else 1
        record_profile(
            args.goal_dir,
            layer=args.layer,
            requested=args.requested,
            invoked=args.invoked,
            effective=args.effective,
            evidence=args.evidence,
        )
        print(f"Recorded execution profile: {args.layer}")
        return 0
    except (LedgerError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
