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
        fable_feedback: str = "no",
        fable_rescue: str = "no",
        fable_review_rounds: int = 1,
        pro_review: str = "no",
        pro_review_stage: str = "plan",
        pro_review_gate: str = "required",
        external_review_prompt: str = "no",
        codex_review: str = "no",
        clean_session_handoff: str = "no",
        planning_input_assessment: str = (
            "- **Required before execution:** None.\n"
            "- **Optional, improves result:** No additional information would materially improve this plan."
        ),
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
            "--planning-input-assessment",
            planning_input_assessment,
            "--planning-profile",
            "gpt-5.6-sol xhigh",
            "--implementation-profile",
            "gpt-5.6-luna max",
            "--review-profile",
            "gpt-5.6-sol xhigh",
            "--fable-feedback",
            fable_feedback,
            "--fable-review-rounds",
            fable_review_rounds,
            "--fable-rescue",
            fable_rescue,
            "--pro-review",
            pro_review,
            "--pro-review-stage",
            pro_review_stage,
            "--pro-review-gate",
            pro_review_gate,
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
                r"\1complete\2",
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
            "| HTTP dashboard preview | pending | Serve HTTP, then present and verify a visible in-app Browser tab in this Codex task; never use `file://`. |",
            "| HTTP dashboard preview | pass | A healthy HTTP URL and visible same-task in-app Browser deliverable were verified. |",
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
        self.assertIn("ledger_version: 7", goal_text)
        self.assertIn("pro_review_delivery: auto-ui", goal_text)
        self.assertIn("fable_review_rounds: 1", goal_text)
        self.assertIn("gpt-5.6-luna max", goal_text)
        self.assertIn("Invoked profile", goal_text)
        self.assertIn("Planning input assessment", goal_text)
        self.assertIn("Claude Fable peer feedback | no", goal_text)
        self.assertIn("Claude Fable scientific rescue | no", goal_text)
        self.assertIn("GPT Pro review | no", goal_text)
        self.assertIn('type="checkbox" disabled', html_text)
        self.assertIn("Ask Fable · 1 round", html_text)
        self.assertIn("Enable scientific rescue", html_text)
        self.assertIn("Ask GPT Pro · plan · 1 round", html_text)
        self.assertIn("Progress without a synthetic score", html_text)
        self.assertIn("Review circuit", html_text)
        self.assertIn("1 / 5 phases resolved", html_text)
        self.assertRegex(
            html_text,
            r'goal-ledger\.css\?v=[0-9a-f]{12}',
        )
        self.assertRegex(
            html_text,
            r'goal-ledger\.js\?v=[0-9a-f]{12}',
        )

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

    def test_planning_input_assessment_requires_defaults_for_optional_context(self) -> None:
        valid_goal, _ = self.init(
            slug="planning-input-valid",
            planning_input_assessment=(
                "- **Required before execution:** None.\n"
                "- **Optional, improves result:**\n"
                "  - **Information:** Target browser versions.\n"
                "  - **What it improves:** Compatibility coverage.\n"
                "  - **Default if omitted:** Test current Codex Preview and localhost."
            ),
        )
        self.validate(valid_goal)

        invalid_goal, _ = self.init(
            slug="planning-input-invalid",
            planning_input_assessment=(
                "- **Required before execution:** None.\n"
                "- **Optional, improves result:** Target browser versions improve compatibility."
            ),
        )
        invalid = self.validate(invalid_goal, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("Default if omitted", invalid.stderr)

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

    def test_render_rejects_symlinked_dashboard_and_asset_without_overwrite(self) -> None:
        goal_dir, _ = self.init()
        dashboard = goal_dir / "index.html"
        original_dashboard = dashboard.read_bytes()
        outside_dashboard = self.project / "outside-dashboard.html"
        outside_dashboard.write_bytes(b"preserve external dashboard\n")
        dashboard.unlink()
        dashboard.symlink_to(outside_dashboard)

        rejected_dashboard = self.render(goal_dir, expected=None)
        self.assertNotEqual(0, rejected_dashboard.returncode)
        self.assertIn("must not be a symlink", rejected_dashboard.stderr)
        self.assertEqual(b"preserve external dashboard\n", outside_dashboard.read_bytes())
        self.assertTrue(dashboard.is_symlink())

        dashboard.unlink()
        dashboard.write_bytes(original_dashboard)
        asset = self.project / "docs" / "assets" / "goal-ledger.css"
        outside_asset = self.project / "outside-asset.css"
        outside_asset.write_bytes(b"preserve external asset\n")
        asset.unlink()
        asset.symlink_to(outside_asset)

        rejected_asset = self.render(goal_dir, "--sync-assets", expected=None)
        self.assertNotEqual(0, rejected_asset.returncode)
        self.assertIn("must not be a symlink", rejected_asset.stderr)
        self.assertEqual(b"preserve external asset\n", outside_asset.read_bytes())
        self.assertTrue(asset.is_symlink())

    def test_sync_assets_rejects_symlinked_docs_ancestor_without_external_write(self) -> None:
        outside_project = self.project / "outside-project"
        outside_goal, _ = self.init(
            project=outside_project,
            slug="ancestor-target",
        )
        outside_asset = outside_project / "docs" / "assets" / "goal-ledger.css"
        outside_asset.write_bytes(b"preserve ancestor target\n")

        alias_project = self.project / "alias-project"
        alias_project.mkdir()
        (alias_project / "docs").symlink_to(
            outside_project / "docs",
            target_is_directory=True,
        )
        aliased_goal = (
            alias_project / "docs" / "goals" / outside_goal.name
        )

        rejected = self.render(aliased_goal, "--sync-assets", expected=None)
        self.assertNotEqual(0, rejected.returncode)
        self.assertIn("ancestor must not be a symlink", rejected.stderr)
        self.assertEqual(b"preserve ancestor target\n", outside_asset.read_bytes())

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
        self.assertIn("5 / 5 phases resolved", html)
        self.assertIn("0 open", html)
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

    def test_wrapped_open_gate_items_render_once_with_complete_text(self) -> None:
        goal_dir, _ = self.init()
        progress = goal_dir / "progress.md"
        self.replace_once(
            progress,
            "- Confirm the success criteria are observable and sufficient.\n"
            "- Confirm the effective execution profile before claiming model routing.",
            "- Preserve the exact reviewed manifest while the independent reviewer\n"
            "  records its verdict outside those bytes.\n"
            "- Keep unrelated repository changes outside this goal's custody and\n"
            "  retain their original ownership.",
        )
        self.render(goal_dir)
        self.validate(goal_dir)

        html = (goal_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn('<span class="gate-count">2 open</span>', html)
        self.assertIn(
            "<li>Preserve the exact reviewed manifest while the independent reviewer "
            "records its verdict outside those bytes.</li>",
            html,
        )
        self.assertIn(
            "<li>Keep unrelated repository changes outside this goal's custody and "
            "retain their original ownership.</li>",
            html,
        )
        self.assertNotIn("<li>records its verdict", html)

        self.replace_once(
            goal_dir / "index.html",
            '<span class="gate-count">2 open</span>',
            '<span class="gate-count">3 open</span>',
        )
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("open-gate rendering count mismatch", invalid.stderr)

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

    def test_complete_goal_requires_selected_fable_evidence_and_verification(self) -> None:
        goal_dir, _ = self.init(fable_feedback="yes")
        initial_html = (goal_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn('type="checkbox" disabled checked', initial_html)
        self.mark_complete(goal_dir)
        self.render(goal_dir)
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("missing selected Fable feedback", invalid.stderr)
        self.assertIn(
            "select Claude Fable peer feedback require a passing Verification row",
            invalid.stderr,
        )

    def test_complete_goal_requires_native_pro_custody_and_verification(self) -> None:
        goal_dir, _ = self.init(pro_review="yes")
        self.mark_complete(goal_dir)
        self.render(goal_dir)
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("missing selected GPT Pro review: plan round 1", invalid.stderr)
        self.assertIn(
            "select GPT Pro review require a passing Verification row",
            invalid.stderr,
        )

    def test_selected_pro_choice_rejects_a_conversational_approval_gate(self) -> None:
        goal_dir, _ = self.init(pro_review="yes")
        progress = goal_dir / "progress.md"
        self.replace_once(
            progress,
            "Review the contract and start the first evidence-producing milestone.",
            "To resume, reply that you approve sending the packet for GPT Pro review.",
        )
        self.render(goal_dir)
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("remove the conversational GPT Pro approval gate", invalid.stderr)

    def test_started_goal_rejects_reauthorization_of_in_scope_execution(self) -> None:
        goal_dir, _ = self.init()
        progress = goal_dir / "progress.md"
        self.replace_once(
            progress,
            "Review the contract and start the first evidence-producing milestone.",
            "To resume, explicitly authorize one v3 plant-blind qualification bound to "
            "the frozen manifest and resource budget.",
        )
        self.render(goal_dir)
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn(
            "remove the repeated in-scope execution approval gate; starting the goal "
            "authorizes the entire accepted execution envelope in Scope and Authorization",
            invalid.stderr,
        )

    def test_started_goal_rejects_reauthorization_of_hardware_research(self) -> None:
        goal_dir, _ = self.init()
        progress = goal_dir / "progress.md"
        self.replace_once(
            progress,
            "Review the contract and start the first evidence-producing milestone.",
            "Await explicit owner authorization before continuing the hardware and component "
            "research already recorded in Scope.",
        )
        self.render(goal_dir)
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("remove the repeated in-scope execution approval gate", invalid.stderr)

    def test_real_external_boundary_may_still_require_owner_approval(self) -> None:
        goal_dir, _ = self.init()
        progress = goal_dir / "progress.md"
        self.replace_once(
            progress,
            "Review the contract and start the first evidence-producing milestone.",
            "Await owner approval before the external transmission of the implementation "
            "packet.",
        )
        self.render(goal_dir)
        self.validate(goal_dir)

    def test_action_outside_recorded_envelope_may_require_owner_approval(self) -> None:
        goal_dir, _ = self.init()
        progress = goal_dir / "progress.md"
        self.replace_once(
            progress,
            "Review the contract and start the first evidence-producing milestone.",
            "Await owner approval because this live hardware experiment is outside the "
            "recorded envelope.",
        )
        self.render(goal_dir)
        self.validate(goal_dir)

    def test_multiple_fable_rounds_are_recorded_and_validated(self) -> None:
        goal_dir, _ = self.init(fable_feedback="yes", fable_review_rounds=3)
        goal_text = (goal_dir / "goal.md").read_text(encoding="utf-8")
        html_text = (goal_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn("fable_review_rounds: 3", goal_text)
        self.assertIn(
            "authorizes 3 sequential read-only Claude review rounds through Anthropic Claude",
            goal_text,
        )
        self.assertIn("Ask Fable · 3 rounds", html_text)
        self.validate(goal_dir)

        self.replace_once(goal_dir / "goal.md", "fable_review_rounds: 3", "fable_review_rounds: 11")
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("fable_review_rounds must be an integer from 1 to 10", invalid.stderr)

    def test_selected_fable_choice_rejects_a_conversational_approval_gate(self) -> None:
        goal_dir, _ = self.init(fable_feedback="yes")
        goal_text = (goal_dir / "goal.md").read_text(encoding="utf-8")
        self.assertIn(
            "A recorded Claude Fable `yes` authorizes the configured lane",
            goal_text,
        )
        progress = goal_dir / "progress.md"
        self.replace_once(
            progress,
            "Review the contract and start the first evidence-producing milestone.",
            "To resume, reply: I approve sending planning files to Claude Fable.",
        )
        self.render(goal_dir)
        invalid = self.validate(goal_dir, expected=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn(
            "remove the conversational Claude Fable approval gate; the one-time goal-level "
            "Fable authorization covers every configured transmission inside its disclosed "
            "envelope",
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

    def test_skill_asks_closeout_questions_before_unattended_execution(self) -> None:
        package_root = SCRIPT_DIR.parent
        skill = (package_root / "SKILL.md").read_text(encoding="utf-8")
        workflow = (package_root / "references" / "workflow.md").read_text(
            encoding="utf-8"
        )
        closeout = (package_root / "references" / "closeout-kit.md").read_text(
            encoding="utf-8"
        )
        controls = (package_root / "references" / "planning-controls.md").read_text(
            encoding="utf-8"
        )
        default_prompt = (package_root / "agents" / "openai.yaml").read_text(
            encoding="utf-8"
        )

        for contract in (skill, workflow, closeout):
            self.assertIn("checkbox", contract)
            self.assertIn("unattended execution", contract)
            self.assertIn("before", contract.casefold())

        for contract in (skill, workflow, closeout):
            lowered = contract.casefold()
            self.assertIn("native", lowered)
            self.assertIn("approval", lowered)
            self.assertIn("manifest", lowered)

        for contract in (skill, workflow):
            self.assertIn("Optional, improves result", contract)
            self.assertIn("Default if omitted", contract)
            self.assertIn("must not block", contract)

        self.assertLess(skill.index("request_user_input"), skill.index("## Operate"))
        self.assertIn("Approve selected lanes", skill)
        self.assertIn("literal checkboxes", controls)
        self.assertIn("Do not ask for a typed approval sentence afterward", controls)
        self.assertIn("Luna | Max | `goal-ledger-implementer`", controls)
        self.assertIn("Sol | Ultra | `goal-ledger-implementer-sol-ultra`", controls)
        self.assertIn(
            "not a literal multi-select checkbox group or range slider",
            controls,
        )
        self.assertIn("Do not ask the user to type or click a second", controls)
        self.assertIn("first planning checkpoint", default_prompt)
        self.assertIn("optional Claude Fable planning rounds", default_prompt)
        self.assertIn("bounded scientific rescue", default_prompt)
        self.assertIn("native GPT Pro review", default_prompt)
        self.assertIn("bundled restricted MCP App", default_prompt)
        self.assertIn("app-native controls", default_prompt)
        self.assertIn("owner-facing external-review approval routing", default_prompt)
        self.assertIn("multi_agent_v2", default_prompt)
        self.assertIn("extra context that could improve", default_prompt)

    def test_skill_requires_visible_same_task_preview_delivery(self) -> None:
        package_root = SCRIPT_DIR.parent
        contracts = (
            (package_root / "SKILL.md").read_text(encoding="utf-8"),
            (package_root / "references" / "workflow.md").read_text(encoding="utf-8"),
            (package_root / "references" / "closeout-kit.md").read_text(
                encoding="utf-8"
            ),
        )
        for contract in contracts:
            lowered = contract.casefold()
            self.assertIn("same codex task", lowered)
            self.assertIn("visibility", lowered)
            self.assertIn("deliverable", lowered)
            self.assertIn("hidden", lowered)
            self.assertIn("do not claim", lowered)

    def test_skill_routes_frequent_operational_gates_to_fast_reviewer(self) -> None:
        package_root = SCRIPT_DIR.parent
        skill = (package_root / "SKILL.md").read_text(encoding="utf-8")
        profile = (
            package_root
            / "assets"
            / "agent-profiles"
            / "goal-ledger-gate-reviewer.toml"
        ).read_text(encoding="utf-8")
        self.assertIn("goal-ledger-gate-reviewer", skill)
        self.assertIn("GO`, `BLOCKED`, or `NEEDS_DEEP_REVIEW", skill)
        self.assertIn("read-only default subagent", skill)
        self.assertIn("model `gpt-5.6-luna` and effort `high`", skill)
        self.assertIn('model = "gpt-5.6-luna"', profile)
        self.assertIn('model_reasoning_effort = "high"', profile)
        self.assertIn("Remain read-only", profile)

    def test_planning_contract_keeps_independent_workstreams_parallel(self) -> None:
        package_root = SCRIPT_DIR.parent
        skill = (package_root / "SKILL.md").read_text(encoding="utf-8")
        workflow = (package_root / "references" / "workflow.md").read_text(
            encoding="utf-8"
        )
        progress_template = (
            package_root / "assets" / "templates" / "progress.md"
        ).read_text(encoding="utf-8")
        progress_reference = (
            package_root / "references" / "progress-template.md"
        ).read_text(encoding="utf-8")

        for contract in (skill, workflow, progress_reference):
            self.assertIn("not a mutex", contract)
            self.assertIn("dependency-free", contract)
            self.assertIn("research", contract)
            self.assertIn("implementation", contract)
            self.assertIn("reserve", contract.casefold())
            self.assertIn("recursive", contract.casefold())
            self.assertIn("interrupted", contract.casefold())

        self.assertIn("## Parallel workstreams", progress_template)
        self.assertIn(
            "Workstream | Deliverable | Blocked by | Mutation class | State | Evidence",
            progress_template,
        )
        self.assertIn("read-only", progress_template)


if __name__ == "__main__":
    unittest.main(verbosity=2)
