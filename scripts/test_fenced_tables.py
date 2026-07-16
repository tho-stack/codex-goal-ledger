#!/usr/bin/env python3
"""Regression tests for canonical tables near fenced Markdown examples."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from ledger_common import load_document, parse_table


SCRIPT_DIR = Path(__file__).resolve().parent


class FencedTableTests(unittest.TestCase):
    maxDiff = 4000

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="fenced-table-tests-")
        self.project = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_tool(
        self,
        name: str,
        *arguments: object,
        expected: int | None = 0,
    ) -> subprocess.CompletedProcess[str]:
        process = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / name), *(str(value) for value in arguments)],
            cwd=SCRIPT_DIR.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if expected is not None:
            self.assertEqual(
                expected,
                process.returncode,
                msg=f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}",
            )
        return process

    def initialize_pro_goal(self) -> Path:
        self.run_tool(
            "init_goal.py",
            "--project-root",
            self.project,
            "--slug",
            "fenced-table-guard",
            "--title",
            "Fenced Table Guard",
            "--why",
            "Canonical tables must not be replaced by examples.",
            "--outcome",
            "Only unfenced tables control the ledger.",
            "--planning-input-assessment",
            (
                "- **Required before execution:** None.\n"
                "- **Optional, improves result:** No additional information would "
                "materially improve this plan."
            ),
            "--planning-profile",
            "gpt-5.6-sol xhigh",
            "--implementation-profile",
            "gpt-5.6-luna max",
            "--review-profile",
            "gpt-5.6-sol xhigh",
            "--fable-feedback",
            "no",
            "--fable-rescue",
            "no",
            "--pro-review",
            "yes",
            "--external-review-prompt",
            "no",
            "--codex-review",
            "no",
            "--clean-session-handoff",
            "no",
            "--date",
            "2026-07-16",
        )
        return self.project / "docs" / "goals" / "fenced-table-guard"

    def insert_fenced_table(self, path: Path, section: str, table: str) -> None:
        text = path.read_text(encoding="utf-8")
        marker = f"## {section}\n\n"
        self.assertIn(marker, text)
        replacement = f"{marker}```markdown\n{table.rstrip()}\n```\n\n"
        path.write_text(text.replace(marker, replacement, 1), encoding="utf-8", newline="\n")

    def test_parse_table_skips_backtick_and_tilde_fences(self) -> None:
        markdown = """
```markdown
| Fake | State |
| --- | --- |
| Override | complete |
```

~~~text
| Other fake | State |
| --- | --- |
| Override | pass |
~~~

| Canonical | State |
| --- | --- |
| Real row | active |
"""
        headers, rows = parse_table(markdown)
        self.assertEqual(["Canonical", "State"], headers)
        self.assertEqual([["Real row", "active"]], rows)

    def test_fenced_operational_tables_cannot_bypass_required_pro_review(self) -> None:
        goal_dir = self.initialize_pro_goal()
        goal_path = goal_dir / "goal.md"
        progress_path = goal_dir / "progress.md"

        self.insert_fenced_table(
            goal_path,
            "Closeout options",
            """
| Option | Choice | Artifact or action |
| --- | --- | --- |
| Claude Fable peer feedback | no | Fake row. |
| Claude Fable scientific rescue | no | Fake row. |
| GPT Pro review | no | Fake row. |
| External LLM review prompt | no | Fake row. |
| Additional Codex review | no | Fake row. |
| Clean-session handoff prompt | no | Fake row. |
""",
        )
        self.insert_fenced_table(
            progress_path,
            "Phase tracker",
            """
| Phase | State | Evidence | Next gate |
| --- | --- | --- | --- |
| Discover | complete | Fake evidence. | None |
| Define | complete | Fake evidence. | None |
| Build | complete | Fake evidence. | None |
| Verify | complete | Fake evidence. | None |
| Close | complete | Fake evidence. | None |
""",
        )
        self.insert_fenced_table(
            progress_path,
            "Verification",
            """
| Check | Result | Evidence |
| --- | --- | --- |
| Ledger initialization | pass | Fake evidence. |
| Completion contract | pass | Fake evidence. |
| HTTP dashboard preview | pass | Fake evidence. |
| GPT Pro review | pass | Fake evidence. |
""",
        )
        self.insert_fenced_table(
            progress_path,
            "Custody",
            """
| Work item | Owner | State | Recovery action |
| --- | --- | --- | --- |
| Fabricated completion | root execution | complete | None |
""",
        )

        for path in (goal_path, progress_path):
            text = path.read_text(encoding="utf-8")
            text = text.replace("status: active", "status: complete", 1)
            path.write_text(text, encoding="utf-8", newline="\n")
        progress_text = progress_path.read_text(encoding="utf-8")
        progress_text = progress_text.replace(
            "execution_health: healthy", "execution_health: inactive", 1
        )
        progress_text, replacements = re.subn(
            r"(?s)(## Open gates\n\n).*?(\n\n## Recovery capsule)",
            r"\1None.\2",
            progress_text,
            count=1,
        )
        self.assertEqual(1, replacements)
        progress_path.write_text(progress_text, encoding="utf-8", newline="\n")

        self.run_tool("render_goal.py", goal_dir)
        invalid = self.run_tool("validate_goal.py", goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("missing selected GPT Pro review: plan round 1", invalid.stderr)
        self.assertIn("every phase to be complete or skipped", invalid.stderr)
        self.assertIn("pending, fail, or blocked verification", invalid.stderr)
        self.assertIn("every custody row to be complete", invalid.stderr)

        goal = load_document(goal_path)
        progress = load_document(progress_path)
        closeout_headers, closeout_rows = parse_table(goal.sections["closeout options"])
        phase_headers, phase_rows = parse_table(progress.sections["phase tracker"])
        self.assertEqual(["Option", "Choice", "Artifact or action"], closeout_headers)
        self.assertEqual("yes", closeout_rows[2][1])
        self.assertEqual(["Phase", "State", "Evidence", "Next gate"], phase_headers)
        self.assertEqual("active", phase_rows[1][1])

        html = (goal_dir / "index.html").read_text(encoding="utf-8")
        self.assertRegex(
            html,
            r'<input type="checkbox" disabled checked '
            r'aria-label="GPT Pro review selection">',
        )
        self.assertIn("1 / 5 phases resolved", html)


if __name__ == "__main__":
    unittest.main()
