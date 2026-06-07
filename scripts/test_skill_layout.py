#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class SkillLayoutTests(unittest.TestCase):
    def test_repository_root_is_the_single_skill_package(self) -> None:
        required = [
            "SKILL.md",
            "agents/openai.yaml",
            "assets/studio/index.html",
            "decks",
            "references",
            "references/design.md",
            "scripts",
            "scripts/package.json",
            "shared",
            "templates",
        ]
        for rel in required:
            self.assertTrue((ROOT / rel).exists(), f"missing {rel}")

    def test_no_committed_platform_mirror_skill_packages(self) -> None:
        forbidden = [
            ".agents/skills/premium-presentations",
            ".claude/skills/premium-presentations",
            ".codex/skills/premium-presentations",
            ".cursor/skills/premium-presentations",
            "app",
            "reference",
            "tests",
            "package.json",
            "package-lock.json",
        ]
        for rel in forbidden:
            self.assertFalse((ROOT / rel).exists(), f"unexpected {rel}")

    def test_skill_docs_use_references_path(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("references/runtime.md", skill)
        self.assertIn("references/components.md", skill)
        self.assertIn("references/", readme)
        self.assertNotIn("reference/runtime.md", skill)
        self.assertNotIn("reference/", readme)


if __name__ == "__main__":
    unittest.main()
