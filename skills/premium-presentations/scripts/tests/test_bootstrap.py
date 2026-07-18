#!/usr/bin/env python3
"""Unit tests for the prerequisite bootstrap helper."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent.parent
BOOTSTRAP_PATH = ROOT / "scripts" / "bootstrap.py"


def load_bootstrap():
    if not BOOTSTRAP_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location("premium_bootstrap", BOOTSTRAP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {BOOTSTRAP_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BootstrapTests(unittest.TestCase):
    def test_python_version_check_requires_python_310(self) -> None:
        module = load_bootstrap()
        self.assertTrue(BOOTSTRAP_PATH.is_file(), "bootstrap.py has not been implemented")
        if module is None:
            return
        self.assertFalse(module.python_version_supported((3, 9, 6)))
        self.assertTrue(module.python_version_supported((3, 10, 0)))

    def test_node_version_check_requires_node_18(self) -> None:
        module = load_bootstrap()
        self.assertTrue(BOOTSTRAP_PATH.is_file(), "bootstrap.py has not been implemented")
        if module is None:
            return
        self.assertFalse(module.node_version_supported(module.parse_node_version("v17.9.1")))
        self.assertTrue(module.node_version_supported(module.parse_node_version("v18.0.0")))

    def test_install_commands_use_current_python_and_managed_chromium(self) -> None:
        module = load_bootstrap()
        self.assertTrue(BOOTSTRAP_PATH.is_file(), "bootstrap.py has not been implemented")
        if module is None:
            return
        requirements = Path("/tmp/premium-presentations-requirements.txt")
        with patch.object(module.sys, "executable", "/tmp/python"):
            commands = module.install_commands(requirements)
        self.assertEqual(
            commands,
            [
                ["/tmp/python", "-m", "pip", "install", "-r", str(requirements)],
                ["/tmp/python", "-m", "playwright", "install", "chromium"],
            ],
        )

    def test_check_mode_does_not_run_install_commands(self) -> None:
        module = load_bootstrap()
        self.assertTrue(BOOTSTRAP_PATH.is_file(), "bootstrap.py has not been implemented")
        if module is None:
            return
        with patch.object(module, "run_command") as run_command:
            module.main(["--check"])
        run_command.assert_not_called()

    def test_install_mode_runs_generated_commands_in_order(self) -> None:
        module = load_bootstrap()
        self.assertTrue(BOOTSTRAP_PATH.is_file(), "bootstrap.py has not been implemented")
        if module is None:
            return
        commands = [
            ["/tmp/python", "-m", "pip", "install", "-r", "/tmp/requirements.txt"],
            ["/tmp/python", "-m", "playwright", "install", "chromium"],
        ]
        with (
            patch.object(module, "install_commands", return_value=commands),
            patch.object(module, "python_version_supported", return_value=True),
            patch.object(module, "run_command") as run_command,
        ):
            self.assertEqual(module.main(["--install-browser-deps"]), 0)
        self.assertEqual([call.args[0] for call in run_command.call_args_list], commands)


if __name__ == "__main__":
    unittest.main()
