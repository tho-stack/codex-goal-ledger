#!/usr/bin/env python3
"""Focused behavioral tests for deterministic closeout prompt generation."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from generate_closeout_prompts import (
    CLEAN_HANDOFF_OPTION,
    CODEX_REVIEW_OPTION,
    EXTERNAL_REVIEW_OPTION,
    FABLE_FEEDBACK_OPTION,
    build_closeout_prompt_artifacts,
    load_closeout_options,
)


SCRIPT_DIR = Path(__file__).resolve().parent


def goal_markdown(
    *, external: str, codex: str, handoff: str, fable: str | None = None
) -> str:
    version = "3" if fable is not None else "2"
    fable_row = (
        f"| Claude Fable peer feedback | {fable} | Run Fable feedback. |\n"
        if fable is not None
        else ""
    )
    return f"""---
ledger_version: {version}
title: Use *literal* C#_2
slug: closeout-test
status: active
created: 2026-07-13
updated: 2026-07-13
mode: overnight-capable
allowed_skipped_phases: none
allowed_skipped_verifications: none
---

# Use \\*literal\\* C\\#\\_2

## Closeout options

| Option | Choice | Artifact or action |
| --- | --- | --- |
{fable_row}| External LLM review prompt | {external} | Generate the review prompt. |
| Additional Codex review | {codex} | Run the Codex review. |
| Clean-session handoff prompt | {handoff} | Generate the handoff prompt. |
"""


class CloseoutPromptTests(unittest.TestCase):
    maxDiff = 4000

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="closeout-prompt-tests-")
        self.project = Path(self.temporary.name)
        self.goal_dir = self.project / "docs" / "goals" / "closeout-test"
        self.goal_dir.mkdir(parents=True)
        (self.goal_dir / "progress.md").write_text("canonical progress\n", encoding="utf-8")
        (self.goal_dir / "index.html").write_text("<!doctype html>\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_goal(
        self, *, external: str, codex: str, handoff: str, fable: str | None = None
    ) -> None:
        (self.goal_dir / "goal.md").write_text(
            goal_markdown(
                external=external, codex=codex, handoff=handoff, fable=fable
            ),
            encoding="utf-8",
            newline="\n",
        )

    def run_tool(self, *arguments: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        process = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "generate_closeout_prompts.py"), *arguments],
            cwd=self.project,
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

    def test_yes_choices_generate_exact_repo_relative_prompts_and_check_bytes(self) -> None:
        self.write_goal(external="yes", codex="yes", handoff="yes")
        generated = self.run_tool(str(self.goal_dir))
        self.assertIn("review-prompt.md", generated.stdout)
        self.assertIn("handoff-prompt.md", generated.stdout)

        goal, choices = load_closeout_options(self.goal_dir)
        self.assertEqual("yes", choices[EXTERNAL_REVIEW_OPTION])
        self.assertEqual("yes", choices[CODEX_REVIEW_OPTION])
        self.assertEqual("yes", choices[CLEAN_HANDOFF_OPTION])
        expected = build_closeout_prompt_artifacts(self.goal_dir, goal=goal, choices=choices)
        self.assertEqual(
            {
                (self.goal_dir / "review-prompt.md").resolve(),
                (self.goal_dir / "handoff-prompt.md").resolve(),
            },
            set(expected),
        )
        for path, data in expected.items():
            self.assertEqual(data, path.read_bytes())
            text = data.decode("utf-8")
            self.assertIn("docs/goals/closeout-test/goal.md", text)
            self.assertNotIn(str(self.project), text)
        self.assertIn("Use \\*literal\\* C\\#\\_2", (self.goal_dir / "review-prompt.md").read_text())
        self.run_tool("--check", str(self.goal_dir))

        (self.goal_dir / "review-prompt.md").write_text("drift\n", encoding="utf-8")
        drift = self.run_tool("--check", str(self.goal_dir), expected=1)
        self.assertIn("stale selected closeout prompt", drift.stderr)
        self.run_tool(str(self.goal_dir))
        self.run_tool("--check", str(self.goal_dir))

    def test_no_and_ask_never_delete_existing_prompt_artifacts(self) -> None:
        self.write_goal(external="yes", codex="no", handoff="yes")
        self.run_tool(str(self.goal_dir))
        self.assertTrue((self.goal_dir / "review-prompt.md").exists())
        self.assertTrue((self.goal_dir / "handoff-prompt.md").exists())

        self.write_goal(external="no", codex="ask", handoff="ask")
        preserved = self.run_tool(str(self.goal_dir), expected=1)
        self.assertIn("unselected closeout prompt must be absent", preserved.stderr)
        self.assertTrue((self.goal_dir / "review-prompt.md").exists())
        self.assertTrue((self.goal_dir / "handoff-prompt.md").exists())
        (self.goal_dir / "review-prompt.md").unlink()
        (self.goal_dir / "handoff-prompt.md").unlink()
        self.run_tool("--check", str(self.goal_dir))

    def test_invalid_choice_or_exact_row_contract_fails_without_artifacts(self) -> None:
        self.write_goal(external="maybe", codex="no", handoff="no")
        invalid = self.run_tool(str(self.goal_dir), expected=2)
        self.assertIn("choice must be one of", invalid.stderr)
        self.assertFalse((self.goal_dir / "review-prompt.md").exists())

        self.write_goal(external="yes", codex="no", handoff="no")
        goal_path = self.goal_dir / "goal.md"
        goal_path.write_text(
            goal_path.read_text(encoding="utf-8").replace(
                "External LLM review prompt", "External review prompt", 1
            ),
            encoding="utf-8",
            newline="\n",
        )
        invalid_row = self.run_tool(str(self.goal_dir), expected=2)
        self.assertIn("rows must be exactly", invalid_row.stderr)
        self.assertFalse((self.goal_dir / "review-prompt.md").exists())

    def test_schema_v3_includes_independent_fable_choice(self) -> None:
        self.write_goal(external="no", codex="no", handoff="no", fable="yes")
        _, choices = load_closeout_options(self.goal_dir)
        self.assertEqual("yes", choices[FABLE_FEEDBACK_OPTION])
        self.assertEqual(4, len(choices))


if __name__ == "__main__":
    unittest.main(verbosity=2)
