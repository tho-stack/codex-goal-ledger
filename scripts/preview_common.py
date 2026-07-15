#!/usr/bin/env python3
"""Shared preview-server state helpers for Codex Goal Ledger."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from ledger_common import LedgerError


PREVIEW_STATE_PATH = Path("evidence/preview-server.json")
PREVIEW_STATES = {"starting", "running", "stopped", "failed", "stale"}
PREVIEW_TRANSPORTS = {"tailscale", "localhost"}


@dataclass(frozen=True)
class PreviewState:
    state: str
    transport: str
    bind_host: str
    display_host: str
    port: int
    url: str
    health_url: str
    pid: int
    started_at: str
    last_health_check: str
    stopped_at: str
    detail: str


def preview_state_path(goal_dir: Path) -> Path:
    return goal_dir.resolve() / PREVIEW_STATE_PATH


def load_preview_state(goal_dir: Path) -> PreviewState | None:
    path = preview_state_path(goal_dir)
    if not path.exists():
        return None
    if not path.is_file():
        raise LedgerError(f"preview state is not a regular file: {path}")
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LedgerError(f"invalid preview state JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LedgerError(f"preview state must be a JSON object: {path}")

    required = {
        "state",
        "transport",
        "bind_host",
        "display_host",
        "port",
        "url",
        "health_url",
        "pid",
        "started_at",
        "last_health_check",
        "stopped_at",
        "detail",
    }
    if set(value) != required:
        raise LedgerError(f"preview state has an invalid field set: {path}")
    if value["state"] not in PREVIEW_STATES:
        raise LedgerError(f"preview state has invalid state {value['state']!r}: {path}")
    if value["transport"] not in PREVIEW_TRANSPORTS:
        raise LedgerError(
            f"preview state has invalid transport {value['transport']!r}: {path}"
        )
    if not isinstance(value["port"], int) or not 1 <= value["port"] <= 65535:
        raise LedgerError(f"preview state has invalid port: {path}")
    if not isinstance(value["pid"], int) or value["pid"] <= 0:
        raise LedgerError(f"preview state has invalid pid: {path}")
    for key in required - {"port", "pid"}:
        if not isinstance(value[key], str):
            raise LedgerError(f"preview state field {key} must be a string: {path}")
    if not value["url"].startswith("http://") or value["url"].startswith("file://"):
        raise LedgerError(f"preview state URL must use HTTP: {path}")
    if not value["health_url"].startswith("http://"):
        raise LedgerError(f"preview health URL must use HTTP: {path}")
    return PreviewState(**value)
