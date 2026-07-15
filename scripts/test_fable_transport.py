#!/usr/bin/env python3
"""Focused tests for durable, duplicate-safe Claude transport."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
