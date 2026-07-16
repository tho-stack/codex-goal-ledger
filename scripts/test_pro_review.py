#!/usr/bin/env python3
"""Behavioral tests for native Goal Ledger GPT Pro review custody."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


SCRIPT_DIR = Path(__file__).resolve().parent


class ProReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="goal-ledger-pro-")
        self.project = Path(self.temporary.name) / "project"
        initialized = self.run_tool(
            "init_goal.py",
            "--project-root",
            self.project,
            "--slug",
            "pro-test",
            "--title",
            "Native Pro Test",
            "--why",
            "A difficult plan needs independent review.",
            "--outcome",
            "The plan is reviewed from a scoped, durable packet.",
            "--fable-feedback",
            "no",
            "--fable-rescue",
            "no",
            "--pro-review",
            "yes",
            "--pro-review-stage",
            "plan",
            "--pro-review-delivery",
            "auto-ui",
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
        self.assertIn("Goal ledger ready", initialized.stdout)
        self.goal_dir = self.project / "docs" / "goals" / "pro-test"
        self.context = self.project / "design" / "plan.md"
        self.context.parent.mkdir(parents=True)
        self.context.write_text("# Plan\n\nUse a deterministic review lane.\n", encoding="utf-8")

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
        return self.goal_dir / "evidence" / "pro-review" / "plan" / "round-001"

    def prepare(self):
        return self.run_tool(
            "run_pro_review.py",
            "prepare",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            "1",
            "--decision",
            "Approve this plan for implementation.",
            "--review-question",
            "Does the plan preserve recovery and evidence integrity?",
            "--context-file",
            "design/plan.md",
            "--context-reason",
            "design/plan.md=Operative implementation plan under review.",
        )

    def complete_signed_off_review(self) -> bytes:
        self.prepare()
        plan = json.loads((self.round_dir / "delivery-plan.json").read_text())
        surface = next(item for item in plan["candidates"] if item != "owner-handoff")
        self.run_tool(
            "run_pro_review.py",
            "record-attempt",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            "1",
            "--surface",
            surface,
            "--result",
            "ready",
            "--detail",
            "Authenticated Pro Extended mode and upload are visible.",
        )
        self.run_tool(
            "run_pro_review.py",
            "record-submission",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            "1",
            "--model-visible",
            "Pro Extended",
            "--transport",
            surface,
            "--thread",
            "Native Pro Test planning review",
        )
        raw = (
            "Verdict: SIGNED OFF\n\n"
            "Required changes:\n- None.\n\n"
            "Risks:\n- Preserve packet hashes.\n\n"
            "Tests or verification:\n- Run the custody checker.\n\n"
            "Reasoning notes:\n- The plan is internally consistent.\n"
            + ("Detailed evidence line.\n" * 200)
        ).encode("utf-8")
        response_source = self.project / "full-pro-response.md"
        response_source.write_bytes(raw)
        self.run_tool(
            "run_pro_review.py",
            "record-response",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            "1",
            "--response-file",
            response_source,
        )
        reconciliation = self.project / "reconciliation.json"
        reconciliation.write_text(
            json.dumps(
                {
                    "pro_verdict": "SIGNED OFF",
                    "items": [],
                    "local_verification": ["Packet hashes and current plan were checked locally."],
                    "next_action": "Begin implementation under the approved plan.",
                }
            ),
            encoding="utf-8",
        )
        self.run_tool(
            "run_pro_review.py",
            "reconcile",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            "1",
            "--reconciliation-file",
            reconciliation,
        )
        return raw

    def test_prepare_builds_deterministic_scoped_zip_and_manifest(self) -> None:
        self.prepare()
        packet = self.round_dir / "context-packet.zip"
        manifest = json.loads((self.round_dir / "packet-manifest.json").read_text())
        first = packet.read_bytes()
        second_run = self.prepare()
        self.assertIn("already current", second_run.stdout)
        self.assertEqual(first, packet.read_bytes())

        with zipfile.ZipFile(packet) as archive:
            names = archive.namelist()
            self.assertEqual(sorted(names), names)
            self.assertIn("START-HERE.md", names)
            self.assertIn("packet-index.json", names)
            self.assertIn("repo-state.txt", names)
            self.assertIn("context/design/plan.md", names)
            self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist()))
            request = archive.read("START-HERE.md").decode("utf-8")
        for heading in (
            "## Role",
            "## Decision",
            "## Success criteria",
            "## Constraints",
            "## Evidence received",
            "## Review questions",
            "## Output",
            "## Stop rules",
        ):
            self.assertIn(heading, request)
        self.assertNotIn(str(self.project), request)
        self.assertEqual(3, len(manifest["source_files"]))
        self.run_tool("run_pro_review.py", "check", self.goal_dir)

    def test_full_response_is_preserved_and_required_plan_gate_is_enforced(self) -> None:
        progress = self.goal_dir / "progress.md"
        progress.write_text(
            progress.read_text(encoding="utf-8").replace(
                "| Define | active |", "| Define | complete |", 1
            ).replace(
                "| Build | pending |", "| Build | active |", 1
            ),
            encoding="utf-8",
        )
        self.run_tool("render_goal.py", self.goal_dir)
        blocked = self.run_tool("validate_goal.py", self.goal_dir, expected=1)
        self.assertIn("Build cannot be active", blocked.stderr)

        self.prepare()
        wrong = self.run_tool(
            "run_pro_review.py",
            "record-submission",
            self.goal_dir,
            "--stage",
            "plan",
            "--model-visible",
            "Thinking",
            "--transport",
            "safari-assisted",
            "--thread",
            "Wrong mode",
            expected=2,
        )
        self.assertIn("must identify a Pro mode", wrong.stderr)

        raw = self.complete_signed_off_review()
        self.assertEqual(raw, (self.round_dir / "response.md").read_bytes())
        self.run_tool("run_pro_review.py", "check", self.goal_dir, "--require-closed")
        self.run_tool("render_goal.py", self.goal_dir)
        self.run_tool("validate_goal.py", self.goal_dir)

    def test_packet_tampering_and_secret_inputs_are_rejected(self) -> None:
        secret = self.project / ".env"
        secret.write_text("TOKEN=secret\n", encoding="utf-8")
        rejected = self.run_tool(
            "run_pro_review.py",
            "prepare",
            self.goal_dir,
            "--stage",
            "plan",
            "--decision",
            "Review the plan.",
            "--context-file",
            ".env",
            expected=2,
        )
        self.assertIn("likely secret", rejected.stderr)

        self.prepare()
        packet = self.round_dir / "context-packet.zip"
        packet.write_bytes(packet.read_bytes() + b"tamper")
        invalid = self.run_tool("run_pro_review.py", "check", self.goal_dir, expected=1)
        self.assertIn("packet hash does not match", invalid.stderr)

    def test_auto_ui_routes_platform_surfaces_and_falls_back_to_manual_handoff(self) -> None:
        self.prepare()
        plan = json.loads((self.round_dir / "delivery-plan.json").read_text())
        self.assertEqual("auto-ui", plan["configured_delivery"])
        expected = (
            ["safari-assisted", "chrome-assisted", "owner-handoff"]
            if plan["host_platform"] == "Darwin"
            else ["chrome-assisted", "owner-handoff"]
        )
        self.assertEqual(expected, plan["candidates"])
        self.assertEqual(
            "goal-ledger-restricted-mcp-app",
            plan["transport_drivers"]["mcp-app"],
        )
        self.assertEqual("computer-use-mcp", plan["transport_drivers"]["browser"])
        self.assertTrue(plan["automatic_submission"])
        self.assertIn("chatgpt-desktop", plan["excluded_surfaces"])
        self.assertFalse(plan["mcp_app_contract"]["live_repository_access"])
        self.assertFalse(plan["mcp_app_contract"]["shell_access"])

        assisted = [item for item in plan["candidates"] if item != "owner-handoff"]
        result = None
        for surface in assisted:
            result = self.run_tool(
                "run_pro_review.py",
                "record-attempt",
                self.goal_dir,
                "--stage",
                "plan",
                "--round",
                "1",
                "--surface",
                surface,
                "--result",
                "unavailable",
                "--detail",
                f"{surface} is unavailable in this test harness.",
            )
        self.assertIsNotNone(result)
        self.assertIn("manual-handoff-ready", result.stdout)
        handoff = (self.round_dir / "manual-handoff.md").read_text()
        self.assertIn("context-packet.zip", handoff)
        self.assertIn("ZIP SHA-256", handoff)
        state = json.loads((self.round_dir / "state.json").read_text())
        self.assertEqual("manual-handoff-ready", state["status"])
        self.run_tool("run_pro_review.py", "check", self.goal_dir)

    def test_ready_chrome_attempt_records_actual_submission_surface(self) -> None:
        self.prepare()
        plan = json.loads((self.round_dir / "delivery-plan.json").read_text())
        assisted = [item for item in plan["candidates"] if item != "owner-handoff"]
        bypass = self.run_tool(
            "run_pro_review.py",
            "record-submission",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            "1",
            "--model-visible",
            "Pro Extended",
            "--transport",
            assisted[0],
            "--thread",
            "Unprobed review",
            expected=2,
        )
        self.assertIn("requires a ready transport attempt", bypass.stderr)
        for surface in assisted:
            outcome = "ready" if surface == "chrome-assisted" else "unavailable"
            self.run_tool(
                "run_pro_review.py",
                "record-attempt",
                self.goal_dir,
                "--stage",
                "plan",
                "--round",
                "1",
                "--surface",
                surface,
                "--result",
                outcome,
                "--detail",
                f"Recorded {outcome} for {surface}.",
            )
            if outcome == "ready":
                break
        self.run_tool(
            "run_pro_review.py",
            "record-submission",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            "1",
            "--model-visible",
            "Pro Extended",
            "--transport",
            "chrome-assisted",
            "--thread",
            "Chrome routed review",
        )
        submission = json.loads((self.round_dir / "submission.json").read_text())
        self.assertEqual("chrome-assisted", submission["transport"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
