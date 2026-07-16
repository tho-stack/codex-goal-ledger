#!/usr/bin/env python3
"""Serve one generated Goal Ledger dashboard over Tailscale or localhost HTTP."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
from typing import Any
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

from ledger_common import LedgerError, project_root_for
from managed_files import (
    atomic_replace_managed,
    normalize_managed_goal_dir,
    read_managed_bytes,
    require_managed_directory,
    require_managed_regular_file,
)
from preview_common import PREVIEW_HEALTH_PATH, preview_state_path
from render_goal import build_dashboard


HEALTH_PATH = PREVIEW_HEALTH_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def detect_tailscale(command: str = "tailscale") -> tuple[str, str] | None:
    executable = shutil.which(command)
    if executable is None:
        return None
    result = subprocess.run(
        [executable, "status", "--json"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        payload: Any = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("BackendState") != "Running":
        return None
    own = payload.get("Self")
    if not isinstance(own, dict) or own.get("Online") is False:
        return None
    addresses = own.get("TailscaleIPs")
    if not isinstance(addresses, list):
        return None
    ipv4 = None
    for address in addresses:
        if not isinstance(address, str):
            continue
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            continue
        if parsed.version == 4:
            ipv4 = address
            break
    if ipv4 is None:
        return None
    dns_name = own.get("DNSName")
    display = dns_name.rstrip(".") if isinstance(dns_name, str) and dns_name else ipv4
    return ipv4, display


def choose_endpoint(mode: str, tailscale_command: str) -> tuple[str, str, str]:
    if mode in {"auto", "tailscale"}:
        endpoint = detect_tailscale(tailscale_command)
        if endpoint is not None:
            bind_host, display_host = endpoint
            return "tailscale", bind_host, display_host
        if mode == "tailscale":
            raise LedgerError("Tailscale is unavailable or not connected")
    return "localhost", "127.0.0.1", "127.0.0.1"


class GoalLedgerHandler(SimpleHTTPRequestHandler):
    server_version = "GoalLedgerPreview/1"

    def __init__(
        self,
        *args: object,
        directory: str,
        health: dict[str, object],
        shared_assets: dict[str, Path],
        managed_root: Path,
        **kwargs: object,
    ):
        self.health = health
        self.goal_root = Path(directory).resolve()
        self.shared_assets = shared_assets
        self.managed_root = managed_root
        super().__init__(*args, directory=directory, **kwargs)

    def request_path(self) -> str:
        return unquote(urlsplit(self.path).path)

    def serve_shared_asset(self, *, head_only: bool = False) -> bool:
        request_path = self.request_path()
        asset = self.shared_assets.get(request_path)
        if asset is None:
            if request_path.startswith("/assets/"):
                self.send_error(404, "Shared preview asset is not allow-listed")
                return True
            return False
        try:
            payload = read_managed_bytes(
                asset,
                root=self.managed_root,
                label=f"managed shared preview asset {asset.name}",
            )
            assert payload is not None
        except (LedgerError, OSError):
            self.send_error(404, "Shared preview asset is unavailable")
            return True
        content_type = {
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
        }.get(asset.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if not head_only:
            self.wfile.write(payload)
        return True

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.request_path() == HEALTH_PATH:
            payload = json.dumps(self.health, sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.serve_shared_asset():
            return
        try:
            require_managed_regular_file(
                self.goal_root / "index.html",
                root=self.goal_root,
                label="managed dashboard",
            )
        except LedgerError:
            self.send_error(403, "Managed dashboard is unavailable")
            return
        target = Path(self.translate_path(self.path)).resolve()
        try:
            target.relative_to(self.goal_root)
        except ValueError:
            self.send_error(403, "Preview paths must remain inside the goal directory")
            return
        super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.serve_shared_asset(head_only=True):
            return
        try:
            require_managed_regular_file(
                self.goal_root / "index.html",
                root=self.goal_root,
                label="managed dashboard",
            )
        except LedgerError:
            self.send_error(403, "Managed dashboard is unavailable")
            return
        target = Path(self.translate_path(self.path)).resolve()
        try:
            target.relative_to(self.goal_root)
        except ValueError:
            self.send_error(403, "Preview paths must remain inside the goal directory")
            return
        super().do_HEAD()

    def log_message(self, format: str, *args: object) -> None:
        print(f"preview: {format % args}", file=sys.stderr)


def start_server(
    goal_dir: Path,
    *,
    bind_host: str,
    display_host: str,
    transport: str,
    requested_port: int,
    attempts: int = 20,
) -> tuple[ThreadingHTTPServer, dict[str, object]]:
    goal_dir = normalize_managed_goal_dir(goal_dir)
    slug = goal_dir.name
    project_root = project_root_for(goal_dir)
    assets_root = (project_root / "docs" / "assets").resolve()
    require_managed_directory(
        project_root / "docs" / "assets",
        root=project_root,
        label="managed shared asset directory",
    )
    shared_assets = {
        "/assets/goal-ledger.css": assets_root / "goal-ledger.css",
        "/assets/goal-ledger.js": assets_root / "goal-ledger.js",
    }
    require_managed_regular_file(
        goal_dir / "index.html",
        root=goal_dir,
        label="managed dashboard",
    )
    for asset in shared_assets.values():
        require_managed_regular_file(
            asset,
            root=project_root,
            label=f"managed shared preview asset {asset.name}",
        )
    health: dict[str, object] = {"ok": True, "goal_slug": slug, "transport": transport}
    handler = partial(
        GoalLedgerHandler,
        directory=str(goal_dir),
        health=health,
        shared_assets=shared_assets,
        managed_root=project_root,
    )
    ports = (
        [requested_port]
        if requested_port == 0
        else range(requested_port, min(65536, requested_port + attempts))
    )
    last_error: OSError | None = None
    for port in ports:
        try:
            server = ThreadingHTTPServer((bind_host, port), handler)
            server.daemon_threads = True
            actual_port = int(server.server_address[1])
            url = f"http://{display_host}:{actual_port}/"
            health.update({"url": url, "port": actual_port})
            return server, health
        except OSError as exc:
            last_error = exc
            if exc.errno not in {48, 98, 10048}:
                raise
    raise LedgerError(
        f"no preview port available from {requested_port} through "
        f"{requested_port + attempts - 1}: {last_error}"
    )


def atomic_json(path: Path, payload: dict[str, object], *, root: Path) -> None:
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_replace_managed(
        path,
        data,
        root=root,
        label="managed preview state",
    )


def render_with_state(goal_dir: Path) -> None:
    goal_dir = normalize_managed_goal_dir(goal_dir)
    atomic_replace_managed(
        goal_dir / "index.html",
        build_dashboard(goal_dir),
        root=goal_dir,
        label="managed dashboard",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve one docs/goals/<slug> dashboard over HTTP; never emit file:// URLs."
    )
    parser.add_argument("goal_dir", type=Path)
    parser.add_argument("--host-mode", choices=("auto", "tailscale", "localhost"), default="auto")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--tailscale-bin", default="tailscale")
    parser.add_argument("--check", action="store_true", help="Check the recorded health URL and exit.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        goal_dir = normalize_managed_goal_dir(args.goal_dir)
        project_root_for(goal_dir)
        if args.check:
            from preview_common import load_preview_state

            state = load_preview_state(goal_dir)
            if state is None:
                raise LedgerError("preview server has not been started")
            try:
                with urlopen(state.health_url, timeout=3) as response:
                    payload = json.load(response)
            except Exception as exc:
                raise LedgerError(f"preview health check failed for {state.health_url}: {exc}") from exc
            expected_health = {
                "ok": True,
                "goal_slug": goal_dir.name,
                "transport": state.transport,
                "url": state.url,
                "port": state.port,
            }
            if response.status != 200 or not isinstance(payload, dict) or any(
                payload.get(key) != expected for key, expected in expected_health.items()
            ):
                raise LedgerError(f"preview health check returned an invalid response: {state.health_url}")
            print(f"Preview is healthy: {state.url}")
            return 0
        if not 0 <= args.port <= 65535:
            raise LedgerError("port must be between 0 and 65535")
        require_managed_regular_file(
            goal_dir / "index.html",
            root=goal_dir,
            label="managed dashboard",
        )

        transport, bind_host, display_host = choose_endpoint(
            args.host_mode, args.tailscale_bin
        )
        try:
            server, health = start_server(
                goal_dir,
                bind_host=bind_host,
                display_host=display_host,
                transport=transport,
                requested_port=args.port,
            )
        except OSError:
            if args.host_mode != "auto" or transport != "tailscale":
                raise
            transport, bind_host, display_host = "localhost", "127.0.0.1", "127.0.0.1"
            server, health = start_server(
                goal_dir,
                bind_host=bind_host,
                display_host=display_host,
                transport=transport,
                requested_port=args.port,
            )

        port = int(server.server_address[1])
        url = str(health["url"])
        health_url = f"http://{bind_host}:{port}{HEALTH_PATH}"
        started = utc_now()
        state: dict[str, object] = {
            "state": "starting",
            "transport": transport,
            "bind_host": bind_host,
            "display_host": display_host,
            "port": port,
            "url": url,
            "health_url": health_url,
            "pid": os.getpid(),
            "started_at": started,
            "last_health_check": "",
            "stopped_at": "",
            "detail": "Waiting for initial HTTP health check.",
        }
        state_path = preview_state_path(goal_dir)
        atomic_json(state_path, state, root=goal_dir)
        render_with_state(goal_dir)

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(health_url, timeout=3) as response:
                payload = json.load(response)
            if response.status != 200 or payload.get("ok") is not True:
                raise LedgerError("initial preview health check returned an invalid response")
            state.update(
                {
                    "state": "running",
                    "last_health_check": utc_now(),
                    "detail": "Initial HTTP health check passed; recheck before claiming the endpoint is still live.",
                }
            )
            atomic_json(state_path, state, root=goal_dir)
            render_with_state(goal_dir)
            print(f"Preview URL: {url}", flush=True)
            print(f"Transport: {transport}; bind: {bind_host}:{port}", flush=True)
            stop = threading.Event()

            def request_stop(_signum: int, _frame: object) -> None:
                stop.set()

            signal.signal(signal.SIGTERM, request_stop)
            signal.signal(signal.SIGINT, request_stop)
            while not stop.wait(0.5):
                if not thread.is_alive():
                    raise LedgerError("preview server stopped unexpectedly")
            return 0
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
            state.update(
                {
                    "state": "stopped",
                    "stopped_at": utc_now(),
                    "detail": "Preview process stopped; restart and health-check before using this URL.",
                }
            )
            atomic_json(state_path, state, root=goal_dir)
            render_with_state(goal_dir)
    except (LedgerError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
