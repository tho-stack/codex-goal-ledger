#!/usr/bin/env python3
"""Behavioral tests for the HTTP dashboard preview server."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import serve_dashboard  # noqa: E402
from ledger_common import LedgerError  # noqa: E402
from preview_common import load_preview_state  # noqa: E402


class PreviewServerTests(unittest.TestCase):
    maxDiff = 4000

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="goal-ledger-preview-")
        self.project = Path(self.temporary.name)
        initialized = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "init_goal.py"),
                "--project-root",
                str(self.project),
                "--slug",
                "preview-test",
                "--title",
                "Preview Test",
                "--why",
                "Verify a browser-safe dashboard URL.",
                "--outcome",
                "The dashboard is available over HTTP.",
                "--fable-feedback",
                "no",
                "--pro-review",
                "no",
                "--external-review-prompt",
                "no",
                "--codex-review",
                "no",
                "--clean-session-handoff",
                "no",
                "--date",
                "2026-07-14",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, initialized.returncode, initialized.stderr)
        self.goal_dir = self.project / "docs" / "goals" / "preview-test"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_localhost_server_health_preview_state_and_path_boundary(self) -> None:
        outside = self.project / "outside-secret.txt"
        outside.write_text("not served\n", encoding="utf-8")
        (self.goal_dir / "outside-link.txt").symlink_to(outside)
        process = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPT_DIR / "serve_dashboard.py"),
                str(self.goal_dir),
                "--host-mode",
                "localhost",
                "--port",
                "0",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            state = None
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    self.fail(f"preview exited early\nstdout:\n{stdout}\nstderr:\n{stderr}")
                try:
                    state = load_preview_state(self.goal_dir)
                except Exception:
                    state = None
                if state is not None and state.state == "running":
                    break
                time.sleep(0.05)
            self.assertIsNotNone(state)
            assert state is not None
            self.assertEqual("localhost", state.transport)
            self.assertTrue(state.url.startswith("http://127.0.0.1:"))
            self.assertNotIn("file://", state.url)

            with urlopen(state.url, timeout=3) as response:
                html = response.read().decode("utf-8")
            self.assertEqual(200, response.status)
            self.assertIn("Preview Test", html)
            self.assertIn(state.url, html)
            with urlopen(state.health_url, timeout=3) as response:
                health = json.load(response)
            self.assertTrue(health["ok"])
            checked = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "serve_dashboard.py"),
                    str(self.goal_dir),
                    "--check",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, checked.returncode, checked.stderr)
            self.assertIn("Preview is healthy", checked.stdout)

            with urlopen(state.url + "assets/goal-ledger.css", timeout=3) as response:
                css = response.read().decode("utf-8")
            self.assertEqual(200, response.status)
            self.assertIn(".instrument-strip", css)
            self.assertEqual("text/css; charset=utf-8", response.headers["Content-Type"])

            with urlopen(state.url + "assets/goal-ledger.js", timeout=3) as response:
                javascript = response.read().decode("utf-8")
            self.assertEqual(200, response.status)
            self.assertIn("data-theme-toggle", javascript)

            with self.assertRaises(HTTPError) as blocked_asset:
                urlopen(state.url + "assets/not-allow-listed.txt", timeout=3)
            self.assertEqual(404, blocked_asset.exception.code)
            blocked_asset.exception.close()

            with self.assertRaises(HTTPError) as blocked:
                urlopen(state.url + "outside-link.txt", timeout=3)
            self.assertEqual(403, blocked.exception.code)
            blocked.exception.close()
        finally:
            process.terminate()
            stdout, stderr = process.communicate(timeout=8)
        self.assertEqual(0, process.returncode, f"stdout:\n{stdout}\nstderr:\n{stderr}")
        stopped = load_preview_state(self.goal_dir)
        self.assertIsNotNone(stopped)
        assert stopped is not None
        self.assertEqual("stopped", stopped.state)
        self.assertIn("restart", stopped.detail.casefold())

    def test_tailscale_discovery_prefers_connected_ipv4_and_magicdns(self) -> None:
        payload = {
            "BackendState": "Running",
            "Self": {
                "Online": True,
                "TailscaleIPs": ["not-an-address", "100.88.77.66", "fd7a:115c:a1e0::1"],
                "DNSName": "preview.example.ts.net.",
            },
        }
        completed = subprocess.CompletedProcess(
            ["tailscale", "status", "--json"], 0, json.dumps(payload), ""
        )
        with mock.patch.object(serve_dashboard.shutil, "which", return_value="/bin/tailscale"), mock.patch.object(
            serve_dashboard.subprocess, "run", return_value=completed
        ):
            self.assertEqual(
                ("100.88.77.66", "preview.example.ts.net"),
                serve_dashboard.detect_tailscale(),
            )
            self.assertEqual(
                ("tailscale", "100.88.77.66", "preview.example.ts.net"),
                serve_dashboard.choose_endpoint("auto", "tailscale"),
            )

    def test_server_rejects_symlinked_shared_asset_before_binding(self) -> None:
        outside = self.project / "outside-shared-asset.txt"
        outside.write_text("private preview data\n", encoding="utf-8")
        asset = self.project / "docs" / "assets" / "goal-ledger.css"
        asset.unlink()
        asset.symlink_to(outside)

        with self.assertRaisesRegex(LedgerError, "must not be a symlink"):
            serve_dashboard.start_server(
                self.goal_dir,
                bind_host="127.0.0.1",
                display_host="127.0.0.1",
                transport="localhost",
                requested_port=0,
            )
        self.assertEqual("private preview data\n", outside.read_text(encoding="utf-8"))

    def test_preview_state_render_rejects_symlinked_dashboard_without_overwrite(self) -> None:
        outside = self.project / "outside-dashboard.html"
        outside.write_text("preserve dashboard target\n", encoding="utf-8")
        dashboard = self.goal_dir / "index.html"
        dashboard.unlink()
        dashboard.symlink_to(outside)

        with self.assertRaisesRegex(LedgerError, "must not be a symlink"):
            serve_dashboard.render_with_state(self.goal_dir)
        self.assertEqual(
            "preserve dashboard target\n",
            outside.read_text(encoding="utf-8"),
        )
        self.assertTrue(dashboard.is_symlink())

    def test_port_collision_selects_the_next_available_port(self) -> None:
        occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        port = occupied.getsockname()[1]
        server = None
        try:
            server, _ = serve_dashboard.start_server(
                self.goal_dir,
                bind_host="127.0.0.1",
                display_host="127.0.0.1",
                transport="localhost",
                requested_port=port,
                attempts=3,
            )
            self.assertNotEqual(port, server.server_address[1])
        finally:
            occupied.close()
            if server is not None:
                server.server_close()

    def test_preview_state_rejects_noncanonical_health_target(self) -> None:
        state_path = self.goal_dir / "evidence" / "preview-server.json"
        state_path.write_text(
            json.dumps(
                {
                    "state": "running",
                    "transport": "localhost",
                    "bind_host": "127.0.0.1",
                    "display_host": "127.0.0.1",
                    "port": 4173,
                    "url": "http://127.0.0.1:4173/",
                    "health_url": "http://169.254.169.254/latest/meta-data/",
                    "pid": 1,
                    "started_at": "2026-07-15T00:00:00Z",
                    "last_health_check": "",
                    "stopped_at": "",
                    "detail": "forged",
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(LedgerError, "health URL does not match"):
            load_preview_state(self.goal_dir)


if __name__ == "__main__":
    unittest.main(verbosity=2)
