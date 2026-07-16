#!/usr/bin/env python3
"""Focused tests for durable, duplicate-safe Claude transport."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from fable_transport import atomic_write_json, run_claude_durable
from ledger_common import LedgerError


class FableTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="fable-transport-tests-")
        self.root = Path(self.temporary.name)
        self.count = self.root / "count.txt"
        self.fake = self.root / "fake.py"
        self.fake.write_text(
            """import json, os
with open(os.environ["COUNT"], "a", encoding="utf-8") as stream:
    stream.write("call\\n")
print(json.dumps({"result": "durable"}))
""",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_completed_matching_invocation_is_reused_without_resubmission(self) -> None:
        environment = os.environ.copy()
        environment["COUNT"] = str(self.count)
        command = [sys.executable, str(self.fake), "prompt"]
        transport = self.root / "transport"
        first = run_claude_durable(
            command,
            cwd=self.root,
            env=environment,
            transport_dir=transport,
            invocation_id="a" * 64,
            timeout_seconds=10,
        )
        second = run_claude_durable(
            command,
            cwd=self.root,
            env=environment,
            transport_dir=transport,
            invocation_id="a" * 64,
            timeout_seconds=10,
        )
        self.assertFalse(first.recovered)
        self.assertTrue(second.recovered)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(["call"], self.count.read_text(encoding="utf-8").splitlines())

    def test_live_matching_pid_refuses_duplicate(self) -> None:
        attempt = self.root / "transport" / "attempt-1"
        attempt.mkdir(parents=True)
        atomic_write_json(
            attempt / "transport.json",
            {
                "schema_version": 1,
                "state": "running",
                "invocation_digest": "b" * 64,
                "attempt": 1,
                "pid": os.getpid(),
            },
        )
        with self.assertRaisesRegex(LedgerError, "do not submit a duplicate"):
            run_claude_durable(
                [sys.executable, str(self.fake), "prompt"],
                cwd=self.root,
                env=os.environ.copy(),
                transport_dir=self.root / "transport",
                invocation_id="b" * 64,
                timeout_seconds=10,
            )

    def test_concurrent_callers_claim_launch_before_process_creation(self) -> None:
        slow = self.root / "slow-success.py"
        slow.write_text(
            """import json, os, time
with open(os.environ["COUNT"], "a", encoding="utf-8") as stream:
    stream.write("call\\n")
time.sleep(0.75)
print(json.dumps({"result": "durable"}))
""",
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment["COUNT"] = str(self.count)
        command = [sys.executable, str(slow), "prompt"]
        transport = self.root / "concurrent-transport"
        barrier = threading.Barrier(2)

        def invoke() -> object:
            barrier.wait(timeout=5)
            try:
                return run_claude_durable(
                    command,
                    cwd=self.root,
                    env=environment,
                    transport_dir=transport,
                    invocation_id="e" * 64,
                    timeout_seconds=10,
                )
            except LedgerError as exc:
                return exc

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: invoke(), range(2)))

        successful = [result for result in results if not isinstance(result, LedgerError)]
        refused = [result for result in results if isinstance(result, LedgerError)]
        self.assertEqual(1, len(successful))
        self.assertEqual(1, len(refused))
        self.assertIn("do not submit a duplicate", str(refused[0]))
        self.assertEqual(["call"], self.count.read_text(encoding="utf-8").splitlines())
        self.assertFalse(
            (transport / "attempt-1" / ".launch-claim.json").exists()
        )

    def test_dead_pre_status_claim_without_outputs_is_recovered(self) -> None:
        dead = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        dead.wait(timeout=5)
        transport = self.root / "stale-unlaunched"
        attempt = transport / "attempt-1"
        attempt.mkdir(parents=True)
        atomic_write_json(
            attempt / ".launch-claim.json",
            {
                "schema_version": 1,
                "claim_id": "stale-unlaunched",
                "invocation_digest": "f" * 64,
                "claimant_pid": dead.pid,
            },
        )
        environment = os.environ.copy()
        environment["COUNT"] = str(self.count)
        result = run_claude_durable(
            [sys.executable, str(self.fake), "prompt"],
            cwd=self.root,
            env=environment,
            transport_dir=transport,
            invocation_id="f" * 64,
            timeout_seconds=10,
        )
        self.assertFalse(result.recovered)
        self.assertEqual(["call"], self.count.read_text(encoding="utf-8").splitlines())
        self.assertFalse((attempt / ".launch-claim.json").exists())

    def test_dead_claim_with_output_evidence_remains_uncertain(self) -> None:
        dead = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        dead.wait(timeout=5)
        transport = self.root / "stale-with-output"
        attempt = transport / "attempt-1"
        attempt.mkdir(parents=True)
        atomic_write_json(
            attempt / ".launch-claim.json",
            {
                "schema_version": 1,
                "claim_id": "stale-with-output",
                "invocation_digest": "1" * 64,
                "claimant_pid": dead.pid,
            },
        )
        (attempt / "raw-response.json").write_text("partial remote evidence\n", encoding="utf-8")
        environment = os.environ.copy()
        environment["COUNT"] = str(self.count)
        with self.assertRaisesRegex(LedgerError, "do not submit a duplicate"):
            run_claude_durable(
                [sys.executable, str(self.fake), "prompt"],
                cwd=self.root,
                env=environment,
                transport_dir=transport,
                invocation_id="1" * 64,
                timeout_seconds=10,
            )
        self.assertFalse(self.count.exists())
        self.assertTrue((attempt / ".launch-claim.json").exists())

    def test_timeout_is_unknown_outcome_and_never_resubmits(self) -> None:
        slow = self.root / "slow.py"
        slow.write_text(
            """import os, time
with open(os.environ["COUNT"], "a", encoding="utf-8") as stream:
    stream.write("call\\n")
time.sleep(5)
""",
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment["COUNT"] = str(self.count)
        transport = self.root / "timeout-transport"
        command = [sys.executable, str(slow), "prompt"]

        with self.assertRaisesRegex(LedgerError, "outcome is uncertain"):
            run_claude_durable(
                command,
                cwd=self.root,
                env=environment,
                transport_dir=transport,
                invocation_id="c" * 64,
                timeout_seconds=1,
            )
        with self.assertRaisesRegex(LedgerError, "do not submit a duplicate"):
            run_claude_durable(
                command,
                cwd=self.root,
                env=environment,
                transport_dir=transport,
                invocation_id="c" * 64,
                timeout_seconds=1,
            )
        self.assertEqual(["call"], self.count.read_text(encoding="utf-8").splitlines())

    def test_multiple_automatic_attempts_are_rejected_before_launch(self) -> None:
        environment = os.environ.copy()
        environment["COUNT"] = str(self.count)
        with self.assertRaisesRegex(LedgerError, "max_attempts must be exactly one"):
            run_claude_durable(
                [sys.executable, str(self.fake), "prompt"],
                cwd=self.root,
                env=environment,
                transport_dir=self.root / "transport",
                invocation_id="d" * 64,
                timeout_seconds=10,
                max_attempts=2,
            )
        self.assertFalse(self.count.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
