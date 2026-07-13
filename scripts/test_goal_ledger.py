#!/usr/bin/env python3
"""Dependency-free behavioral tests for the Codex Goal Ledger tooling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
FIXED_DATE = "2026-07-13"


@dataclass(frozen=True)
class Run:
    returncode: int
    stdout: str
    stderr: str


class GoalLedgerTests(unittest.TestCase):
    maxDiff = 4000

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="goal-ledger-tests-")
        self.project = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_tool(
        self,
        name: str,
        *arguments: object,
        expected: int | None = 0,
    ) -> Run:
        command = [sys.executable, str(SCRIPT_DIR / name), *(str(value) for value in arguments)]
        process = subprocess.run(
            command,
            cwd=SCRIPT_DIR.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        result = Run(process.returncode, process.stdout, process.stderr)
        if expected is not None:
            self.assertEqual(
                expected,
                result.returncode,
                msg=(
                    f"command returned {result.returncode}: {' '.join(command)}\n"
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                ),
            )
        return result

    def init(
        self,
        *,
        project: Path | None = None,
        slug: str = "overnight-build",
        title: str = "Overnight Build",
        why: str = "This work must survive interruption.",
        outcome: str = "A verified durable result.",
        external_review_prompt: str = "no",
        codex_review: str = "no",
        clean_session_handoff: str = "no",
        expected: int | None = 0,
    ) -> tuple[Path, Run]:
        root = project or self.project
        result = self.run_tool(
            "init_goal.py",
            "--project-root",
            root,
            "--slug",
            slug,
            "--title",
            title,
            "--why",
            why,
            "--outcome",
            outcome,
            "--planning-profile",
            "gpt-5.6-sol xhigh",
            "--implementation-profile",
            "gpt-5.6-terra max",
            "--review-profile",
            "gpt-5.6-sol xhigh",
            "--external-review-prompt",
            external_review_prompt,
            "--codex-review",
            codex_review,
            "--clean-session-handoff",
            clean_session_handoff,
            "--date",
            FIXED_DATE,
            expected=expected,
        )
        return root / "docs" / "goals" / slug, result

    def replace_once(self, path: Path, old: str, new: str) -> None:
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, msg=f"fixture token not found in {path}: {old!r}")
        path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

    def render(self, goal_dir: Path, *options: str, expected: int | None = 0) -> Run:
        return self.run_tool("render_goal.py", *options, goal_dir, expected=expected)

    def validate(self, goal_dir: Path, expected: int | None = 0) -> Run:
        return self.run_tool("validate_goal.py", goal_dir, expected=expected)

    def generate_closeout(self, goal_dir: Path, *options: str, expected: int | None = 0) -> Run:
        return self.run_tool(
            "generate_closeout_prompts.py", goal_dir, *options, expected=expected
        )

    def mark_complete(self, goal_dir: Path) -> None:
        goal = goal_dir / "goal.md"
        progress = goal_dir / "progress.md"
        self.replace_once(goal, "status: active", "status: complete")
        self.replace_once(progress, "status: active", "status: complete")
        self.replace_once(progress, "execution_health: healthy", "execution_health: inactive")

        text = progress.read_text(encoding="utf-8")
        for phase in ("Define", "Build", "Verify", "Close"):
            text, count = re.subn(
                rf"^(\| {phase} \| )(?:active|pending)( \|)",
                rf"\1complete\2",
                text,
                count=1,
                flags=re.MULTILINE,
            )
            self.assertEqual(1, count, msg=f"could not complete phase {phase}")
        text = text.replace(
            "| Completion contract | pending | Review the generated goal before implementation. |",
            "| Completion contract | pass | Completion evidence is recorded and reconciled. |",
            1,
        )
        text = text.replace(
            "| Contract review and first milestone | root execution | active |",
            "| Contract review and first milestone | root execution | complete |",
            1,
        )
        text, count = re.subn(
            r"(?s)(## Open gates\n\n).*?(\n\n## Recovery capsule)",
            r"\1None.\2",
            text,
            count=1,
        )
        self.assertEqual(1, count, msg="could not close open gates")
        progress.write_text(text, encoding="utf-8", newline="\n")

    def test_initialization_is_valid_deterministic_and_round_trips_literals(self) -> None:
        title = 'Dawn: "Flight Recorder"'
        literal = "Keep literal {{TITLE}} and {{OUTCOME_HTML}} text intact."
        goal_dir, _ = self.init(title=title, why=literal, outcome=literal)

        expected_files = {
            goal_dir / "goal.md",
            goal_dir / "progress.md",
            goal_dir / "index.html",
            self.project / "docs" / "assets" / "goal-ledger.css",
            self.project / "docs" / "assets" / "goal-ledger.js",
        }
        for path in expected_files:
            self.assertTrue(path.is_file(), msg=f"missing initialized artifact: {path}")
        self.assertTrue((goal_dir / "evidence").is_dir())

        goal_text = (goal_dir / "goal.md").read_text(encoding="utf-8")
        html_text = (goal_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn(title, goal_text)
        self.assertIn("{{TITLE}}", goal_text)
        self.assertIn("{{TITLE}}", html_text)
        self.assertNotIn("2025-", html_text)
        self.assertIn(FIXED_DATE, html_text)

        self.render(goal_dir, "--check")
        self.validate(goal_dir)
        first = (goal_dir / "index.html").read_bytes()
        self.render(goal_dir)
        second = (goal_dir / "index.html").read_bytes()
        self.render(goal_dir)
        third = (goal_dir / "index.html").read_bytes()
        self.assertEqual(first, second)
        self.assertEqual(second, third)

    def test_markdown_title_initializes_to_consistent_visible_text(self) -> None:
        cases = (
            ("markdown-title", "Use *bold* title", r"# Use \*bold\* title"),
            ("literal-title", "C# API_2", r"# C\# API\_2"),
        )
        for slug, title, source_heading in cases:
            with self.subTest(title=title):
                goal_dir, ready = self.init(slug=slug, title=title)
                self.assertIn("Goal ledger ready", ready.stdout)
                self.render(goal_dir, "--check")
                self.validate(goal_dir)
                goal_text = (goal_dir / "goal.md").read_text(encoding="utf-8")
                html = (goal_dir / "index.html").read_text(encoding="utf-8")
                self.assertIn(source_heading, goal_text)
                self.assertIn(f"<title>{title} · Goal Ledger</title>", html)
                self.assertIn(f'<h1 id="goal-title">{title}</h1>', html)

    def test_init_preserves_existing_artifacts_and_rejects_conflicting_partial_state(self) -> None:
        goal_dir, _ = self.init()
        tracked = [
            goal_dir / "goal.md",
            goal_dir / "progress.md",
            goal_dir / "index.html",
            self.project / "docs" / "assets" / "goal-ledger.css",
            self.project / "docs" / "assets" / "goal-ledger.js",
        ]
        before = {path: path.read_bytes() for path in tracked}
        _, rerun = self.init()
        self.assertIn("Preserved:", rerun.stdout)
        self.assertEqual(before, {path: path.read_bytes() for path in tracked})

        stale = b"preserve-this-stale-dashboard\n"
        (goal_dir / "index.html").write_bytes(stale)
        _, conflict = self.init(expected=None)
        self.assertNotEqual(0, conflict.returncode)
        self.assertEqual(stale, (goal_dir / "index.html").read_bytes())

        partial = self.project / "partial"
        partial_goal = partial / "docs" / "goals" / "overnight-build"
        partial_goal.mkdir(parents=True)
        sentinel = b"existing contract must survive\n"
        (partial_goal / "goal.md").write_bytes(sentinel)
        _, partial_run = self.init(project=partial, expected=None)
        self.assertNotEqual(0, partial_run.returncode)
        self.assertEqual(sentinel, (partial_goal / "goal.md").read_bytes())
        self.assertFalse((partial_goal / "progress.md").exists())
        self.assertFalse((partial / "docs" / "assets" / "goal-ledger.css").exists())

    def test_stale_digest_check_mode_never_mutates_then_render_recovers(self) -> None:
        goal_dir, _ = self.init()
        index_path = goal_dir / "index.html"
        old_html = index_path.read_bytes()
        self.replace_once(
            goal_dir / "progress.md",
            "Confirm the contract, execution profile, and first observable milestone.",
            "Resume from the last verified evidence boundary.",
        )

        checked = self.render(goal_dir, "--check", expected=None)
        self.assertNotEqual(0, checked.returncode)
        self.assertIn("stale generated dashboard", checked.stderr)
        self.assertEqual(old_html, index_path.read_bytes())
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("digest is stale", invalid.stderr)

        self.render(goal_dir)
        self.render(goal_dir, "--check")
        self.validate(goal_dir)
        self.assertNotEqual(old_html, index_path.read_bytes())

    def test_sync_asset_check_is_non_mutating_and_sync_repairs_drift(self) -> None:
        goal_dir, _ = self.init()
        css = self.project / "docs" / "assets" / "goal-ledger.css"
        css.write_bytes(b"stale but preserved during check\n")
        stale = css.read_bytes()

        checked = self.render(goal_dir, "--sync-assets", "--check", expected=None)
        self.assertNotEqual(0, checked.returncode)
        self.assertIn("stale shared asset", checked.stderr)
        self.assertEqual(stale, css.read_bytes())

        self.render(goal_dir, "--sync-assets")
        self.render(goal_dir, "--sync-assets", "--check")
        self.validate(goal_dir)
        self.assertNotEqual(stale, css.read_bytes())

    def test_interrupted_execution_and_lost_custody_remain_valid_and_recoverable(self) -> None:
        goal_dir, _ = self.init()
        progress = goal_dir / "progress.md"
        self.replace_once(progress, "execution_health: healthy", "execution_health: interrupted")
        self.replace_once(progress, "| Define | active |", "| Define | blocked |")
        self.replace_once(
            progress,
            "| Contract review and first milestone | root execution | active |",
            "| Contract review and first milestone | root execution | lost |",
        )
        self.replace_once(
            progress,
            "- **Last verified truth:** the ledger artifacts were initialized.",
            "- **Last verified truth:** initialization passed before the root execution stopped.",
        )
        self.replace_once(
            progress,
            "- **Resume at:** review `goal.md`, then update the first active phase.",
            "- **Resume at:** reconcile lost custody, then restart from the recorded gate.",
        )

        self.render(goal_dir)
        self.validate(goal_dir)
        html = (goal_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-execution-health="interrupted"', html)
        self.assertIn('data-state="lost"', html)
        self.assertIn("reconcile lost custody", html)

    def test_valid_completion_passes_all_closeout_invariants(self) -> None:
        goal_dir, _ = self.init()
        self.mark_complete(goal_dir)
        self.replace_once(
            goal_dir / "progress.md",
            "## Open gates\n\nNone.",
            "## Open gates\n\n- None.",
        )
        self.render(goal_dir)
        self.render(goal_dir, "--check")
        self.validate(goal_dir)
        html = (goal_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-goal-status="complete"', html)
        self.assertIn('data-execution-health="inactive"', html)
        self.assertIn("100%", html)
        self.assertIn('<span class="gate-count">0 open</span>', html)
        self.assertIn('<div class="gate-list"><p>No open gates.</p></div>', html)

    def test_no_gate_marker_cannot_hide_narrative_blocker(self) -> None:
        goal_dir, _ = self.init()
        self.mark_complete(goal_dir)
        progress = goal_dir / "progress.md"
        self.replace_once(
            progress,
            "## Open gates\n\nNone.",
            "## Open gates\n\nCritical blocker remains.\n\n- None.",
        )
        self.render(goal_dir)
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("Critical blocker remains", invalid.stderr)
        html = (goal_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn('<span class="gate-count">1 open</span>', html)
        self.assertIn("Critical blocker remains", html)
        self.assertNotIn('<span class="gate-count">0 open</span>', html)

    def test_skips_require_machine_readable_contract_permission(self) -> None:
        goal_dir, _ = self.init()
        self.mark_complete(goal_dir)
        goal = goal_dir / "goal.md"
        progress = goal_dir / "progress.md"
        self.replace_once(progress, "| Close | complete |", "| Close | skipped |")
        self.replace_once(
            progress,
            "| Ledger initialization | pass |",
            "| Ledger initialization | skipped |",
        )
        self.render(goal_dir)

        unauthorized = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, unauthorized.returncode)
        self.assertIn("allowed_skipped_phases does not authorize it", unauthorized.stderr)
        self.assertIn("allowed_skipped_verifications does not authorize it", unauthorized.stderr)

        self.replace_once(goal, "allowed_skipped_phases: none", "allowed_skipped_phases: Close")
        self.replace_once(
            goal,
            "allowed_skipped_verifications: none",
            "allowed_skipped_verifications: Ledger initialization",
        )
        self.render(goal_dir)
        self.validate(goal_dir)

    def test_init_rejects_template_breaking_headings_before_writes(self) -> None:
        project = self.project / "unsafe-markdown"
        goal_dir, rejected = self.init(
            project=project,
            slug="unsafe-markdown",
            why="Useful context.\n\n## Outcome\n\nTemplate takeover.",
            expected=None,
        )
        self.assertNotEqual(0, rejected.returncode)
        self.assertIn("template owns those headings", rejected.stderr)
        self.assertFalse(goal_dir.exists())
        self.assertFalse((project / "docs").exists())

        indented_project = self.project / "indented-heading"
        indented_goal, indented = self.init(
            project=indented_project,
            slug="indented-heading",
            why="Useful context.\n\n ## Outcome\n\nIndented takeover.",
            expected=None,
        )
        self.assertNotEqual(0, indented.returncode)
        self.assertIn("template owns those headings", indented.stderr)
        self.assertFalse(indented_goal.exists())
        self.assertFalse((indented_project / "docs").exists())

    def test_unbalanced_fences_fail_before_init_and_during_validation(self) -> None:
        project = self.project / "unsafe-fence"
        goal_dir, rejected = self.init(
            project=project,
            slug="unsafe-fence",
            why="Context.\n\n```text\nunclosed",
            expected=None,
        )
        self.assertNotEqual(0, rejected.returncode)
        self.assertIn("unbalanced fenced code block", rejected.stderr)
        self.assertFalse(goal_dir.exists())
        self.assertFalse((project / "docs").exists())

        valid_goal, _ = self.init(slug="manual-fence")
        self.replace_once(
            valid_goal / "goal.md",
            "This work must survive interruption.",
            "This work must survive interruption.\n\n```text\nunclosed",
        )
        invalid = self.validate(valid_goal, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("unbalanced fenced code block", invalid.stderr)

        cross_goal, _ = self.init(slug="cross-section-fence")
        self.replace_once(
            cross_goal / "goal.md",
            "This work must survive interruption.",
            "Context.\n\n```text",
        )
        self.replace_once(
            cross_goal / "goal.md",
            "## Outcome\n\nA verified durable result.",
            "## Outcome\n\n```\nA verified durable result.",
        )
        cross_invalid = self.validate(cross_goal, expected=None)
        self.assertNotEqual(0, cross_invalid.returncode)
        self.assertIn("fences may not cross section boundaries", cross_invalid.stderr)

    def test_duplicate_frontmatter_keys_fail_without_ambiguity(self) -> None:
        goal_dir, _ = self.init()
        goal = goal_dir / "goal.md"
        self.replace_once(
            goal,
            "status: active\ncreated:",
            "status: active\nstatus: blocked\ncreated:",
        )
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("duplicate frontmatter key: status", invalid.stderr)

    def test_table_width_mismatch_never_hides_extra_or_missing_cells(self) -> None:
        extra_goal, _ = self.init(slug="extra-table-cell")
        extra_progress = extra_goal / "progress.md"
        self.replace_once(
            extra_progress,
            "and shared assets exist. |",
            "and shared assets exist. | unresolved caveat |",
        )
        extra = self.validate(extra_goal, expected=None)
        self.assertNotEqual(0, extra.returncode)
        self.assertIn("exactly 3 cells; found 4", extra.stderr)
        self.assertIn("Escape literal pipes", extra.stderr)

        missing_goal, _ = self.init(slug="missing-table-cell")
        missing_progress = missing_goal / "progress.md"
        self.replace_once(
            missing_progress,
            "| Ledger initialization | pass | `goal.md`, `progress.md`, `index.html`, and shared assets exist. |",
            "| Ledger initialization | pass |",
        )
        missing = self.validate(missing_goal, expected=None)
        self.assertNotEqual(0, missing.returncode)
        self.assertIn("exactly 3 cells; found 2", missing.stderr)

    def test_contradictory_completion_and_invalid_states_fail_clearly(self) -> None:
        goal_dir, _ = self.init()
        self.mark_complete(goal_dir)
        progress = goal_dir / "progress.md"
        self.replace_once(progress, "execution_health: inactive", "execution_health: healthy")
        self.replace_once(progress, "| Build | complete |", "| Build | active |")
        self.replace_once(
            progress,
            "| Completion contract | pass |",
            "| Completion contract | fail |",
        )
        self.replace_once(
            progress,
            "| Contract review and first milestone | root execution | complete |",
            "| Contract review and first milestone | root execution | queued |",
        )
        self.replace_once(progress, "## Open gates\n\nNone.", "## Open gates\n\n- Final review remains open.")
        self.render(goal_dir)
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        for message in (
            "execution_health: inactive",
            "every phase to be complete or skipped",
            "pending, fail, or blocked verification",
            "every custody row to be complete",
            "cannot retain open gates",
        ):
            self.assertIn(message, invalid.stderr)

        other_project = self.project / "invalid-health"
        other_goal, _ = self.init(project=other_project, slug="invalid-health")
        self.replace_once(
            other_goal / "progress.md",
            "execution_health: healthy",
            "execution_health: teleporting",
        )
        self.render(other_goal)
        invalid_health = self.validate(other_goal, expected=None)
        self.assertNotEqual(0, invalid_health.returncode)
        self.assertIn("invalid execution_health", invalid_health.stderr)

    def test_complete_goal_must_resolve_closeout_questions(self) -> None:
        goal_dir, _ = self.init(external_review_prompt="ask")
        self.mark_complete(goal_dir)
        self.render(goal_dir)
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn(
            "complete goals must resolve every Closeout options choice to yes or no",
            invalid.stderr,
        )

    def test_selected_prompt_artifacts_are_deterministic_and_machine_independent(self) -> None:
        goal_dir, _ = self.init(
            external_review_prompt="yes",
            clean_session_handoff="yes",
        )
        generated = self.generate_closeout(goal_dir)
        self.assertIn("review-prompt.md", generated.stdout)
        self.assertIn("handoff-prompt.md", generated.stdout)
        self.generate_closeout(goal_dir, "--check")

        for name in ("review-prompt.md", "handoff-prompt.md"):
            path = goal_dir / name
            self.assertTrue(path.is_file())
            content = path.read_text(encoding="utf-8")
            self.assertIn("goal.md", content)
            self.assertIn("progress.md", content)
            self.assertNotIn(str(self.project), content)

        first = (goal_dir / "review-prompt.md").read_bytes()
        self.generate_closeout(goal_dir)
        self.assertEqual(first, (goal_dir / "review-prompt.md").read_bytes())

        self.mark_complete(goal_dir)
        self.render(goal_dir)
        self.validate(goal_dir)
        (goal_dir / "review-prompt.md").write_text("stale\n", encoding="utf-8")
        stale = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, stale.returncode)
        self.assertIn("stale selected closeout prompt", stale.stderr)

    def test_shipped_dashboard_has_ibm_typography_and_no_print_contract(self) -> None:
        package_root = SCRIPT_DIR.parent
        sources = {
            "template": package_root / "assets" / "templates" / "index.html",
            "styles": package_root / "assets" / "goal-ledger.css",
            "behavior": package_root / "assets" / "goal-ledger.js",
        }
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in sources.values()
        )
        lowered = combined.casefold()

        self.assertIn('"ibm plex sans"', lowered)
        self.assertIn('"ibm plex mono"', lowered)
        for forbidden in (
            "window.print",
            "@media print",
            "data-print",
            ">print<",
            "pdf",
            "chrome_executable",
            "playwright_module",
            "/applications/",
        ):
            self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
