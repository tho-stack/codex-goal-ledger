#!/usr/bin/env python3
"""Symlink-safe reads and atomic replacement for Goal Ledger managed files."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import tempfile

from ledger_common import LedgerError


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def _managed_relative(path: Path, root: Path, *, label: str) -> tuple[Path, Path]:
    """Return canonical lexical paths while requiring a trusted non-symlink root."""
    absolute_root = _absolute(root)
    try:
        resolved_root = absolute_root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise LedgerError(f"missing managed root for {label}: {absolute_root}") from exc
    if resolved_root != absolute_root:
        raise LedgerError(
            f"managed root for {label} must be canonical and non-symlinked: {absolute_root}"
        )
    root_metadata = _lstat(absolute_root)
    if root_metadata is None or not stat.S_ISDIR(root_metadata.st_mode):
        raise LedgerError(f"managed root for {label} is not a directory: {absolute_root}")

    absolute_path = _absolute(path)
    try:
        relative = absolute_path.relative_to(absolute_root)
    except ValueError as exc:
        raise LedgerError(
            f"{label} escapes its managed root {absolute_root}: {absolute_path}"
        ) from exc
    return absolute_root, relative


def _existing_entry(
    path: Path,
    *,
    root: Path,
    label: str,
) -> tuple[Path, os.stat_result | None]:
    """Inspect a leaf after rejecting every symlink or invalid ancestor beneath root."""
    absolute_root, relative = _managed_relative(path, root, label=label)
    if relative == Path("."):
        metadata = _lstat(absolute_root)
        assert metadata is not None
        return absolute_root, metadata

    current = absolute_root
    parts = relative.parts
    for index, part in enumerate(parts):
        current /= part
        metadata = _lstat(current)
        final = index == len(parts) - 1
        if metadata is None:
            return current, None
        if stat.S_ISLNK(metadata.st_mode):
            role = label if final else f"{label} ancestor"
            raise LedgerError(f"{role} must not be a symlink: {current}")
        if not final and not stat.S_ISDIR(metadata.st_mode):
            raise LedgerError(f"{label} ancestor is not a directory: {current}")
        if final:
            return current, metadata
    raise AssertionError("managed path inspection produced no leaf")


def normalize_managed_goal_dir(path: Path) -> Path:
    """Normalize docs/goals/<slug> while rejecting symlinks inside the project root."""
    lexical = _absolute(path)
    if lexical.parent.name != "goals" or lexical.parent.parent.name != "docs":
        raise LedgerError(f"goal directory must be docs/goals/<slug>: {lexical}")
    lexical_root = lexical.parent.parent.parent
    try:
        trusted_root = lexical_root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise LedgerError(f"missing project root for goal directory: {lexical_root}") from exc
    candidate = trusted_root / lexical.relative_to(lexical_root)
    require_managed_directory(
        candidate,
        root=trusted_root,
        label="managed goal directory",
    )
    return candidate


def managed_path_exists(path: Path, *, root: Path, label: str) -> bool:
    """Return whether a safe directory entry exists without following symlinks."""
    _, metadata = _existing_entry(path, root=root, label=label)
    return metadata is not None


def require_managed_directory(
    path: Path,
    *,
    root: Path,
    label: str,
    create: bool = False,
) -> None:
    """Require a real directory path, creating each checked component when requested."""
    absolute_root, relative = _managed_relative(path, root, label=label)
    current = absolute_root
    if relative == Path("."):
        return
    for index, part in enumerate(relative.parts):
        current /= part
        metadata = _lstat(current)
        final = index == len(relative.parts) - 1
        if metadata is None:
            if not create:
                raise LedgerError(f"missing {label}: {current}")
            current.mkdir()
            metadata = _lstat(current)
            if metadata is None:
                raise LedgerError(f"could not create {label}: {current}")
        if stat.S_ISLNK(metadata.st_mode):
            role = label if final else f"{label} ancestor"
            raise LedgerError(f"{role} must not be a symlink: {current}")
        if not stat.S_ISDIR(metadata.st_mode):
            role = label if final else f"{label} ancestor"
            raise LedgerError(f"{role} is not a directory: {current}")


def require_managed_regular_file(path: Path, *, root: Path, label: str) -> None:
    """Require a regular non-symlink file without reading its contents."""
    absolute_path, metadata = _existing_entry(path, root=root, label=label)
    if metadata is None:
        raise LedgerError(f"missing {label}: {absolute_path}")
    if not stat.S_ISREG(metadata.st_mode):
        raise LedgerError(f"{label} is not a regular file: {absolute_path}")


def read_managed_bytes(
    path: Path,
    *,
    root: Path,
    label: str,
    missing_ok: bool = False,
) -> bytes | None:
    """Read a stable regular file while refusing to follow a final symlink."""
    absolute_path, metadata = _existing_entry(path, root=root, label=label)
    if metadata is None:
        if missing_ok:
            return None
        raise LedgerError(f"missing {label}: {absolute_path}")
    if not stat.S_ISREG(metadata.st_mode):
        raise LedgerError(f"{label} is not a regular file: {absolute_path}")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute_path, flags)
    except OSError as exc:
        raise LedgerError(
            f"could not safely open {label}: {absolute_path}: {exc}"
        ) from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise LedgerError(f"{label} changed while being opened: {absolute_path}")
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise LedgerError(f"{label} changed while being opened: {absolute_path}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def read_managed_text(
    path: Path,
    *,
    root: Path,
    label: str,
    encoding: str = "utf-8",
) -> str:
    """Read a managed regular text file without following a symlink."""
    data = read_managed_bytes(path, root=root, label=label)
    assert data is not None
    return data.decode(encoding)


def atomic_replace_managed(
    path: Path,
    data: bytes,
    *,
    root: Path,
    label: str,
) -> None:
    """Atomically replace a managed regular file without following symlink targets."""
    require_managed_directory(
        path.parent,
        root=root,
        label=f"{label} parent directory",
        create=True,
    )
    absolute_path, existing = _existing_entry(path, root=root, label=label)
    if existing is not None:
        if not stat.S_ISREG(existing.st_mode):
            raise LedgerError(f"{label} is not a regular file: {absolute_path}")
        mode = stat.S_IMODE(existing.st_mode)
    else:
        mode = 0o644

    with tempfile.NamedTemporaryFile(
        dir=absolute_path.parent,
        prefix=f".{absolute_path.name}.",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.chmod(temporary, mode)
        os.replace(temporary, absolute_path)
    finally:
        temporary.unlink(missing_ok=True)
