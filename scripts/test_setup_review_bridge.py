#!/usr/bin/env python3
"""Behavioral tests for the idempotent review-bridge machine bootstrap."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from setup_review_bridge import (
    SetupPaths,
    _profile_tunnel_id,
    configure_profile,
    profile_problems,
    record_chatgpt_app,
    setup_status,
    start_runtime,
    status_problems,
    store_clipboard_key,
)


TUNNEL_ID = "tunnel_0123456789abcdef"
CONNECTOR_ID = "asdk_app_0123456789abcdef"


class ReviewBridgeSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="goal-ledger-bridge-setup-")
        self.root = Path(self.temporary.name)
        self.paths = SetupPaths(self.root / "profiles", self.root / "state")
        self.tunnel_client = self._write_executable(
            "tunnel-client",
            r"""#!/usr/bin/env python3
import json
from pathlib import Path
import sys

args = sys.argv[1:]
if args[0] == "init":
    def value(flag):
        return args[args.index(flag) + 1]
    profile_dir = Path(value("--profile-dir"))
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile = profile_dir / (value("--profile") + ".yaml")
    profile.write_text(
        'control_plane:\n'
        f'  tunnel_id: "{value("--tunnel-id")}"\n'
        '  api_key: "env:CONTROL_PLANE_API_KEY"\n'
        'mcp:\n'
        f'  command: "{value("--mcp-command")}"\n',
        encoding="utf-8",
    )
elif args[:2] == ["runtimes", "connect"] or args[:2] == ["runtimes", "status"]:
    print(json.dumps({"process_running": True, "healthy": True, "ready": True}))
elif args[0] == "doctor":
    print("RESULT ok")
else:
    raise SystemExit(2)
""",
        )
        self.security = self._write_executable(
            "security",
            """#!/usr/bin/env python3
import sys
if "find-generic-password" in sys.argv and "-w" in sys.argv:
    print("sk-proj-" + "x" * 80)
raise SystemExit(0)
""",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_executable(self, name: str, text: str) -> str:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return str(path)

    def test_profile_configuration_and_runtime_start_are_idempotent(self) -> None:
        configure_profile(
            tunnel_client_bin=self.tunnel_client,
            paths=self.paths,
            tunnel_id=TUNNEL_ID,
            replace=False,
        )
        self.assertEqual([], profile_problems(self.paths.profile_path, TUNNEL_ID))
        self.assertNotIn("sk-proj-", self.paths.profile_path.read_text())

        configure_profile(
            tunnel_client_bin=self.tunnel_client,
            paths=self.paths,
            tunnel_id=TUNNEL_ID,
            replace=False,
        )
        with patch("setup_review_bridge.sys.platform", "darwin"):
            runtime = start_runtime(
                tunnel_client_bin=self.tunnel_client,
                security_bin=self.security,
                keychain_service="test-goal-ledger",
                paths=self.paths,
            )
        self.assertTrue(runtime["process_running"])
        self.assertTrue(runtime["healthy"])
        self.assertTrue(runtime["ready"])

    def test_tunnel_id_is_read_from_current_json_profile_format(self) -> None:
        self.paths.profile_dir.mkdir(parents=True)
        self.paths.profile_path.write_text(
            json.dumps({"control_plane": {"tunnel_id": TUNNEL_ID}}),
            encoding="utf-8",
        )
        self.assertEqual(TUNNEL_ID, _profile_tunnel_id(self.paths.profile_path))

    def test_clipboard_key_is_saved_and_clipboard_is_cleared(self) -> None:
        pbpaste = self._write_executable(
            "pbpaste", '#!/bin/sh\nprintf "sk-proj-%080d" 0\n'
        )
        cleared = self.root / "clipboard-cleared"
        pbcopy = self._write_executable(
            "pbcopy", f'#!/bin/sh\ncat > "{cleared}"\n'
        )
        with patch("setup_review_bridge.sys.platform", "darwin"):
            store_clipboard_key(
                security_bin=self.security,
                pbpaste_bin=pbpaste,
                pbcopy_bin=pbcopy,
                service="test-goal-ledger",
            )
        self.assertTrue(cleared.is_file())
        self.assertEqual(b"", cleared.read_bytes())

    def test_visible_app_record_is_required_for_complete_check(self) -> None:
        configure_profile(
            tunnel_client_bin=self.tunnel_client,
            paths=self.paths,
            tunnel_id=TUNNEL_ID,
            replace=False,
        )
        environment = os.environ.copy()
        environment["PATH"] = str(self.root) + os.pathsep + environment.get("PATH", "")
        with patch.dict(os.environ, environment, clear=True), patch(
            "setup_review_bridge.sys.platform", "darwin"
        ):
            status = setup_status(
                tunnel_client_bin=self.tunnel_client,
                security_bin=self.security,
                keychain_service="test-goal-ledger",
                paths=self.paths,
            )
        self.assertIn(
            "verified ChatGPT Goal Ledger app connection is not recorded",
            status_problems(status, require_app=True),
        )

        record_chatgpt_app(
            paths=self.paths,
            tunnel_id=TUNNEL_ID,
            connector_id=CONNECTOR_ID,
            app_name="Codex Goal Ledger",
        )
        record = json.loads(self.paths.state_path.read_text())
        self.assertEqual(CONNECTOR_ID, record["connector_id"])
        self.assertEqual(0o600, stat.S_IMODE(self.paths.state_path.stat().st_mode))


if __name__ == "__main__":
    unittest.main(verbosity=2)
