#!/usr/bin/env python3
from __future__ import annotations

import unittest
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
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
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
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
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("assets/decks/", gitignore)


if __name__ == "__main__":
    unittest.main()
