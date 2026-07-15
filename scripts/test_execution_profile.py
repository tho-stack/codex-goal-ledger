#!/usr/bin/env python3
"""Behavioral tests for Goal Ledger execution profile evidence."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agent_profiles import IMPLEMENTER_PROFILES


SCRIPT_DIR = Path(__file__).resolve().parent


class ExecutionProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="goal-ledger-profile-")
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        initialized = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "init_goal.py"),
                "--project-root",
                str(self.project),
                "--slug",
                "profile-test",
                "--title",
                "Profile Test",
                "--why",
                "Keep routing evidence honest.",
                "--outcome",
                "Requested, invoked, and effective profiles remain distinct.",
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
        self.goal_dir = self.project / "docs" / "goals" / "profile-test"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_script(self, name: str, *arguments: object, expected: int = 0, env=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / name), *(str(value) for value in arguments)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=env,
        )
        self.assertEqual(expected, result.returncode, result.stderr)
        return result

    def test_owned_agent_preflight_distinguishes_configuration_from_runtime(self) -> None:
        codex_home = self.root / "codex-home"
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(codex_home)
        self.run_script("install_skill.py", "--with-agents", env=environment)
        checked = self.run_script(
            "execution_profile.py",
            "preflight",
            "--codex-home",
            codex_home,
            "--implementer",
            "goal-ledger-implementer-sol-ultra",
            "--swarm-implementer",
            "goal-ledger-implementer-terra-ultra",
            "--swarm-implementer",
            "goal-ledger-implementer-luna-high",
            "--json",
        )
        payload = json.loads(checked.stdout)
        self.assertTrue(payload["configured"])
        self.assertEqual("unconfirmed", payload["session_visible"])
        self.assertFalse(payload["runtime_confirmed"])
        self.assertEqual(
            {"model": "gpt-5.6-luna", "effort": "max"},
            payload["profiles"]["goal-ledger-implementer"],
        )
        self.assertEqual(
            {profile.name for profile in IMPLEMENTER_PROFILES},
            {
                name
                for name in payload["profiles"]
                if name.startswith("goal-ledger-implementer")
            },
        )
        self.assertEqual(
            {
                "name": "goal-ledger-implementer-sol-ultra",
                "configured": True,
                "model": "gpt-5.6-sol",
                "effort": "ultra",
            },
            payload["selected_implementer"],
        )
        self.assertEqual(
            [
                "goal-ledger-implementer-sol-ultra",
                "goal-ledger-implementer-terra-ultra",
                "goal-ledger-implementer-luna-high",
            ],
            [profile["name"] for profile in payload["selected_implementers"]],
        )
        self.assertFalse(payload["external_review_approval"]["configured"])

    def test_external_review_preflight_fails_fast_until_owner_routing_is_configured(self) -> None:
        codex_home = self.root / "codex-home-external-review"
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(codex_home)
        self.run_script("install_skill.py", "--with-agents", env=environment)
        config = codex_home / "config.toml"
        text = config.read_text(encoding="utf-8")
        config.write_text(
            'approvals_reviewer = "auto_review"\n'
            'approval_policy = "never"\n\n'
            + text,
            encoding="utf-8",
        )
        blocked = self.run_script(
            "execution_profile.py",
            "preflight",
            "--codex-home",
            codex_home,
            "--require-external-review-approval",
            "--json",
            expected=1,
        )
        payload = json.loads(blocked.stdout)
        self.assertFalse(payload["external_review_approval"]["configured"])
        self.assertIn(
            'root approvals_reviewer must be "user"',
            "\n".join(payload["external_review_approval"]["problems"]),
        )

        self.run_script(
            "install_skill.py",
            "--configure-review-approvals",
            env=environment,
        )
        ready = self.run_script(
            "execution_profile.py",
            "preflight",
            "--codex-home",
            codex_home,
            "--require-external-review-approval",
            "--json",
        )
        payload = json.loads(ready.stdout)
        self.assertTrue(payload["external_review_approval"]["configured"])
        self.assertEqual("unconfirmed", payload["external_review_approval"]["session_effective"])

    def test_initializer_derives_requested_profile_from_selected_implementer(self) -> None:
        selected_project = self.root / "selected-project"
        self.run_script(
            "init_goal.py",
            "--project-root",
            selected_project,
            "--slug",
            "selected-profile",
            "--title",
            "Selected Profile",
            "--why",
            "Exercise implementation-agent selection.",
            "--outcome",
            "The ledger records the selected owned preset.",
            "--implementation-agent",
            "goal-ledger-implementer-terra-ultra",
            "--swarm-implementer",
            "goal-ledger-implementer-sol-xhigh",
            "--swarm-implementer",
            "goal-ledger-implementer-luna-high",
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
        )
        goal = selected_project / "docs" / "goals" / "selected-profile" / "goal.md"
        text = goal.read_text(encoding="utf-8")
        self.assertIn(
            "| Implementation | gpt-5.6-terra ultra | not-invoked | unconfirmed | "
            "Primary owned role: `goal-ledger-implementer-terra-ultra`. Optional mixed-swarm "
            "roles: `goal-ledger-implementer-sol-xhigh` (gpt-5.6-sol xhigh), "
            "`goal-ledger-implementer-luna-high` (gpt-5.6-luna high).",
            text,
        )

    def test_record_updates_only_the_selected_v4_profile_row(self) -> None:
        self.run_script(
            "execution_profile.py",
            "record",
            self.goal_dir,
            "--layer",
            "Implementation",
            "--invoked",
            "goal-ledger-implementer",
            "--effective",
            "gpt-5.6-luna max",
            "--evidence",
            "runtime metadata captured in evidence/worker.json",
        )
        text = (self.goal_dir / "goal.md").read_text(encoding="utf-8")
        self.assertIn(
            "| Implementation | gpt-5.6-luna max | goal-ledger-implementer | "
            "gpt-5.6-luna max | runtime metadata captured in evidence/worker.json |",
            text,
        )
        self.assertIn(
            "| Final adversarial review | gpt-5.6-sol xhigh | not-invoked | unconfirmed |",
            text,
        )
        self.run_script("render_goal.py", self.goal_dir)
        self.run_script("validate_goal.py", self.goal_dir)


if __name__ == "__main__":
    unittest.main(verbosity=2)
