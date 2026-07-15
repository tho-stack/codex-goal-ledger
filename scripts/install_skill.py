#!/usr/bin/env python3
"""Install the Codex Goal Ledger skill from this repository."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import tomllib

from agent_profiles import AGENT_NAMES, PROFILE_BY_NAME


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "codex-goal-ledger"
PACKAGE_ENTRIES = ("SKILL.md", "agents", "assets", "references", "scripts")
IGNORED_NAMES = frozenset({".DS_Store", "__pycache__"})
IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})
AGENT_SOURCE = PACKAGE_ROOT / "assets" / "agent-profiles"
MANAGED_BEGIN = "# BEGIN codex-goal-ledger managed agents"
MANAGED_END = "# END codex-goal-ledger managed agents"
MULTI_AGENT_SECTION = "features.multi_agent_v2"
MULTI_AGENT_SETTINGS = {
    "hide_spawn_agent_metadata": False,
    "max_concurrent_threads_per_session": 8,
    "tool_namespace": "agents",
}
REVIEW_APPROVAL_SETTINGS = {
    "approvals_reviewer": "user",
    "approval_policy": "on-request",
}


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def default_destination() -> Path:
    """Return the portable Codex skill destination."""
    return default_codex_home() / "skills" / SKILL_NAME


def managed_agent_block() -> str:
    rows = [MANAGED_BEGIN]
    for name in AGENT_NAMES:
        rows.extend(
            (
                f"[agents.{name}]",
                f'config_file = "./agents/{name}.toml"',
                "",
            )
        )
    rows.append(MANAGED_END)
    return "\n".join(rows)


def _managed_pattern() -> re.Pattern[str]:
    return re.compile(
        rf"(?ms)^{re.escape(MANAGED_BEGIN)}\n.*?^{re.escape(MANAGED_END)}\n?"
    )


def _validate_toml(text: str, path: Path) -> None:
    try:
        tomllib.loads(text or "\n")
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"refusing invalid TOML for {path}: {exc}") from exc


def _config_with_agents(config_text: str, config_path: Path, *, replace: bool) -> str:
    _validate_toml(config_text, config_path)
    if config_text.count(MANAGED_BEGIN) != config_text.count(MANAGED_END):
        raise ValueError(f"unbalanced Goal Ledger managed markers in {config_path}")
    pattern = _managed_pattern()
    matches = list(pattern.finditer(config_text))
    if len(matches) > 1:
        raise ValueError(f"multiple Goal Ledger managed blocks in {config_path}")

    outside = pattern.sub("", config_text)
    for name in AGENT_NAMES:
        if re.search(rf"(?m)^\[agents\.{re.escape(name)}\]\s*$", outside):
            raise ValueError(
                f"refusing unmanaged [agents.{name}] registration in {config_path}"
            )

    block = managed_agent_block()
    if matches:
        existing = matches[0].group(0).rstrip("\n")
        if existing != block and not replace:
            raise FileExistsError(
                f"managed agent registration differs in {config_path}; rerun with --replace"
            )
        candidate = pattern.sub(block + "\n", config_text, count=1)
    else:
        prefix = config_text.rstrip()
        candidate = (prefix + "\n\n" if prefix else "") + block + "\n"
    _validate_toml(candidate, config_path)
    return candidate


def _config_without_agents(config_text: str, config_path: Path) -> str:
    _validate_toml(config_text, config_path)
    if config_text.count(MANAGED_BEGIN) != config_text.count(MANAGED_END):
        raise ValueError(f"unbalanced Goal Ledger managed markers in {config_path}")
    pattern = _managed_pattern()
    matches = list(pattern.finditer(config_text))
    if len(matches) > 1:
        raise ValueError(f"multiple Goal Ledger managed blocks in {config_path}")
    if not matches:
        return config_text
    candidate = pattern.sub("", config_text, count=1).rstrip() + "\n"
    _validate_toml(candidate, config_path)
    return candidate


def _toml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    raise TypeError(f"unsupported TOML scalar: {value!r}")


def multi_agent_config_problems(config_path: Path) -> list[str]:
    if not config_path.is_file():
        return [f"missing multi-agent configuration: {config_path}"]
    try:
        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"cannot validate multi-agent configuration {config_path}: {exc}"]
    section: object = parsed
    for part in MULTI_AGENT_SECTION.split("."):
        if not isinstance(section, dict) or part not in section:
            return [f"missing [{MULTI_AGENT_SECTION}] in {config_path}"]
        section = section[part]
    if not isinstance(section, dict):
        return [f"[{MULTI_AGENT_SECTION}] is not a table in {config_path}"]
    problems = []
    for key, expected in MULTI_AGENT_SETTINGS.items():
        actual = section.get(key)
        if actual != expected or type(actual) is not type(expected):
            problems.append(
                f"[{MULTI_AGENT_SECTION}] {key} must be {_toml_scalar(expected)}; "
                f"found {_toml_scalar(actual) if isinstance(actual, (bool, int, str)) else actual!r}"
            )
    return problems


def review_approval_config_problems(config_path: Path) -> list[str]:
    """Return configuration drift that prevents native owner approval UI."""
    if not config_path.is_file():
        return [f"missing external-review approval configuration: {config_path}"]
    try:
        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"cannot validate external-review approval configuration {config_path}: {exc}"]
    problems = []
    for key, expected in REVIEW_APPROVAL_SETTINGS.items():
        actual = parsed.get(key)
        if actual != expected:
            problems.append(
                f"root {key} must be {_toml_scalar(expected)} for native owner approval; "
                f"found {_toml_scalar(actual) if isinstance(actual, (bool, int, str)) else actual!r}"
            )
    return problems


def _config_with_review_approvals(config_text: str, config_path: Path) -> str:
    """Set only the two root approval keys, preserving every table and other key."""
    _validate_toml(config_text, config_path)
    first_table = re.search(r"(?m)^\s*\[", config_text)
    managed_marker = re.search(rf"(?m)^{re.escape(MANAGED_BEGIN)}$", config_text)
    boundaries = [
        match.start() for match in (first_table, managed_marker) if match is not None
    ]
    end = min(boundaries) if boundaries else len(config_text)
    root = config_text[:end]
    rest = config_text[end:]
    for key, value in REVIEW_APPROVAL_SETTINGS.items():
        pattern = re.compile(rf"(?m)^[ \t]*{re.escape(key)}[ \t]*=.*$")
        replacement = f"{key} = {_toml_scalar(value)}"
        if pattern.search(root):
            root = pattern.sub(replacement, root, count=1)
        else:
            root = root.rstrip() + ("\n" if root.strip() else "") + replacement + "\n"
    candidate = root.rstrip() + ("\n\n" if rest else "\n") + rest.lstrip("\n")
    _validate_toml(candidate, config_path)
    return candidate


def configure_review_approvals(codex_home: Path) -> list[Path]:
    """Configure native user approval for external review, preserving a backup."""
    codex_home = codex_home.expanduser().resolve()
    config_path = codex_home / "config.toml"
    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    candidate = _config_with_review_approvals(config_text, config_path)
    if candidate == config_text:
        return []
    changed: list[Path] = []
    if config_path.exists():
        backup = backup_path(config_path)
        shutil.copy2(config_path, backup)
        changed.append(backup)
    _atomic_write(config_path, candidate.encode("utf-8"))
    changed.append(config_path)
    return changed


def _config_with_multi_agent(config_text: str, config_path: Path, *, replace: bool) -> str:
    _validate_toml(config_text, config_path)
    problems = multi_agent_config_problems(config_path) if config_path.is_file() else ["missing"]
    if not problems:
        return config_text

    header_pattern = re.compile(rf"(?m)^\[{re.escape(MULTI_AGENT_SECTION)}\][ \t]*$")
    match = header_pattern.search(config_text)
    if match is None:
        prefix = config_text.rstrip()
        rows = [f"[{MULTI_AGENT_SECTION}]"] + [
            f"{key} = {_toml_scalar(value)}" for key, value in MULTI_AGENT_SETTINGS.items()
        ]
        candidate = (prefix + "\n\n" if prefix else "") + "\n".join(rows) + "\n"
        _validate_toml(candidate, config_path)
        return candidate
    if not replace:
        raise FileExistsError(
            f"[{MULTI_AGENT_SECTION}] differs from the Goal Ledger requirements in "
            f"{config_path}; rerun with --replace"
        )

    next_header = re.search(r"(?m)^\[[^\n]+\][ \t]*$", config_text[match.end() :])
    end = match.end() + next_header.start() if next_header else len(config_text)
    body = config_text[match.end() : end]
    for key, value in MULTI_AGENT_SETTINGS.items():
        pattern = re.compile(rf"(?m)^[ \t]*{re.escape(key)}[ \t]*=.*$")
        replacement = f"{key} = {_toml_scalar(value)}"
        if pattern.search(body):
            body = pattern.sub(replacement, body, count=1)
        else:
            body = body.rstrip() + "\n" + replacement + "\n"
    candidate = config_text[: match.end()] + body + config_text[end:]
    _validate_toml(candidate, config_path)
    return candidate


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


def agent_installation_problems(codex_home: Path) -> list[str]:
    codex_home = codex_home.expanduser().resolve()
    problems: list[str] = []
    for name in AGENT_NAMES:
        source = AGENT_SOURCE / f"{name}.toml"
        target = codex_home / "agents" / f"{name}.toml"
        if not target.is_file():
            problems.append(f"missing managed agent profile: {target}")
        elif target.read_bytes() != source.read_bytes():
            problems.append(f"stale managed agent profile: {target}")

    config_path = codex_home / "config.toml"
    if not config_path.is_file():
        problems.append(f"missing agent registration config: {config_path}")
        return problems
    config_text = config_path.read_text(encoding="utf-8")
    try:
        _validate_toml(config_text, config_path)
    except ValueError as exc:
        problems.append(str(exc))
        return problems
    matches = list(_managed_pattern().finditer(config_text))
    if len(matches) != 1:
        problems.append(f"missing exact Goal Ledger managed agent block: {config_path}")
    elif matches[0].group(0).rstrip("\n") != managed_agent_block():
        problems.append(f"stale Goal Ledger managed agent block: {config_path}")
    problems.extend(multi_agent_config_problems(config_path))
    return problems


def validate_agent_install(codex_home: Path, *, replace: bool) -> None:
    codex_home = codex_home.expanduser().resolve()
    agents_dir = codex_home / "agents"
    config_path = codex_home / "config.toml"
    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    candidate = _config_with_agents(config_text, config_path, replace=replace)
    _config_with_multi_agent(candidate, config_path, replace=replace)

    for name in AGENT_NAMES:
        source = AGENT_SOURCE / f"{name}.toml"
        target = agents_dir / f"{name}.toml"
        if not source.is_file():
            raise FileNotFoundError(f"missing shipped agent profile: {source}")
        try:
            shipped = tomllib.loads(source.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"invalid shipped agent profile {source}: {exc}") from exc
        expected = PROFILE_BY_NAME[name]
        if (
            shipped.get("name") != name
            or shipped.get("model") != expected.model
            or shipped.get("model_reasoning_effort") != expected.effort
        ):
            raise ValueError(
                f"shipped agent profile does not match the canonical manifest: {source}"
            )
        if target.exists() and (
            not target.is_file() or target.read_bytes() != source.read_bytes()
        ) and not replace:
            raise FileExistsError(
                f"{target} differs from the shipped profile; rerun with --replace"
            )


def install_agent_profiles(codex_home: Path, *, replace: bool) -> list[Path]:
    codex_home = codex_home.expanduser().resolve()
    validate_agent_install(codex_home, replace=replace)
    agents_dir = codex_home / "agents"
    config_path = codex_home / "config.toml"
    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    candidate = _config_with_agents(config_text, config_path, replace=replace)
    candidate = _config_with_multi_agent(candidate, config_path, replace=replace)

    changed: list[Path] = []
    agents_dir.mkdir(parents=True, exist_ok=True)
    for name in AGENT_NAMES:
        source = AGENT_SOURCE / f"{name}.toml"
        target = agents_dir / f"{name}.toml"
        data = source.read_bytes()
        if not target.is_file() or target.read_bytes() != data:
            if target.exists():
                backup = backup_path(target)
                os.replace(target, backup)
                changed.append(backup)
            _atomic_write(target, data)
            changed.append(target)

    if config_text != candidate:
        if config_path.exists():
            backup = backup_path(config_path)
            shutil.copy2(config_path, backup)
            changed.append(backup)
        _atomic_write(config_path, candidate.encode("utf-8"))
        changed.append(config_path)
    return changed


def uninstall_agent_profiles(codex_home: Path, *, force: bool) -> list[Path]:
    codex_home = codex_home.expanduser().resolve()
    removed: list[Path] = []
    for name in AGENT_NAMES:
        source = AGENT_SOURCE / f"{name}.toml"
        target = codex_home / "agents" / f"{name}.toml"
        if not target.exists():
            continue
        if not target.is_file():
            raise ValueError(f"managed agent path is not a regular file: {target}")
        if target.read_bytes() != source.read_bytes() and not force:
            raise FileExistsError(
                f"refusing to remove customized agent profile {target}; "
                "rerun with --force-agent-uninstall"
            )
        target.unlink()
        removed.append(target)

    config_path = codex_home / "config.toml"
    if config_path.is_file():
        config_text = config_path.read_text(encoding="utf-8")
        candidate = _config_without_agents(config_text, config_path)
        if candidate != config_text:
            backup = backup_path(config_path)
            shutil.copy2(config_path, backup)
            _atomic_write(config_path, candidate.encode("utf-8"))
            removed.append(config_path)
    return removed


def ignored(path: Path) -> bool:
    return any(part in IGNORED_NAMES for part in path.parts) or path.suffix in IGNORED_SUFFIXES


def package_files(root: Path) -> dict[Path, Path]:
    """Map managed repository-relative paths to source files."""
    files: dict[Path, Path] = {}
    for entry_name in PACKAGE_ENTRIES:
        entry = root / entry_name
        if entry.is_file():
            files[Path(entry_name)] = entry
            continue
        if not entry.is_dir():
            raise FileNotFoundError(f"missing package entry: {entry}")
        for path in sorted(entry.rglob("*")):
            relative = path.relative_to(root)
            if path.is_file() and not ignored(relative):
                files[relative] = path
    return files


def installation_problems(source: Path, destination: Path) -> list[str]:
    """Return exact managed-file drift without mutating either tree."""
    expected = package_files(source)
    if not destination.exists():
        return [f"missing installation: {destination}"]
    if destination.is_symlink() or not destination.is_dir():
        return [f"installation is not a regular directory: {destination}"]

    actual = package_files(destination)
    problems: list[str] = []
    for relative in sorted(expected.keys() - actual.keys()):
        problems.append(f"missing managed file: {relative.as_posix()}")
    for relative in sorted(actual.keys() - expected.keys()):
        problems.append(f"unexpected managed file: {relative.as_posix()}")
    for relative in sorted(expected.keys() & actual.keys()):
        if expected[relative].read_bytes() != actual[relative].read_bytes():
            problems.append(f"stale managed file: {relative.as_posix()}")
    return problems


def copy_package(source: Path, staging: Path) -> None:
    """Copy only the allow-listed skill package into an empty staging directory."""
    for entry_name in PACKAGE_ENTRIES:
        source_entry = source / entry_name
        destination_entry = staging / entry_name
        if source_entry.is_file():
            shutil.copy2(source_entry, destination_entry)
        else:
            shutil.copytree(
                source_entry,
                destination_entry,
                ignore=shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc", "*.pyo"),
            )


def backup_path(destination: Path) -> Path:
    """Choose a collision-free sibling backup path."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = destination.with_name(f"{destination.name}.backup-{timestamp}")
    suffix = 1
    while candidate.exists():
        candidate = destination.with_name(
            f"{destination.name}.backup-{timestamp}-{suffix}"
        )
        suffix += 1
    return candidate


def install(source: Path, destination: Path, *, replace: bool) -> tuple[Path, Path | None]:
    """Install transactionally and preserve a replaced installation as a backup."""
    source = source.resolve()
    destination = destination.expanduser().resolve()
    if source == destination:
        raise ValueError("source and destination must be different directories")
    package_files(source)
    if destination.is_symlink():
        raise ValueError(f"refusing to replace symlink destination: {destination}")

    if destination.exists():
        problems = installation_problems(source, destination)
        if not problems:
            return destination, None
        if not replace:
            raise FileExistsError(
                f"{destination} differs from this package; rerun with --replace to preserve "
                "the existing installation as a sibling backup"
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-install-", dir=destination.parent)
    )
    backup: Path | None = None
    try:
        copy_package(source, staging)
        staged_problems = installation_problems(source, staging)
        if staged_problems:
            raise OSError("staged package verification failed: " + "; ".join(staged_problems))

        if destination.exists():
            backup = backup_path(destination)
            os.replace(destination, backup)
        try:
            os.replace(staging, destination)
        except Exception:
            if backup is not None and backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return destination, backup


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install the portable codex-goal-ledger skill. Existing drift is preserved "
            "unless --replace is explicitly supplied."
        )
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=None,
        help="Skill directory; defaults to $CODEX_HOME/skills/codex-goal-ledger.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Verify exact managed files without changing the installation.",
    )
    mode.add_argument(
        "--replace",
        action="store_true",
        help="Replace drifted files after preserving the existing directory as a backup.",
    )
    parser.add_argument(
        "--with-agents",
        action="store_true",
        help="Also install or check Goal Ledger-owned Codex agent profiles and registrations.",
    )
    parser.add_argument(
        "--configure-review-approvals",
        action="store_true",
        help=(
            "Set root approvals_reviewer=\"user\" and approval_policy=\"on-request\" "
            "so exact Fable manifests can reach the native owner approval UI."
        ),
    )
    parser.add_argument(
        "--uninstall-agents",
        action="store_true",
        help="Remove only Goal Ledger-owned agent profiles and their managed config block.",
    )
    parser.add_argument(
        "--force-agent-uninstall",
        action="store_true",
        help="Allow --uninstall-agents to remove customized Goal Ledger agent profile files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    destination = args.destination or default_destination()
    try:
        if args.uninstall_agents:
            if args.check or args.with_agents or args.configure_review_approvals:
                raise ValueError(
                    "--uninstall-agents cannot be combined with --check, --with-agents, "
                    "or --configure-review-approvals"
                )
            removed = uninstall_agent_profiles(
                default_codex_home(), force=args.force_agent_uninstall
            )
            for path in removed:
                print(f"Removed or updated: {path}")
            if not removed:
                print("Goal Ledger agent profiles are not installed.")
            return 0
        if args.force_agent_uninstall:
            raise ValueError("--force-agent-uninstall requires --uninstall-agents")
        if args.check:
            problems = installation_problems(PACKAGE_ROOT, destination.expanduser().resolve())
            if args.with_agents:
                problems.extend(agent_installation_problems(default_codex_home()))
            if args.configure_review_approvals:
                problems.extend(
                    review_approval_config_problems(default_codex_home() / "config.toml")
                )
            if problems:
                for problem in problems:
                    print(f"error: {problem}", file=sys.stderr)
                return 1
            print(f"Installation is current: {destination.expanduser().resolve()}")
            if args.with_agents:
                print("Goal Ledger agent profiles and registrations are current.")
            if args.configure_review_approvals:
                print("External-review owner approval configuration is current.")
            return 0

        if args.with_agents:
            # Fail on config/profile drift before replacing an otherwise installable skill.
            validate_agent_install(default_codex_home(), replace=args.replace)
        installed, backup = install(PACKAGE_ROOT, destination, replace=args.replace)
        agent_changes = (
            install_agent_profiles(default_codex_home(), replace=args.replace)
            if args.with_agents
            else []
        )
        review_approval_changes = (
            configure_review_approvals(default_codex_home())
            if args.configure_review_approvals
            else []
        )
    except (FileExistsError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if backup is None:
        print(f"Installed: {installed}")
    else:
        print(f"Installed: {installed}")
        print(f"Preserved previous installation: {backup}")
    for path in agent_changes:
        print(f"Agent install change: {path}")
    for path in review_approval_changes:
        print(f"Review approval config change: {path}")
    if args.with_agents or review_approval_changes:
        print(
            "Restart Codex or open a new task before checking session-visible agent roles "
            "or native owner approval routing."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
