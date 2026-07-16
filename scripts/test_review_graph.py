#!/usr/bin/env python3
"""Behavioral tests for the evidence-derived dashboard review circuit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent


class ReviewGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="goal-ledger-graph-")
        self.project = Path(self.temporary.name) / "project"
        self.run_tool(
            "init_goal.py",
            "--project-root",
            self.project,
            "--slug",
            "graph-test",
            "--title",
            "Review Graph Test",
            "--why",
            "Review loops need durable visual evidence.",
            "--outcome",
            "The dashboard shows a blocked review, revision, and signed-off re-review.",
            "--fable-feedback",
            "no",
            "--fable-rescue",
            "no",
            "--pro-review",
            "yes",
            "--pro-review-rounds",
            "2",
            "--pro-review-stage",
            "plan",
            "--pro-review-delivery",
            "owner-handoff",
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
        self.goal_dir = self.project / "docs" / "goals" / "graph-test"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_tool(self, name: str, *args: object, expected: int = 0):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / name), *(str(arg) for arg in args)],
            cwd=SCRIPT_DIR.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(expected, result.returncode, msg=result.stdout + result.stderr)
        return result

    def complete_round(self, number: int, verdict: str) -> None:
        self.run_tool(
            "run_pro_review.py",
            "prepare",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            number,
            "--decision",
            "Approve this plan for implementation.",
        )
        self.run_tool(
            "run_pro_review.py",
            "record-submission",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            number,
            "--model-visible",
            "Pro Extended",
            "--transport",
            "owner-handoff",
            "--thread",
            f"Graph review round {number}",
        )
        response = self.project / f"response-{number}.md"
        response.write_text(
            f"Verdict: {verdict}\n\n"
            "Required changes:\n- Clarify the review route.\n\n"
            "Risks:\n- None beyond the recorded finding.\n\n"
            "Tests or verification:\n- Render the circuit.\n\n"
            "Reasoning notes:\n- Evidence is sufficient.\n",
            encoding="utf-8",
        )
        self.run_tool(
            "run_pro_review.py",
            "record-response",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            number,
            "--response-file",
            response,
        )
        raw_hash = hashlib.sha256(response.read_bytes()).hexdigest()
        reconciliation = self.project / f"reconciliation-{number}.json"
        reconciliation.write_text(
            json.dumps(
                {
                    "pro_verdict": verdict,
                    "response_sha256": raw_hash,
                    "items": (
                        [
                            {
                                "classification": "FIX",
                                "finding": "Clarify the review route.",
                                "disposition": "Accepted and updated before the next round.",
                                "evidence": ["goal.md and progress.md"],
                            }
                        ]
                        if verdict == "BLOCKED"
                        else []
                    ),
                    "local_verification": ["Reviewed the current packet and route state."],
                    "next_action": (
                        "Prepare the revised plan round."
                        if verdict == "BLOCKED"
                        else "Begin implementation."
                    ),
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
            number,
            "--reconciliation-file",
            reconciliation,
        )

    def test_blocked_revision_signed_off_loop_is_visible_and_deterministic(self) -> None:
        self.complete_round(1, "BLOCKED")
        self.complete_round(2, "SIGNED OFF")
        self.run_tool("render_goal.py", self.goal_dir)
        first = (self.goal_dir / "index.html").read_bytes()
        self.run_tool("render_goal.py", self.goal_dir)
        self.assertEqual(first, (self.goal_dir / "index.html").read_bytes())
        html = first.decode("utf-8")
        self.assertIn("GPT Pro R1", html)
        self.assertIn("GPT Pro R2", html)
        self.assertNotIn("Verified fixes before re-review", html)
        self.assertIn("return for revision", html)
        self.assertIn('data-direction="return"', html)
        self.assertIn('data-layout="flow"', html)
        self.assertIn('class="review-step"', html)
        self.assertIn('class="review-node-order" aria-hidden="true">01</span>', html)
        self.assertIn(
            'data-node="pro-plan-1" data-state="blocked" data-completed="true"',
            html,
        )
        self.assertIn(
            'data-node="define-gate" data-state="active" data-current="true"',
            html,
        )
        self.assertIn("Define gate", html)
        self.assertIn('href="#briefing"', html)
        self.assertNotIn(
            'data-node="build" data-state="pending" data-current="true"',
            html,
        )
        self.assertIn('class="review-node-check" aria-label="Completed review"', html)
        self.assertIn("1 / 1 selected lanes reconciled", html)
        self.assertNotIn("COMPLETION_PERCENT", html)

    def test_historic_plan_reviews_remain_after_implementation_stage_is_selected(self) -> None:
        self.complete_round(1, "BLOCKED")
        self.complete_round(2, "SIGNED OFF")
        goal_path = self.goal_dir / "goal.md"
        goal_text = goal_path.read_text(encoding="utf-8")
        goal_path.write_text(
            goal_text.replace(
                "pro_review_stage: plan", "pro_review_stage: implementation", 1
            ),
            encoding="utf-8",
        )

        self.run_tool("render_goal.py", self.goal_dir)
        html = (self.goal_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn(
            'data-node="pro-plan-1" data-state="blocked" data-completed="true"',
            html,
        )
        self.assertIn(
            'data-node="pro-plan-2" data-state="pass" data-completed="true"',
            html,
        )
        self.assertIn(
            'data-node="pro-implementation-1" data-state="pending"',
            html,
        )
        self.assertIn(
            'data-node="pro-implementation-2" data-state="pending"',
            html,
        )
        self.assertIn("0 / 1 selected lanes reconciled", html)

    def test_current_marker_follows_review_gate_not_rescue_build_placeholder(self) -> None:
        html = (self.goal_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn(
            'data-node="pro-plan-1" data-state="pending" data-current="true"',
            html,
        )
        self.assertIn(
            'data-node="build-rescue" data-state="pending"',
            html,
        )
        self.assertNotIn(
            'data-node="build-rescue" data-state="active" data-current="true"',
            html,
        )

    def test_later_submitted_round_is_current_after_reconciled_blocked_round(self) -> None:
        self.complete_round(1, "BLOCKED")
        self.run_tool(
            "run_pro_review.py",
            "prepare",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            2,
            "--decision",
            "Approve this revised plan for implementation.",
        )
        self.run_tool(
            "run_pro_review.py",
            "record-submission",
            self.goal_dir,
            "--stage",
            "plan",
            "--round",
            2,
            "--model-visible",
            "Pro Extended",
            "--transport",
            "owner-handoff",
            "--thread",
            "Graph review round 2",
        )
        self.run_tool("render_goal.py", self.goal_dir)
        html = (self.goal_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn(
            'data-node="pro-plan-1" data-state="blocked"',
            html,
        )
        self.assertNotIn(
            'data-node="pro-plan-1" data-state="blocked" data-current="true"',
            html,
        )
        self.assertIn(
            'data-node="pro-plan-2" data-state="active" data-current="true"',
            html,
        )

    def test_dashboard_css_keeps_review_graph_responsive_and_reduced_motion(self) -> None:
        css = (SCRIPT_DIR.parent / "assets" / "goal-ledger.css").read_text()
        self.assertIn(".review-circuit-scroll", css)
        self.assertIn("overflow-x: visible", css)
        self.assertIn('grid-template-columns: repeat(auto-fit, minmax(min(100%, 13.5rem), 1fr))', css)
        self.assertIn("grid-template-columns: clamp(6rem, 9vw, 8rem) minmax(0, 1fr)", css)
        self.assertIn("justify-content: center", css)
        edge_rule = css.split(".review-edge > span {", 1)[1].split("}", 1)[0]
        self.assertIn("font-size: 1.45rem", edge_rule)
        self.assertIn("text-align: center", edge_rule)
        self.assertNotIn("text-align: end", edge_rule)
        self.assertIn("@keyframes active-node-sweep", css)
        self.assertIn("@keyframes active-node-breathe", css)
        self.assertIn("@keyframes active-phase-beacon", css)
        self.assertIn('.review-step[data-current="true"] .review-node-title::after', css)
        self.assertIn('content: "Live"', css)
        self.assertIn('.activity-row[data-state="active"]', css)
        self.assertIn('animation: none !important', css)
        opening_rule = css.split(".opening {", 1)[1].split("}", 1)[0]
        self.assertIn("align-items: start", opening_rule)
        self.assertNotIn("align-items: end", opening_rule)
        self.assertNotIn("min-width: max-content", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)


if __name__ == "__main__":
    unittest.main(verbosity=2)
