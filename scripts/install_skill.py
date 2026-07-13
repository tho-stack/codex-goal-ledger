#!/usr/bin/env python3
"""Install the Codex Goal Ledger skill from this repository."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sys
import tempfile


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "codex-goal-ledger"
PACKAGE_ENTRIES = ("SKILL.md", "agents", "assets", "references", "scripts")
IGNORED_NAMES = frozenset({".DS_Store", "__pycache__"})
IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})


def default_destination() -> Path:
    """Return the portable Codex skill destination."""
    configured = os.environ.get("CODEX_HOME")
    codex_home = Path(configured).expanduser() if configured else Path.home() / ".codex"
    return codex_home / "skills" / SKILL_NAME


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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    destination = args.destination or default_destination()
    try:
        if args.check:
            problems = installation_problems(PACKAGE_ROOT, destination.expanduser().resolve())
            if problems:
                for problem in problems:
                    print(f"error: {problem}", file=sys.stderr)
                return 1
            print(f"Installation is current: {destination.expanduser().resolve()}")
            return 0

        installed, backup = install(PACKAGE_ROOT, destination, replace=args.replace)
    except (FileExistsError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if backup is None:
        print(f"Installed: {installed}")
    else:
        print(f"Installed: {installed}")
        print(f"Preserved previous installation: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
