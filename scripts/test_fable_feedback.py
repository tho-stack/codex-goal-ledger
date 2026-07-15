#!/usr/bin/env python3
"""Behavioral tests for opt-in Claude Fable planning feedback."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent


class FableFeedbackTests(unittest.TestCase):
    maxDiff = 4000

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="fable-feedback-tests-")
        self.project = Path(self.temporary.name)
        self.goal_dir = self.project / "docs" / "goals" / "fable-test"
        initialized = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "init_goal.py"),
                "--project-root",
                str(self.project),
                "--slug",
                "fable-test",
                "--title",
                "Fable Test",
                "--why",
                "Exercise the optional planning peer.",
                "--outcome",
                "A durable structured Fable opinion.",
                "--fable-feedback",
                "yes",
                "--pro-review",
                "no",
                "--fable-profile",
                "claude-fable-5 xhigh",
                "--external-review-prompt",
                "no",
                "--codex-review",
                "no",
                "--clean-session-handoff",
                "no",
                "--date",
                "2026-07-14",
            ],
            cwd=SCRIPT_DIR.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, initialized.returncode, initialized.stderr)
        self.fake_claude = self.project / "fake-claude"
        self.fake_claude.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys

with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as stream:
    stream.write(sys.argv[-1] + "\\n<<<END>>>\\n")

assert "--safe-mode" in sys.argv
assert "dontAsk" in sys.argv
assert "claude-fable-5" in sys.argv
assert "WebSearch,WebFetch" in sys.argv
assert "Read,Glob,Grep,LS" not in sys.argv
assert "--no-session-persistence" in sys.argv
assert "ANTHROPIC_API_KEY" not in os.environ
assert "ANTHROPIC_AUTH_TOKEN" not in os.environ
assert "NODE_OPTIONS" not in os.environ

payload = {
    "verdict": "REVISE",
    "summary": "The plan is viable but needs a sharper verification boundary.",
    "strengths": ["The outcome is observable."],
    "concerns": [{
        "severity": "major",
        "finding": "Verification is underspecified.",
        "evidence": "The initial progress record has only scaffold checks.",
        "recommendation": "Name the focused and full validation commands."
    }],
    "additional_information": [{
        "information": "Expected runtime environment",
        "improves": "Preview and portability validation",
        "default_if_omitted": "Validate localhost and simulated Tailscale routing"
    }],
    "feature_proposals": [{
        "title": "Evidence diff view",
        "opportunity": "Show what changed between review rounds.",
        "user_value": "Makes reconciliation faster and auditable.",
        "fit_with_goal": "in-scope",
        "validation": "Render two rounds and verify the dashboard exposes their differences."
    }],
    "science_proposals": [{
        "question": "Do reconciled review rounds reduce unresolved major findings?",
        "hypothesis": "A second round after reconciliation will reduce major findings.",
        "why_it_matters": "It tests whether multiple rounds add value instead of repetition.",
        "proposed_method": "Compare finding counts across paired round artifacts.",
        "evidence_needed": "A sample of multi-round ledgers with severity-coded findings.",
        "fit_with_goal": "adjacent"
    }],
    "amended_brief": "Add exact validation commands before implementation."
}
print(json.dumps({"structured_output": payload}))
""",
            encoding="utf-8",
        )
        self.fake_claude.chmod(0o755)
        self.fake_claude_log = self.project / "fake-claude.log"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def invoke_feedback(
        self, *arguments: str, expected: int = 0
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(
            {
                "ANTHROPIC_API_KEY": "must-not-leak",
                "ANTHROPIC_AUTH_TOKEN": "must-not-leak",
                "NODE_OPTIONS": "must-not-leak",
                "FAKE_CLAUDE_LOG": str(self.fake_claude_log),
            }
        )
        process = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "run_fable_feedback.py"),
                str(self.goal_dir),
                "--claude-bin",
                str(self.fake_claude),
                *arguments,
            ],
            cwd=SCRIPT_DIR.parent,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(expected, process.returncode, process.stderr)
        return process

    def run_feedback(
        self, *arguments: str, expected: int = 0
    ) -> subprocess.CompletedProcess[str]:
        if "--check" in arguments or "--prepare-transmission" in arguments:
            return self.invoke_feedback(*arguments, expected=expected)
        prepared = self.invoke_feedback(*arguments, "--prepare-transmission", expected=expected)
        if prepared.returncode != 0 or not prepared.stdout.lstrip().startswith("{"):
            return prepared
        manifest = json.loads(prepared.stdout)
        return self.invoke_feedback(
            *arguments,
            "--approve-transmission",
            manifest["approval_digest"],
            expected=expected,
        )

    def test_selected_feedback_runs_read_only_and_is_durable(self) -> None:
        result = self.run_feedback()
        self.assertIn("evidence/fable-feedback.md", result.stdout)
        artifact = self.goal_dir / "evidence" / "fable-feedback.md"
        text = artifact.read_text(encoding="utf-8")
        self.assertIn("# Claude Fable peer feedback", text)
        self.assertIn("**REVISE**", text)
        self.assertIn("**Requested profile:** `claude-fable-5 xhigh`", text)
        self.assertIn("**Invoked profile:** `claude-fable-5 high`", text)
        self.assertIn("**Effective profile:** `unconfirmed unconfirmed`", text)
        self.assertIn("## Additional information that could improve the plan", text)
        self.assertIn("## Feature opportunities", text)
        self.assertIn("### In-Scope: Evidence diff view", text)
        self.assertIn("## Science and research opportunities", text)
        self.assertIn("Do reconciled review rounds reduce unresolved major findings?", text)
        self.assertIn("## Structured result", text)
        self.assertIn("**Round:** 1 of 1", text)
        transport = (
            self.goal_dir
            / "evidence"
            / "fable-transport"
            / "planning-round-1"
            / "attempt-1"
        )
        self.assertTrue((transport / "raw-response.json").is_file())
        status = json.loads((transport / "transport.json").read_text(encoding="utf-8"))
        self.assertEqual("completed", status["state"])
        self.assertRegex(status["stdout_sha256"], r"^[0-9a-f]{64}$")
        prompt = self.fake_claude_log.read_text(encoding="utf-8")
        self.assertIn("Act as an inventive product and science peer too", prompt)
        self.assertIn("Proposals are advisory and not authorization to expand scope", prompt)
        self.assertIn("ALLOW-LISTED CONTEXT PACKET", prompt)
        self.assertIn("docs/goals/fable-test/goal.md", prompt)
        self.assertIn("docs/goals/fable-test/progress.md", prompt)

        checked = self.run_feedback("--check")
        self.assertIn("Fable feedback is valid", checked.stdout)
        unchanged = artifact.read_bytes()
        reused = self.run_feedback()
        self.assertIn("already exists", reused.stdout)
        self.assertEqual(unchanged, artifact.read_bytes())

    def test_invalid_existing_feedback_fails_check(self) -> None:
        artifact = self.goal_dir / "evidence" / "fable-feedback.md"
        artifact.write_text("invalid\n", encoding="utf-8")
        checked = self.run_feedback("--check", expected=1)
        self.assertIn("invalid Fable feedback structure", checked.stderr)

    def test_unselected_feedback_never_calls_claude(self) -> None:
        goal = self.goal_dir / "goal.md"
        text = goal.read_text(encoding="utf-8").replace(
            "| Claude Fable peer feedback | yes |",
            "| Claude Fable peer feedback | no |",
            1,
        )
        goal.write_text(text, encoding="utf-8", newline="\n")
        self.fake_claude.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
        skipped = self.run_feedback()
        self.assertIn("not selected", skipped.stdout)
        self.assertFalse((self.goal_dir / "evidence" / "fable-feedback.md").exists())

    def test_existing_artifact_repairs_profile_ledger_without_calling_claude_again(self) -> None:
        self.run_feedback()
        goal = self.goal_dir / "goal.md"
        text = goal.read_text(encoding="utf-8")
        text = text.replace(
            "| Claude Fable planning peer | claude-fable-5 xhigh | claude-fable-5 high | unconfirmed |",
            "| Claude Fable planning peer | claude-fable-5 xhigh | not-invoked | unconfirmed |",
            1,
        )
        goal.write_text(text, encoding="utf-8", newline="\n")
        checked = self.run_feedback("--check", expected=1)
        self.assertIn("invoked profile does not match", checked.stderr)

        self.fake_claude.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
        reused = self.run_feedback()
        self.assertIn("already exists", reused.stdout)
        self.run_feedback("--check")

    def test_multiple_rounds_advance_sequentially_and_include_prior_feedback(self) -> None:
        goal = self.goal_dir / "goal.md"
        text = goal.read_text(encoding="utf-8").replace(
            "fable_review_rounds: 1", "fable_review_rounds: 3", 1
        )
        goal.write_text(text, encoding="utf-8", newline="\n")

        out_of_order = self.run_feedback("--round", "2", expected=1)
        self.assertIn("cannot run Fable round 2 before valid round 1", out_of_order.stderr)
        first = self.run_feedback()
        self.assertIn("evidence/fable-feedback.md", first.stdout)
        incomplete = self.run_feedback("--check", expected=1)
        self.assertIn("missing selected Fable feedback round 2 of 3", incomplete.stderr)

        second = self.run_feedback()
        self.assertIn("evidence/fable-feedback-round-2.md", second.stdout)
        third = self.run_feedback()
        self.assertIn("evidence/fable-feedback-round-3.md", third.stdout)
        checked = self.run_feedback("--check")
        self.assertIn("valid for 3 rounds", checked.stdout)

        for round_number, name in (
            (1, "fable-feedback.md"),
            (2, "fable-feedback-round-2.md"),
            (3, "fable-feedback-round-3.md"),
        ):
            artifact = self.goal_dir / "evidence" / name
            self.assertIn(
                f"**Round:** {round_number} of 3",
                artifact.read_text(encoding="utf-8"),
            )

        prompts = self.fake_claude_log.read_text(encoding="utf-8")
        self.assertIn("review round 2 of 3", prompts)
        self.assertIn("docs/goals/fable-test/evidence/fable-feedback.md", prompts)
        self.assertIn("review round 3 of 3", prompts)
        self.assertIn("docs/goals/fable-test/evidence/fable-feedback-round-2.md", prompts)

        reused = self.run_feedback()
        self.assertIn("round 3 of 3 already exists", reused.stdout)

    def test_manifest_is_exact_and_stale_digest_prevents_transmission(self) -> None:
        context = self.project / "design-note.md"
        context.write_text("Allow-listed design evidence.\n", encoding="utf-8")
        prepared = self.invoke_feedback(
            "--context-file",
            "design-note.md",
            "--prepare-transmission",
        )
        manifest = json.loads(prepared.stdout)
        self.assertEqual(
            [
                "docs/goals/fable-test/goal.md",
                "docs/goals/fable-test/progress.md",
                "design-note.md",
            ],
            [item["path"] for item in manifest["files"]],
        )
        self.assertEqual(
            "only the enumerated UTF-8 files embedded in the prompt",
            manifest["repository_access"],
        )
        self.assertRegex(manifest["prompt_sha256"], r"^[0-9a-f]{64}$")
        context.write_text("Changed after approval.\n", encoding="utf-8")
        stale = self.invoke_feedback(
            "--context-file",
            "design-note.md",
            "--approve-transmission",
            manifest["approval_digest"],
            expected=1,
        )
        self.assertIn("approval is missing or stale", stale.stderr)
        self.assertFalse((self.goal_dir / "evidence" / "fable-feedback.md").exists())

    def test_context_file_must_stay_inside_repository(self) -> None:
        outside = self.project.parent / "outside-fable-context.txt"
        outside.write_text("outside\n", encoding="utf-8")
        try:
            escaped = self.invoke_feedback(
                "--context-file",
                "../outside-fable-context.txt",
                "--prepare-transmission",
                expected=1,
            )
            self.assertIn("escapes the repository", escaped.stderr)
        finally:
            outside.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
