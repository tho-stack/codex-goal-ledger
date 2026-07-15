#!/usr/bin/env python3
"""Behavioral tests for bounded Fable scientific rescue and durable capture."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent


class FableRescueTests(unittest.TestCase):
    maxDiff = 5000

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="fable-rescue-tests-")
        self.project = Path(self.temporary.name)
        self.goal_dir = self.project / "docs" / "goals" / "science-test"
        initialized = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "init_goal.py"),
                "--project-root",
                str(self.project),
                "--slug",
                "science-test",
                "--title",
                "Science Test",
                "--why",
                "A hard scientific ambiguity needs bounded rescue.",
                "--outcome",
                "A falsifiable next experiment.",
                "--fable-feedback",
                "no",
                "--fable-rescue",
                "yes",
                "--pro-review",
                "no",
                "--external-review-prompt",
                "no",
                "--codex-review",
                "no",
                "--clean-session-handoff",
                "no",
                "--date",
                "2026-07-15",
            ],
            cwd=SCRIPT_DIR.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, initialized.returncode, initialized.stderr)
        self.evidence = self.project / "experiment.txt"
        self.evidence.write_text("known answer and ambiguous observation\n", encoding="utf-8")
        digest = hashlib.sha256(self.evidence.read_bytes()).hexdigest()
        self.candidate = self.project / "candidate.json"
        candidate = {
            "schema_version": 1,
            "trigger": "failed_approaches",
            "question": "Which mechanism explains the unresolved decay behavior?",
            "operational_blockers": [],
            "uncertainty_metric": {"name": "candidate mechanisms", "lower_is_better": True},
            "attempts": [
                {
                    "approach_family": "analytic",
                    "material_change": "Changed from curve fitting to symbolic bounds.",
                    "uncertainty_before": 2,
                    "uncertainty_after": 2,
                },
                {
                    "approach_family": "simulation",
                    "material_change": "Changed the method family to a seeded solver.",
                    "uncertainty_before": 2,
                    "uncertainty_after": 2,
                },
            ],
            "contradictions": [],
            "known_answer_checks": [],
            "implementation_checks": [],
            "hypotheses": [
                {
                    "name": "physical decay",
                    "strongest_disconfirming_evidence": "The known-answer control is stable.",
                },
                {
                    "name": "solver artifact",
                    "strongest_disconfirming_evidence": "Two solvers agree on the sign.",
                },
            ],
            "verified_facts": [
                {
                    "fact": "The known-answer fixture passes.",
                    "verification_method": "Exact fixture comparison.",
                    "evidence_path": "experiment.txt",
                    "sha256": digest,
                }
            ],
            "constraints": ["Remain read-only outside generated rescue evidence."],
            "non_goals": ["Do not broaden the scientific question."],
            "current_experiment": None,
            "answerability_gap": None,
            "evidence_files": ["experiment.txt"],
        }
        self.candidate.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
        self.fake_log = self.project / "fake-claude-count.log"
        self.fake_claude = self.project / "fake-claude"
        self.fake_claude.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
with open(os.environ["FAKE_CLAUDE_COUNT"], "a", encoding="utf-8") as stream:
    stream.write("call\\n")
assert "--tools" in sys.argv
assert sys.argv[sys.argv.index("--tools") + 1] == ""
assert "ANTHROPIC_API_KEY" not in os.environ
payload = {
  "verdict": "REDESIGN_TEST",
  "summary": "The observations do not yet separate the mechanisms.",
  "root_diagnoses": ["identifiability_problem"],
  "diagnosis_distinguishable": True,
  "alternative_hypotheses": [{
    "hypothesis": "A solver boundary condition mimics decay.",
    "rationale": "Both approaches share the boundary data.",
    "disconfirming_observation": "A boundary-free fixture preserves the decay."
  }],
  "discriminating_experiment": {
    "title": "Boundary-free paired run",
    "method": "Run the same seed with and without the shared boundary condition.",
    "information_gain_rationale": "Only the solver-artifact hypothesis predicts a sign change.",
    "required_evidence": ["paired output"],
    "known_answer_controls": ["zero-decay fixture"]
  },
  "expected_outcomes": [
    {"hypothesis": "physical decay", "observation": "Decay persists.", "interpretation": "Supports physical decay."},
    {"hypothesis": "solver artifact", "observation": "Decay disappears.", "interpretation": "Supports solver artifact."}
  ],
  "stop_conditions": ["The paired outputs remain identical within tolerance."],
  "what_would_change_my_mind": ["A boundary-free known answer fails."],
  "confidence": "moderate",
  "unknowns": ["Boundary sensitivity."],
  "scope_effects": [],
  "requested_artifact": None
}
print(json.dumps({"structured_output": payload, "model": "claude-fable-5", "effort": "xhigh", "duration_ms": 42}))
""",
            encoding="utf-8",
        )
        self.fake_claude.chmod(0o755)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def invoke(self, *args: str, expected: int = 0, discard_output: bool = False):
        environment = os.environ.copy()
        environment["FAKE_CLAUDE_COUNT"] = str(self.fake_log)
        environment["ANTHROPIC_API_KEY"] = "must-not-leak"
        process = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "run_fable_rescue.py"),
                str(self.goal_dir),
                "--claude-bin",
                str(self.fake_claude),
                *args,
            ],
            cwd=SCRIPT_DIR.parent,
            env=environment,
            text=True,
            stdout=subprocess.DEVNULL if discard_output else subprocess.PIPE,
            stderr=subprocess.DEVNULL if discard_output else subprocess.PIPE,
            check=False,
        )
        self.assertEqual(expected, process.returncode, "" if discard_output else process.stderr)
        return process

    def prepare(self) -> dict:
        result = self.invoke(
            "--candidate", str(self.candidate), "--prepare-transmission"
        )
        return json.loads(result.stdout)

    def run_rescue(self, *, discard_output: bool = False) -> None:
        manifest = self.prepare()
        self.invoke(
            "--candidate",
            str(self.candidate),
            "--approve-transmission",
            manifest["approval_digest"],
            discard_output=discard_output,
        )

    def test_lost_wrapper_output_cannot_lose_completed_response(self) -> None:
        self.run_rescue(discard_output=True)
        incident = self.goal_dir / "evidence" / "fable-rescue" / "rescue-001"
        self.assertTrue((incident / "response.md").is_file())
        self.assertTrue((incident / "response.json").is_file())
        self.assertTrue((incident / "transport" / "attempt-1" / "raw-response.json").is_file())
        status = json.loads(
            (incident / "transport" / "attempt-1" / "transport.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("completed", status["state"])
        self.assertRegex(status["stdout_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(["call"], self.fake_log.read_text(encoding="utf-8").splitlines())
        checked = self.invoke("--check")
        self.assertIn("artifacts are valid", checked.stdout)

    def test_reconciliation_locks_predictions_and_outcome_closes_incident(self) -> None:
        self.run_rescue()
        incident = self.goal_dir / "evidence" / "fable-rescue" / "rescue-001"
        reconciliation = self.project / "reconciliation.json"
        reconciliation.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "claims": [
                        {
                            "type": "diagnostic_judgment",
                            "decision": "deferred",
                            "rationale": "Await the paired experiment.",
                        },
                        {
                            "type": "recommendation",
                            "decision": "accepted",
                            "rationale": "The experiment is in scope and safe.",
                        },
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.invoke("--incident", "1", "--reconcile", str(reconciliation))
        locked = json.loads((incident / "reconciliation.json").read_text(encoding="utf-8"))
        self.assertRegex(locked["prediction_sha256"], r"^[0-9a-f]{64}$")

        outcome_evidence = self.project / "paired-output.txt"
        outcome_evidence.write_text("decay persists\n", encoding="utf-8")
        outcome = self.project / "outcome.json"
        outcome.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "observed_result": "Decay persisted without the boundary condition.",
                    "matched_prediction": 1,
                    "hypothesis_update": "Physical decay is now favored.",
                    "evidence_path": "paired-output.txt",
                    "evidence_sha256": hashlib.sha256(outcome_evidence.read_bytes()).hexdigest(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.invoke("--incident", "1", "--record-outcome", str(outcome))
        recorded = json.loads((incident / "outcome.json").read_text(encoding="utf-8"))
        self.assertEqual(locked["prediction_sha256"], recorded["prediction_sha256"])

    def test_operational_blocker_and_stale_evidence_do_not_qualify(self) -> None:
        value = json.loads(self.candidate.read_text(encoding="utf-8"))
        value["operational_blockers"] = ["Claude authentication is unavailable"]
        self.candidate.write_text(json.dumps(value) + "\n", encoding="utf-8")
        rejected = self.invoke(
            "--candidate", str(self.candidate), "--prepare-transmission", expected=1
        )
        self.assertIn("excludes operational blockers", rejected.stderr)
        self.assertFalse(self.fake_log.exists())

    def test_insufficient_packet_gets_one_durable_existing_artifact_followup(self) -> None:
        script = self.fake_claude.read_text(encoding="utf-8")
        marker = 'print(json.dumps({"structured_output": payload, "model": "claude-fable-5", "effort": "xhigh", "duration_ms": 42}))'
        replacement = (
            'if "one permitted existing-artifact supplement" not in sys.argv[-1]:\n'
            '    payload["verdict"] = "INSUFFICIENT_PACKET"\n'
            '    payload["requested_artifact"] = "supplement.txt"\n'
            + marker
        )
        self.assertIn(marker, script)
        self.fake_claude.write_text(script.replace(marker, replacement), encoding="utf-8")
        supplement = self.project / "supplement.txt"
        supplement.write_text("bounded existing evidence\n", encoding="utf-8")

        self.run_rescue()
        incident = self.goal_dir / "evidence" / "fable-rescue" / "rescue-001"
        initial = json.loads((incident / "response.json").read_text(encoding="utf-8"))
        self.assertEqual("INSUFFICIENT_PACKET", initial["verdict"])

        prepared = self.invoke(
            "--incident",
            "1",
            "--supplement",
            "supplement.txt",
            "--prepare-transmission",
        )
        manifest = json.loads(prepared.stdout)
        self.invoke(
            "--incident",
            "1",
            "--supplement",
            "supplement.txt",
            "--approve-transmission",
            manifest["approval_digest"],
        )
        preserved = json.loads(
            (incident / "response-initial.json").read_text(encoding="utf-8")
        )
        final = json.loads((incident / "response.json").read_text(encoding="utf-8"))
        self.assertEqual("INSUFFICIENT_PACKET", preserved["verdict"])
        self.assertEqual("REDESIGN_TEST", final["verdict"])
        self.assertTrue(
            (incident / "transport-followup-1" / "attempt-1" / "raw-response.json").is_file()
        )
        self.assertEqual(
            ["call", "call"], self.fake_log.read_text(encoding="utf-8").splitlines()
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
