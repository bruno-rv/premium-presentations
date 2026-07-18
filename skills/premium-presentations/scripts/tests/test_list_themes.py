#!/usr/bin/env python3
"""Custom-registry regression tests for list-themes.py."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parent.parent.parent
SCRIPT = SKILL / "scripts" / "list-themes.py"
BUILTIN_CSS = SKILL / "assets" / "shared" / "premium-themes.css"


class ListThemesCustomRegistryTests(unittest.TestCase):
    def test_themes_css_option_lists_custom_workspace_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            themes_css = Path(tmp) / "premium-themes.css"
            shutil.copyfile(BUILTIN_CSS, themes_css)
            with themes_css.open("a", encoding="utf-8") as handle:
                handle.write('\nhtml[data-theme="workspace-custom"] { --bg: #000; }\n')

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--themes-css", str(themes_css)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("workspace-custom", result.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()
