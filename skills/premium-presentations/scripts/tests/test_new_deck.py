#!/usr/bin/env python3
"""Workspace-output regression tests for new-deck.sh."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parent.parent.parent
SCRIPT = SKILL / "scripts" / "new-deck.sh"


class NewDeckWorkspaceTests(unittest.TestCase):
    def test_output_dir_keeps_generated_files_out_of_plugin_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_skill = root / "cache" / "skills" / "premium-presentations"
            shutil.copytree(SKILL, cache_skill)
            # Local test runs may leave an ignored, empty source-clone output
            # directory behind; an installed cache starts without generated decks.
            shutil.rmtree(cache_skill / "assets" / "decks", ignore_errors=True)
            workspace_deck = root / "workspace" / "deck"
            unrelated_cwd = root / "unrelated"
            unrelated_cwd.mkdir(parents=True)

            result = subprocess.run(
                [
                    str(cache_skill / "scripts" / "new-deck.sh"),
                    "--output-dir",
                    str(workspace_deck),
                    "warm",
                    "workspace-talk",
                    "Workspace Talk",
                    "8",
                ],
                cwd=unrelated_cwd,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((workspace_deck / "workspace-talk-slides.html").is_file())
            self.assertTrue((workspace_deck / "workspace-talk-slide-spec.md").is_file())
            self.assertFalse((cache_skill / "assets" / "decks").exists())


if __name__ == "__main__":
    unittest.main()
