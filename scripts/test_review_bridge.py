#!/usr/bin/env python3
"""Behavioral tests for Goal Ledger's restricted MCP App review bridge."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ledger_common import LedgerError
from run_review_bridge import ReviewScope, WIDGET_URI, build_server


SCRIPT_DIR = Path(__file__).resolve().parent


class ReviewBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="goal-ledger-review-bridge-")
        self.project = Path(self.temporary.name) / "project"
        self.run_tool(
            "init_goal.py",
            "--project-root",
            self.project,
            "--slug",
            "bridge-test",
            "--title",
            "Restricted Review Bridge",
            "--why",
            "A difficult plan needs a bounded direct Pro review lane.",
            "--outcome",
            "Pro reviews one immutable packet without live repository or shell access.",
            "--fable-feedback",
            "no",
            "--fable-rescue",
            "no",
            "--pro-review",
            "yes",
            "--pro-review-stage",
            "plan",
            "--pro-review-delivery",
            "mcp-app",
            "--pro-review-gate",
            "required",
            "--external-review-prompt",
            "no",
            "--codex-review",
            "no",
            "--clean-session-handoff",
            "no",
            "--date",
            "2026-07-15",
        )
        self.goal_dir = self.project / "docs" / "goals" / "bridge-test"
        context = self.project / "design" / "plan.md"
        context.parent.mkdir(parents=True)
        context.write_text("# Plan\n\nUse the restricted review bridge.\n", encoding="utf-8")
        self.run_tool(
            "run_pro_review.py",
            "prepare",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            "1",
            "--decision",
            "Approve this plan for implementation.",
            "--context-file",
            "design/plan.md",
            "--context-reason",
            "design/plan.md=Operative plan under review.",
        )
        self.scope = ReviewScope(self.goal_dir, "plan", 1)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_tool(self, name: str, *arguments: object, expected: int = 0):
        process = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / name), *(str(value) for value in arguments)],
            cwd=SCRIPT_DIR.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(
            expected,
            process.returncode,
            msg=f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}",
        )
        return process

    @property
    def round_dir(self) -> Path:
        return self.scope.round_dir

    def test_packet_scope_reads_only_manifest_members_and_detects_tampering(self) -> None:
        summary = self.scope.summary()
        self.assertEqual("immutable context-packet.zip only", summary["security"]["source"])
        self.assertFalse(summary["security"]["live_repository_access"])
        self.assertFalse(summary["security"]["shell_access"])
        names = [item["path"] for item in summary["members"]]
        self.assertIn("START-HERE.md", names)
        self.assertIn("context/design/plan.md", names)
        self.assertIn("Use the restricted review bridge", self.scope.read_member("context/design/plan.md"))
        with self.assertRaises(LedgerError):
            self.scope.read_member("../../goal.md")

        packet = self.scope.packet_path
        packet.write_bytes(packet.read_bytes() + b"tamper")
        with self.assertRaisesRegex(LedgerError, "packet hash"):
            self.scope.summary()

    def test_mcp_app_exposes_only_bounded_tools_and_widget(self) -> None:
        server = build_server(self.scope)
        tools = asyncio.run(server.list_tools())
        names = {tool.name for tool in tools}
        self.assertEqual(
            {
                "open_goal_ledger",
                "get_review_status",
                "read_review_file",
                "begin_pro_review",
                "submit_pro_review_response",
            },
            names,
        )
        self.assertFalse(any(name in names for name in ("bash", "exec_command", "read", "write", "edit")))
        open_tool = next(tool for tool in tools if tool.name == "open_goal_ledger")
        self.assertEqual(WIDGET_URI, open_tool.meta["ui"]["resourceUri"])
        resources = asyncio.run(server.list_resources())
        self.assertEqual(1, len(resources))
        self.assertEqual(WIDGET_URI, str(resources[0].uri))
        self.assertEqual("text/html;profile=mcp-app", resources[0].mimeType)

    def test_direct_mcp_review_records_submission_and_complete_response(self) -> None:
        server = build_server(self.scope)
        opened = asyncio.run(server.call_tool("open_goal_ledger", {}))
        self.assertEqual("review", opened.structuredContent["mode"])
        self.assertEqual("packet-ready", opened.structuredContent["review"]["status"])

        begun = asyncio.run(
            server.call_tool(
                "begin_pro_review",
                {
                    "model_visible": "Pro Extended",
                    "thread_reference": "Goal Ledger MCP App review",
                },
            )
        )
        self.assertEqual("submitted-waiting-response", begun.structuredContent["status"])
        submission = json.loads((self.round_dir / "submission.json").read_text())
        self.assertEqual("mcp-app", submission["transport"])
        self.assertEqual(self.scope.summary()["packet_sha256"], submission["packet_sha256"])
        for member in self.scope.summary()["members"]:
            read = asyncio.run(
                server.call_tool("read_review_file", {"member_path": member["path"]})
            )
            self.assertFalse(read.isError)
        self.assertEqual(
            {"read": 6, "total": 6, "missing": []},
            self.scope.summary()["read_progress"],
        )

        response = (
            "Verdict: SIGNED OFF\n\n"
            "Required changes:\n- None.\n\n"
            "Risks:\n- Preserve the immutable packet boundary.\n\n"
            "Tests or verification:\n- Run the bridge and custody tests.\n\n"
            "Reasoning notes:\n- The reviewed plan is internally consistent.\n"
        )
        received = asyncio.run(
            server.call_tool("submit_pro_review_response", {"response": response})
        )
        self.assertEqual("SIGNED OFF", received.structuredContent["verdict"])
        self.assertEqual(response.encode("utf-8"), (self.round_dir / "response.md").read_bytes())
        repeated = asyncio.run(
            server.call_tool("submit_pro_review_response", {"response": response})
        )
        self.assertEqual("already-recorded", repeated.structuredContent["status"])

    def test_mcp_response_requires_all_reads_and_complete_shape(self) -> None:
        server = build_server(self.scope)
        asyncio.run(
            server.call_tool(
                "begin_pro_review",
                {
                    "model_visible": "Pro Extended",
                    "thread_reference": "Goal Ledger MCP App review",
                },
            )
        )
        complete = (
            "Verdict: SIGNED OFF\n\n"
            "Required changes:\n- None.\n\n"
            "Risks:\n- Preserve custody.\n\n"
            "Tests or verification:\n- Verify receipts.\n\n"
            "Reasoning notes:\n- The packet is sufficient.\n"
        )
        with self.assertRaisesRegex(Exception, "did not read packet member"):
            asyncio.run(
                server.call_tool("submit_pro_review_response", {"response": complete})
            )

        for member in self.scope.summary()["members"]:
            asyncio.run(
                server.call_tool("read_review_file", {"member_path": member["path"]})
            )
        with self.assertRaisesRegex(Exception, "must contain exactly these sections"):
            asyncio.run(
                server.call_tool(
                    "submit_pro_review_response", {"response": "Verdict: SIGNED OFF\n"}
                )
            )

    def test_planning_mode_has_real_choice_schema_without_filesystem_scope(self) -> None:
        server = build_server(None)
        opened = asyncio.run(
            server.call_tool("open_goal_ledger", {"scientific_or_high_risk": True})
        )
        self.assertEqual("planning", opened.structuredContent["mode"])
        planning = opened.structuredContent["planning"]
        self.assertEqual(6, len(planning["schema"]["review_choices"]))
        self.assertEqual("mcp-app", planning["defaults"]["pro_delivery"])
        self.assertTrue(planning["defaults"]["fable_rescue"])

    def test_operator_guide_covers_complete_one_time_setup_and_recovery(self) -> None:
        guide = (SCRIPT_DIR.parent / "references" / "review-bridge.md").read_text(
            encoding="utf-8"
        )
        required_contracts = (
            "## What is actually one-time",
            "## Detailed one-time setup",
            "## Automatic Codex-driven setup",
            "Tunnels Read + Manage",
            "Tunnels Read + Use",
            "every non-tunnel permission",
            "ChatGPT subscription",
            "CONTROL_PLANE_API_KEY",
            "codex-goal-ledger-tunnel-client",
            "sample_mcp_stdio_local",
            "tunnel-client doctor --profile",
            "Settings → Security and login",
            "https://chatgpt.com/plugins",
            "No Auth",
            "setup_review_bridge.py start",
            "## Verify the connection",
            "## What changes for each review",
            "## Credential and data handling",
            "## Troubleshooting",
        )
        for contract in required_contracts:
            self.assertIn(contract, guide)
        self.assertIn(
            "references/review-bridge.md#detailed-one-time-setup",
            (SCRIPT_DIR.parent / "README.md").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
