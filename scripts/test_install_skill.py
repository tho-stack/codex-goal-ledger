#!/usr/bin/env python3
"""Behavioral tests for the portable skill installer."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agent_profiles import AGENT_NAMES


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

    def test_owned_agents_install_check_and_uninstall_without_touching_other_agents(self) -> None:
        codex_home = self.root / "codex-home-agents"
        agents = codex_home / "agents"
        agents.mkdir(parents=True)
        unrelated = agents / "my-existing-agent.toml"
        unrelated.write_text('name = "mine"\n', encoding="utf-8")
        config = codex_home / "config.toml"
        original = 'model = "gpt-5.6-sol"\n\n[agents]\nmax_threads = 8\n'
        config.write_text(original, encoding="utf-8")

        installed = self.run_installer("--with-agents", codex_home=codex_home)
        self.assertIn("Restart Codex", installed.stdout)
        for name in AGENT_NAMES:
            profile = agents / f"{name}.toml"
            self.assertTrue(profile.is_file())
            self.assertIn(f"[agents.{name}]", config.read_text(encoding="utf-8"))
        self.assertEqual('name = "mine"\n', unrelated.read_text(encoding="utf-8"))
        installed_config = config.read_text(encoding="utf-8")
        self.assertIn(original.rstrip(), installed_config)
        self.assertIn("[features.multi_agent_v2]", installed_config)
        self.assertIn("hide_spawn_agent_metadata = false", installed_config)
        self.assertIn("max_concurrent_threads_per_session = 8", installed_config)
        self.assertIn('tool_namespace = "agents"', installed_config)

        checked = self.run_installer(
            "--check", "--with-agents", codex_home=codex_home
        )
        self.assertIn("agent profiles and registrations are current", checked.stdout)

        removed = self.run_installer("--uninstall-agents", codex_home=codex_home)
        self.assertIn("Removed or updated", removed.stdout)
        self.assertEqual('name = "mine"\n', unrelated.read_text(encoding="utf-8"))
        text = config.read_text(encoding="utf-8")
        self.assertNotIn("goal-ledger-implementer", text)
        self.assertNotIn("goal-ledger-reviewer", text)
        self.assertIn('[agents]\nmax_threads = 8', text)
        self.assertIn("[features.multi_agent_v2]", text)

    def test_multi_agent_v2_drift_requires_replace_and_preflight_sees_it(self) -> None:
        codex_home = self.root / "codex-home-multi-agent"
        codex_home.mkdir(parents=True)
        config = codex_home / "config.toml"
        config.write_text(
            "[features.multi_agent_v2]\n"
            "hide_spawn_agent_metadata = true\n"
            "max_concurrent_threads_per_session = 2\n"
            'tool_namespace = "legacy"\n',
            encoding="utf-8",
        )
        refused = self.run_installer("--with-agents", codex_home=codex_home, expected=1)
        self.assertIn("multi_agent_v2", refused.stderr)
        replaced = self.run_installer(
            "--with-agents", "--replace", codex_home=codex_home
        )
        self.assertIn("Restart Codex", replaced.stdout)
        text = config.read_text(encoding="utf-8")
        self.assertIn("hide_spawn_agent_metadata = false", text)
        self.assertIn("max_concurrent_threads_per_session = 8", text)
        self.assertIn('tool_namespace = "agents"', text)
        self.run_installer("--check", "--with-agents", codex_home=codex_home)

    def test_owned_agent_drift_requires_explicit_replace_or_forced_uninstall(self) -> None:
        codex_home = self.root / "codex-home-agent-drift"
        self.run_installer("--with-agents", codex_home=codex_home)
        profile = codex_home / "agents" / "goal-ledger-implementer.toml"
        profile.write_text("customized\n", encoding="utf-8")

        refused = self.run_installer(
            "--with-agents", codex_home=codex_home, expected=1
        )
        self.assertIn("differs from the shipped profile", refused.stderr)
        refused_uninstall = self.run_installer(
            "--uninstall-agents", codex_home=codex_home, expected=1
        )
        self.assertIn("refusing to remove customized agent profile", refused_uninstall.stderr)

        forced = self.run_installer(
            "--uninstall-agents",
            "--force-agent-uninstall",
            codex_home=codex_home,
        )
        self.assertIn("Removed or updated", forced.stdout)
        self.assertFalse(profile.exists())

    def test_unbalanced_managed_config_markers_are_never_rewritten(self) -> None:
        codex_home = self.root / "codex-home-markers"
        codex_home.mkdir(parents=True)
        config = codex_home / "config.toml"
        original = 'model = "gpt-5.6-sol"\n# BEGIN codex-goal-ledger managed agents\n'
        config.write_text(original, encoding="utf-8")
        refused = self.run_installer(
            "--with-agents", codex_home=codex_home, expected=1
        )
        self.assertIn("unbalanced Goal Ledger managed markers", refused.stderr)
        self.assertEqual(original, config.read_text(encoding="utf-8"))
        self.assertFalse((codex_home / "skills" / "codex-goal-ledger").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
