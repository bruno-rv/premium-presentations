#!/usr/bin/env python3
from __future__ import annotations

import json
import re
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

    def test_repository_exposes_schema_safe_claude_and_codex_metadata(self) -> None:
        claude_marketplace = REPO_ROOT / ".claude-plugin" / "marketplace.json"
        claude_manifest = REPO_ROOT / ".claude-plugin" / "plugin.json"
        codex_manifest = REPO_ROOT / ".codex-plugin" / "plugin.json"
        codex_marketplace = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"

        self.assertTrue(claude_marketplace.exists(), "missing Claude marketplace manifest")
        self.assertTrue(claude_manifest.exists(), "missing Claude plugin manifest")
        self.assertTrue(codex_manifest.exists(), "missing Codex plugin manifest")
        self.assertTrue(codex_marketplace.exists(), "missing Codex marketplace manifest")

        claude = json.loads(claude_manifest.read_text(encoding="utf-8"))
        claude_market = json.loads(claude_marketplace.read_text(encoding="utf-8"))
        codex = json.loads(codex_manifest.read_text(encoding="utf-8"))
        codex_market = json.loads(codex_marketplace.read_text(encoding="utf-8"))

        expected_name = "premium-presentations"
        self.assertEqual(expected_name, claude["name"])
        self.assertEqual(expected_name, claude_market["name"])
        self.assertEqual(expected_name, claude_market["plugins"][0]["name"])
        self.assertEqual(expected_name, codex["name"])
        self.assertEqual(expected_name, codex_market["name"])
        self.assertEqual(expected_name, codex_market["plugins"][0]["name"])

        self.assertNotIn("id", claude_market, "Claude marketplace rejects the legacy id field")
        self.assertEqual(["./skills/premium-presentations"], claude["skills"])
        self.assertEqual(["./commands/"], claude["commands"])
        for raw_path in claude["skills"] + claude["commands"]:
            self.assertTrue((REPO_ROOT / raw_path).exists(), f"unresolved Claude path: {raw_path}")
        self.assertTrue(
            any((REPO_ROOT / "commands").glob("*.md")),
            "Claude commands directory must contain at least one command",
        )

        self.assertEqual("./skills/", codex["skills"])
        self.assertNotIn("commands", codex)
        codex_skills = REPO_ROOT / codex["skills"]
        self.assertTrue(codex_skills.is_dir(), f"unresolved Codex skills path: {codex['skills']}")
        self.assertTrue(any(codex_skills.glob("*/SKILL.md")), "Codex skills path contains no skills")

        self.assertEqual("./", claude_market["plugins"][0]["source"])
        self.assertEqual(
            {"source": "url", "url": "./"},
            codex_market["plugins"][0]["source"],
        )

    def test_release_versions_match_across_manifests_package_and_lock(self) -> None:
        claude = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        claude_market = json.loads(
            (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        codex = json.loads((REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        package = json.loads((ROOT / "scripts" / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((ROOT / "scripts" / "package-lock.json").read_text(encoding="utf-8"))

        versions = {
            "Claude plugin": claude["version"],
            "Claude marketplace": claude_market["metadata"]["version"],
            "Codex plugin": codex["version"],
            "package": package["version"],
            "package-lock": lock["version"],
            "package-lock root": lock["packages"][""]["version"],
        }
        self.assertEqual({"2.0.0"}, set(versions.values()), versions)

    def test_aggregate_script_covers_every_shipped_node_suite_and_python_discovery(self) -> None:
        package = json.loads((ROOT / "scripts" / "package.json").read_text(encoding="utf-8"))
        scripts = package["scripts"]
        self.assertIn("test:all", scripts)

        reachable: set[str] = set()
        pending = ["test:all"]
        while pending:
            name = pending.pop()
            if name in reachable:
                continue
            self.assertIn(name, scripts, f"aggregate script references missing npm script {name!r}")
            reachable.add(name)
            pending.extend(re.findall(r"\bnpm run ([\w:-]+)", scripts[name]))
        aggregate = "\n".join(scripts[name] for name in sorted(reachable))

        node_suites = sorted((ROOT / "scripts" / "tests").glob("*.mjs"))
        for suite in node_suites:
            if suite.name == "_helpers.mjs":
                continue
            if suite.name.endswith(".test.mjs"):
                self.assertIn("node --test tests/*.test.mjs", aggregate)
            else:
                self.assertIn(f"tests/{suite.name}", aggregate, f"Node suite omitted: {suite.name}")
        self.assertIn("python3 -m unittest discover -s tests", aggregate)

    def test_public_bundle_script_uses_the_canonical_example(self) -> None:
        package = json.loads((ROOT / "scripts" / "package.json").read_text(encoding="utf-8"))
        command = package["scripts"]["test:bundle"]
        canonical = "../assets/examples/rag-vector-graph/rag-vector-graph-slides.html"
        self.assertIn(canonical, command)
        self.assertTrue((ROOT / "scripts" / canonical).is_file(), "canonical bundle fixture is missing")

    def test_ci_runs_the_complete_cross_ecosystem_gate(self) -> None:
        workflow_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(workflow_path.is_file(), "missing CI workflow")
        workflow = workflow_path.read_text(encoding="utf-8")
        required_markers = (
            "actions/setup-node@v4",
            "node-version: 20",
            "actions/setup-python@v5",
            "python-version: '3.12'",
            "npm ci",
            "playwright install",
            "chromium",
            "npm run test:all",
            "validate_runtime_contract.py",
            "validate_contrast.py",
            "claude plugin validate . --strict",
            "validate_plugin.py",
            "npm audit",
            "git diff --check",
        )
        for marker in required_markers:
            self.assertIn(marker, workflow, f"CI missing required gate: {marker}")


if __name__ == "__main__":
    unittest.main()
