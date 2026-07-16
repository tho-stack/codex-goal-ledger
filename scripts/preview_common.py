#!/usr/bin/env python3
"""Shared preview-server state helpers for Codex Goal Ledger."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
import re
from typing import Any

from ledger_common import LedgerError


PREVIEW_STATE_PATH = Path("evidence/preview-server.json")
PREVIEW_HEALTH_PATH = "/__goal_ledger_health__"
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
    bind_host = value["bind_host"]
    display_host = value["display_host"]
    transport = value["transport"]
    try:
        bind_address = ipaddress.ip_address(bind_host)
    except ValueError as exc:
        raise LedgerError(f"preview state bind_host must be an IP address: {path}") from exc
    if bind_address.version != 4:
        raise LedgerError(f"preview state bind_host must be IPv4: {path}")
    if transport == "localhost":
        if bind_host != "127.0.0.1" or display_host != "127.0.0.1":
            raise LedgerError(f"localhost preview state must use 127.0.0.1: {path}")
    else:
        if bind_address not in ipaddress.ip_network("100.64.0.0/10"):
            raise LedgerError(f"Tailscale preview state must use a Tailscale IPv4 address: {path}")
        display_is_magicdns = bool(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.ts\.net", display_host)
        )
        if display_host != bind_host and not display_is_magicdns:
            raise LedgerError(
                f"Tailscale preview display_host must be its bind IP or MagicDNS name: {path}"
            )
    expected_url = f"http://{display_host}:{value['port']}/"
    expected_health_url = f"http://{bind_host}:{value['port']}{PREVIEW_HEALTH_PATH}"
    if value["url"] != expected_url:
        raise LedgerError(f"preview state URL does not match its validated endpoint: {path}")
    if value["health_url"] != expected_health_url:
        raise LedgerError(f"preview health URL does not match its validated endpoint: {path}")
    return PreviewState(**value)
