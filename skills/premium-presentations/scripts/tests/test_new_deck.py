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
    def _run(
        self,
        root: Path,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        cache_skill = root / "cache" / "skills" / "premium-presentations"
        shutil.copytree(SKILL, cache_skill)
        shutil.rmtree(cache_skill / "assets" / "decks", ignore_errors=True)
        return subprocess.run(
            [str(cache_skill / "scripts" / "new-deck.sh"), *args],
            cwd=root,
            capture_output=True,
            text=True,
        )

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

    def test_ampersand_in_title_is_preserved_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "workspace" / "deck"
            result = self._run(
                root,
                "--output-dir",
                str(output_dir),
                "warm",
                "ampersand-talk",
                "A&B",
                "2",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            html = (output_dir / "ampersand-talk-slides.html").read_text(encoding="utf-8")
            self.assertIn("<title>A&B</title>", html)

    def test_pipe_in_title_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "workspace" / "deck"
            result = self._run(
                root,
                "--output-dir",
                str(output_dir),
                "warm",
                "pipe-talk",
                "A|B",
                "2",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            html = (output_dir / "pipe-talk-slides.html").read_text(encoding="utf-8")
            self.assertIn("<title>A|B</title>", html)

    def test_failure_removes_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_skill = root / "cache" / "skills" / "premium-presentations"
            shutil.copytree(SKILL, cache_skill)
            shutil.rmtree(cache_skill / "assets" / "decks", ignore_errors=True)
            (cache_skill / "references" / "slide-spec-template.md").unlink()
            output_dir = root / "workspace" / "deck"

            result = subprocess.run(
                [
                    str(cache_skill / "scripts" / "new-deck.sh"),
                    "--output-dir",
                    str(output_dir),
                    "warm",
                    "failed-talk",
                    "Failure",
                    "8",
                ],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(output_dir.exists())

    def test_legacy_positional_invocation_still_writes_skill_local_deck(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._run(root, "warm", "legacy-talk", "Legacy", "2")
            cache_skill = root / "cache" / "skills" / "premium-presentations"

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(
                (cache_skill / "assets" / "decks" / "legacy-talk" / "legacy-talk-slides.html").is_file()
            )


if __name__ == "__main__":
    unittest.main()
