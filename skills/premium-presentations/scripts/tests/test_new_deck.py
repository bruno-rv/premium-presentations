#!/usr/bin/env python3
"""Regression tests for escaped, transactional, workspace-portable deck scaffolding."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent.parent
ROOT = SKILL
SCRIPT = SKILL / "scripts" / "new-deck.sh"
DECKS = SKILL / "assets" / "decks"
sys.path.insert(0, str(SKILL / "scripts"))

from render_template import render_template_text  # noqa: E402


class RenderTemplateTests(unittest.TestCase):
    def test_inserted_placeholder_like_text_is_not_reprocessed(self) -> None:
        rendered = render_template_text(
            "<title>{{TITLE}}</title><link href='{{SHARED}}'>{{BAR_RIGHT}}",
            {
                "TITLE": "R&D {{SHARED}} {{BAR_RIGHT}} <Q3>",
                "SHARED": "../../shared/",
                "BAR_RIGHT": "",
            },
        )
        self.assertIn("R&amp;D {{SHARED}} {{BAR_RIGHT}} &lt;Q3&gt;", rendered)
        self.assertIn("href='../../shared/'", rendered)

    def test_original_unresolved_placeholder_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "MISSING"):
            render_template_text("{{TITLE}} {{MISSING}}", {"TITLE": "Deck"})


class NewDeckTests(unittest.TestCase):
    """Default (skill-local assets/decks/) invocation, run directly against ROOT."""

    def setUp(self) -> None:
        DECKS.mkdir(parents=True, exist_ok=True)
        self.slug = "test-" + uuid.uuid4().hex[:12]
        self.deck_dir = DECKS / self.slug
        self.addCleanup(shutil.rmtree, self.deck_dir, True)

    def _run(self, title: str, count: int = 2, *, env: dict[str, str] | None = None):
        return subprocess.run(
            ["bash", str(SCRIPT), "warm", self.slug, title, str(count)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_special_character_title_is_literal_and_html_escaped(self) -> None:
        title = 'R&D | <Q3> "Launch" {{SHARED}}'
        result = self._run(title, count=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        html = (self.deck_dir / f"{self.slug}-slides.html").read_text(encoding="utf-8")
        self.assertIn(
            "R&amp;D | &lt;Q3&gt; &quot;Launch&quot; {{SHARED}}",
            html,
        )
        self.assertNotIn("{{TITLE}}", html)
        self.assertNotIn("<Q3>", html)
        self.assertEqual(html.count("/* --- theme-visuals-embed --- */"), 1)
        manifest_path = ROOT / "assets" / "shared" / "assets" / "theme-visuals" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_assets = sum(len(theme["assets"]) for theme in manifest.values())
        self.assertEqual(html.count("data:image/webp;base64,"), expected_assets)
        for theme in manifest:
            self.assertIn(f'"{theme}"', html)
        spec = (self.deck_dir / f"{self.slug}-slide-spec.md").read_text(encoding="utf-8")
        self.assertIn(
            '| **Title** | R&amp;D \\| &lt;Q3&gt; &quot;Launch&quot; {{SHARED}} |',
            spec,
        )

    def test_failure_after_staging_removes_all_partial_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir)
            wrapper = bin_dir / "python3"
            wrapper.write_text(
                "#!/bin/sh\n"
                "case \"$*\" in *bundle_deck.py*) exit 42 ;; esac\n"
                f'exec "{sys.executable}" "$@"\n',
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
            result = self._run("Rollback test", env=env)

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.deck_dir.exists())
        self.assertEqual(list(DECKS.glob(f".{self.slug}.staging.*")), [])


class NewDeckWorkspaceTests(unittest.TestCase):
    """--output-dir invocation against a cached (installed-plugin-like) skill copy."""

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

    def test_ampersand_in_title_is_html_escaped(self) -> None:
        # render_template.py HTML-escapes all substituted values (a deliberate
        # HTML-injection hardening fix) — "&" becomes "&amp;" in the emitted
        # <title>, unlike the pre-hardening literal-passthrough behavior.
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
            self.assertIn("<title>A&amp;B</title>", html)

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
