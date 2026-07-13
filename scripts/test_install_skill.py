#!/usr/bin/env python3
"""Behavioral tests for the portable skill installer."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
INSTALLER = SCRIPT_DIR / "install_skill.py"


class InstallerTests(unittest.TestCase):
    maxDiff = 4000

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="goal-ledger-installer-")
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_installer(
        self,
        *arguments: object,
        codex_home: Path | None = None,
        expected: int = 0,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        if codex_home is not None:
            environment["CODEX_HOME"] = str(codex_home)
        process = subprocess.run(
            [sys.executable, str(INSTALLER), *(str(argument) for argument in arguments)],
            cwd=SCRIPT_DIR.parent,
            env=environment,
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

    def test_default_install_copies_only_skill_package_and_checks_exact_bytes(self) -> None:
        codex_home = self.root / "codex-home"
        installed = codex_home / "skills" / "codex-goal-ledger"

        result = self.run_installer(codex_home=codex_home)
        self.assertIn("Installed:", result.stdout)
        self.assertEqual(
            {"SKILL.md", "agents", "assets", "references", "scripts"},
            {path.name for path in installed.iterdir()},
        )
        self.assertFalse((installed / "docs").exists())
        self.assertFalse((installed / "PRODUCT.md").exists())
        self.assertFalse((installed / "DESIGN.md").exists())
        self.assertFalse(any(installed.rglob("__pycache__")))

        current = self.run_installer("--check", codex_home=codex_home)
        self.assertIn("Installation is current", current.stdout)
        unchanged = self.run_installer(codex_home=codex_home)
        self.assertIn("Installed:", unchanged.stdout)
        self.assertNotIn("Preserved previous", unchanged.stdout)

    def test_drift_is_preserved_until_explicit_replace_and_backup_remains(self) -> None:
        destination = self.root / "custom-skill"
        self.run_installer("--destination", destination)
        skill = destination / "SKILL.md"
        skill.write_text("local customization\n", encoding="utf-8")

        checked = self.run_installer(
            "--destination", destination, "--check", expected=1
        )
        self.assertIn("stale managed file: SKILL.md", checked.stderr)
        refused = self.run_installer("--destination", destination, expected=1)
        self.assertIn("rerun with --replace", refused.stderr)
        self.assertEqual("local customization\n", skill.read_text(encoding="utf-8"))

        replaced = self.run_installer("--destination", destination, "--replace")
        self.assertIn("Preserved previous installation", replaced.stdout)
        self.assertEqual(
            (SCRIPT_DIR.parent / "SKILL.md").read_bytes(),
            skill.read_bytes(),
        )
        backups = list(self.root.glob("custom-skill.backup-*"))
        self.assertEqual(1, len(backups))
        self.assertEqual(
            "local customization\n",
            (backups[0] / "SKILL.md").read_text(encoding="utf-8"),
        )
        self.run_installer("--destination", destination, "--check")


if __name__ == "__main__":
    unittest.main(verbosity=2)
