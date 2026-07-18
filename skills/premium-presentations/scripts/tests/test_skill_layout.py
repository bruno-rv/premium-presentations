#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = ROOT.parent.parent
ALLOWED_TOP_LEVEL = {
    ".gitignore",
    "LICENSE",
    "README.md",
    "SKILL.md",
    "assets",
    "references",
    "scripts",
}


def tracked_files() -> set[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return {Path(line) for line in result.stdout.splitlines() if line}


class SkillLayoutTests(unittest.TestCase):
    def test_repository_root_is_an_anthropic_skill_package(self) -> None:
        required = [
            "SKILL.md",
            "assets",
            "assets/shared",
            "assets/studio/index.html",
            "assets/templates",
            "references",
            "references/design.md",
            "scripts",
            "scripts/package.json",
        ]
        for rel in required:
            self.assertTrue((ROOT / rel).exists(), f"missing {rel}")

    def test_no_non_skill_project_clutter(self) -> None:
        forbidden = [
            ".agents/skills/premium-presentations",
            "agents",
            ".claude/skills/premium-presentations",
            ".codex/skills/premium-presentations",
            ".cursor/skills/premium-presentations",
            ".impeccable",
            ".remember",
            "app",
            "assets/decks",
            "decks",
            "docs",
            "PLAN.md",
            "PLAN-REVIEW-LOG.md",
            "PRODUCT.md",
            "reference",
            "REVIEW_PROMPT.txt",
            "shared",
            "templates",
            "tests",
            "package.json",
            "package-lock.json",
        ]
        tracked = tracked_files()
        for rel in forbidden:
            rel_path = Path(rel)
            self.assertFalse(
                any(path == rel_path or rel_path in path.parents for path in tracked),
                f"unexpected tracked {rel}",
            )

    def test_tracked_top_level_contains_only_skill_files(self) -> None:
        tracked = {path.parts[0] for path in tracked_files()}
        unexpected = sorted(tracked - ALLOWED_TOP_LEVEL)
        self.assertEqual([], unexpected)

    def test_skill_docs_use_references_path(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        references = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((ROOT / "references").glob("*.md"))
        )
        self.assertIn("references/runtime.md", skill)
        self.assertIn("references/components.md", skill)
        self.assertIn("assets/shared/premium-themes.css", skill)
        self.assertIn("assets/templates/components", references)
        self.assertIn("assets/decks/", readme)
        self.assertIn("generated output", readme)
        self.assertIn("assets/shared", readme)
        self.assertNotIn("reference/runtime.md", skill)
        self.assertNotIn("reference/", skill)

    def test_generated_decks_are_ignored(self) -> None:
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("assets/decks/", gitignore)

    def test_partial_regeneration_guidance_is_provider_neutral(self) -> None:
        documents = {
            "SKILL.md": (ROOT / "SKILL.md").read_text(encoding="utf-8"),
            "README.md": (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
            "runtime.md": (ROOT / "references" / "runtime.md").read_text(encoding="utf-8"),
        }
        for name, document in documents.items():
            with self.subTest(document=name):
                for command in (
                    "partial_regen.py init",
                    "partial_regen.py plan",
                    "partial_regen.py apply",
                    "partial_regen.py rollback",
                ):
                    self.assertIn(command, document)
                self.assertIn("Claude Code", document)
                self.assertIn("Codex", document)
        self.assertNotIn("row index, confirmed by title", documents["SKILL.md"])
        self.assertNotIn("stable data-slide-id", documents["SKILL.md"])

    def test_repository_exposes_claude_and_codex_plugin_manifests(self) -> None:
        claude_manifest = REPO_ROOT / ".claude-plugin" / "plugin.json"
        codex_manifest = REPO_ROOT / ".codex-plugin" / "plugin.json"
        codex_marketplace = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
        command_recipe = REPO_ROOT / "commands" / "present-pr.md"

        self.assertTrue(claude_manifest.exists(), "missing Claude plugin manifest")
        self.assertTrue(codex_manifest.exists(), "missing Codex plugin manifest")
        self.assertTrue(codex_marketplace.exists(), "missing Codex marketplace manifest")
        self.assertTrue(command_recipe.exists(), "missing present-pr command recipe")

        claude = json.loads(claude_manifest.read_text(encoding="utf-8"))
        self.assertEqual(["./commands/"], claude["commands"])

        claude_marketplace = json.loads(
            (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("id", claude_marketplace)

        codex = json.loads(codex_manifest.read_text(encoding="utf-8"))
        self.assertEqual("premium-presentations", codex["name"])
        self.assertEqual("./skills/", codex["skills"])
        self.assertNotIn("commands", codex)

        marketplace = json.loads(codex_marketplace.read_text(encoding="utf-8"))
        self.assertEqual("premium-presentations", marketplace["name"])
        self.assertEqual("premium-presentations", marketplace["plugins"][0]["name"])
        self.assertEqual({"source": "url", "url": "./"}, marketplace["plugins"][0]["source"])

    def test_present_pr_uses_explicit_claude_roots_and_workspace_output(self) -> None:
        command = (REPO_ROOT / "commands" / "present-pr.md").read_text(encoding="utf-8")

        self.assertIn("${CLAUDE_PLUGIN_ROOT}", command)
        self.assertIn("${CLAUDE_PROJECT_DIR}", command)
        self.assertNotIn("./skills/premium-presentations", command)
        self.assertNotRegex(
            command,
            r"(?m)^\s*(?:python3\s+)?skills/premium-presentations/",
        )
        self.assertIn("--output-dir", command)
        self.assertIn("$skill_root/scripts/new-deck.sh", command)
        self.assertIn("$skill_root/scripts/deck_doctor.py", command)

    def test_shared_recipe_captures_workspace_before_skill_root(self) -> None:
        documents = {
            "SKILL.md": (ROOT / "SKILL.md").read_text(encoding="utf-8"),
            "runtime.md": (ROOT / "references" / "runtime.md").read_text(encoding="utf-8"),
        }
        for name, document in documents.items():
            with self.subTest(document=name):
                self.assertIn("workspace root", document.lower())
                self.assertIn("skill root", document.lower())
                self.assertIn("Codex", document)

        skill = documents["SKILL.md"]
        self.assertIn("workspace_root", skill)
        self.assertIn("skill_root", skill)
        self.assertIn("absolute skill root", skill.lower())
        self.assertNotIn("cd skills/premium-presentations", skill)


if __name__ == "__main__":
    unittest.main()
