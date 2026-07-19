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
            "references/present-architecture-brief.md",
            "references/present-postmortem-brief.md",
            "scripts",
            "scripts/package.json",
            "scripts/recipe_source_guard.py",
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
        self.assertNotIn("id", claude_market)
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
        self.assertEqual({"2.1.0"}, set(versions.values()), versions)

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
        self.assertIn('themes_css="$project_root/assets/shared/premium-themes.css"', command)
        self.assertIn('themes_css="$skill_root/assets/shared/premium-themes.css"', command)
        self.assertIn('--themes-css "$themes_css"', command)

    def test_new_recipe_commands_are_registered_and_use_the_source_guard(self) -> None:
        for rel in (
            "commands/present-architecture.md",
            "commands/present-postmortem.md",
        ):
            path = REPO_ROOT / rel
            self.assertTrue(path.exists(), f"missing {rel}")
            command = path.read_text(encoding="utf-8")
            self.assertIn("${CLAUDE_PLUGIN_ROOT}", command)
            self.assertIn("${CLAUDE_PROJECT_DIR}", command)
            self.assertIn("recipe_source_guard.py", command)
            self.assertIn("$skill_root/scripts/new-deck.sh", command)
            self.assertIn("$skill_root/scripts/deck_doctor.py", command)

        postmortem = (REPO_ROOT / "commands" / "present-postmortem.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("--git-range", postmortem)
        self.assertIn("--ci-log", postmortem)
        self.assertIn("--keep-identifiers", postmortem)

        codex_manifest = json.loads(
            (REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertNotIn(
            "commands",
            codex_manifest,
            "Codex manifest must not gain a commands key for the new recipes",
        )

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
                self.assertIn('--themes-css "$workspace_theme_css"', document)
                self.assertIn(
                    'cp "$skill_root/assets/shared/premium-themes.css" "$workspace_theme_css"',
                    document,
                )
                self.assertIn('themes_css="$workspace_root/assets/shared/premium-themes.css"', document)
                self.assertIn('themes_css="$skill_root/assets/shared/premium-themes.css"', document)
                self.assertIn('--themes-css "$themes_css"', document)

        skill = documents["SKILL.md"]
        self.assertIn("workspace_root", skill)
        self.assertIn("skill_root", skill)
        self.assertIn("absolute skill root", skill.lower())
        self.assertNotIn("cd skills/premium-presentations", skill)

    def test_runtime_recipe_executes_new_deck_shell_directly(self) -> None:
        runtime = (ROOT / "references" / "runtime.md").read_text(encoding="utf-8")

        self.assertNotIn('python3 "$skill_root/scripts/new-deck.sh"', runtime)
        self.assertRegex(
            runtime,
            r'(?m)^"\$skill_root/scripts/new-deck\.sh"\s+--output-dir',
        )

    def test_installed_plugin_bootstrap_does_not_run_npm_ci_in_readonly_cache(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        skill_bootstrap = skill.split("## Source checkout validation", 1)[0]
        readme_bootstrap = readme.split("### Requirements and bootstrap", 1)[1].split(
            "### Source checkout validation", 1
        )[0]

        self.assertNotIn("npm --prefix", skill_bootstrap)
        self.assertNotIn("npm --prefix", readme_bootstrap)
        self.assertIn("source checkout", skill.lower())
        self.assertIn("npm --prefix \"$skill_root/scripts\" ci", skill)
        self.assertIn("source checkout", readme.lower())

    def test_marketplace_guidance_never_derives_skill_root_from_repo_relative_cd(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("marketplace users", skill.lower())
        self.assertIn("absolute skill root", skill.lower())
        self.assertIn("new session", readme.lower())
        self.assertNotIn('skill_root="$(cd skills/premium-presentations', readme)
        self.assertIn('skill_root="$workspace_root/skills/premium-presentations"', readme)

    def test_ci_workflow_covers_the_release_gate_without_provider_installs(self) -> None:
        workflow_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(workflow_path.is_file(), "missing CI release-gate workflow")
        workflow = workflow_path.read_text(encoding="utf-8")

        required_markers = (
            "node-version: 20",
            "python-version: '3.12'",
            "timeout-minutes: 20",
            "npm ci --prefix skills/premium-presentations/scripts",
            "npm audit",
            "python3 -m pip install -r skills/premium-presentations/scripts/requirements.txt",
            "python3 -m playwright install --with-deps chromium",
            "python3 skills/premium-presentations/scripts/bootstrap.py --check",
            "python3 skills/premium-presentations/scripts/validate_runtime_contract.py",
            "python3 skills/premium-presentations/scripts/validate_contrast.py",
            "python3 -m unittest discover",
            "working-directory: skills/premium-presentations/scripts",
            "npm test --prefix skills/premium-presentations/scripts",
            "git diff --check",
        )
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, workflow)

        self.assertNotIn("npm install --global @anthropic-ai", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s*claude\s+plugin\s+(?:add|install)")
        self.assertNotRegex(workflow, r"(?m)^\s*codex\s+plugin\s+(?:add|install)")

    def test_readme_documents_the_ci_release_gate(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## CI release gate", readme)
        section = readme.split("## CI release gate", 1)[1]
        self.assertIn("Node.js 20", section)
        self.assertIn("Python 3.12", section)
        self.assertIn("npm ci", section)
        self.assertIn("npm audit", section)
        self.assertIn("bootstrap.py --check", section)
        self.assertIn("Claude-compatible", section)
        self.assertIn("CLI installs", section)
        self.assertIn("python3 -m venv", section)
        self.assertIn("PATH=", section)
        self.assertIn("--with-deps", section)
        self.assertIn("Linux", section)
        self.assertIn("macOS", section)
        self.assertIn("activate", section)


if __name__ == "__main__":
    unittest.main()
