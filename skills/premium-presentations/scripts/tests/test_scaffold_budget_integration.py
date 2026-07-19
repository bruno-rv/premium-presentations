#!/usr/bin/env python3
"""Scaffold integration test (PLAN.md Workstream A step 16): generate a real
deck via new-deck.sh and assert the scaffolded Slide Map header/separator +
empty Budget cells parse as budgetless and pass the deck_doctor budgetless
path — the concrete artifact an agent starts from, not a synthetic fixture."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent.parent
SCRIPT = SKILL / "scripts" / "new-deck.sh"
DECK_DOCTOR = SKILL / "scripts" / "deck_doctor.py"
DECKS = SKILL / "assets" / "decks"

sys.path.insert(0, str(SKILL / "scripts"))
from slide_spec import BudgetColumns, parse_budget_columns, parse_slide_map  # noqa: E402


class ScaffoldBudgetIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        DECKS.mkdir(parents=True, exist_ok=True)
        self.slug = "budget-scaffold-" + uuid.uuid4().hex[:12]
        self.deck_dir = DECKS / self.slug
        self.addCleanup(shutil.rmtree, self.deck_dir, True)

    def test_scaffolded_spec_budget_columns_parse_budgetless(self) -> None:
        # 8+ slides triggers spec_generator.py, which scaffolds the Budget
        # (mm:ss)/Budget (ms) header pair with empty cells (see
        # references/slide-spec-template.md and spec_generator.py).
        result = subprocess.run(
            ["bash", str(SCRIPT), "warm", self.slug, "Budget Scaffold", "8"],
            cwd=SKILL,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        spec_path = self.deck_dir / f"{self.slug}-slide-spec.md"
        self.assertTrue(spec_path.is_file(), result.stdout)
        spec_text = spec_path.read_text(encoding="utf-8")
        self.assertIn("Budget (mm:ss)", spec_text)
        self.assertIn("Budget (ms)", spec_text)

        parsed = parse_slide_map(spec_text, require_ids=True)
        self.assertEqual(len(parsed.rows), 8)
        self.assertEqual(parse_budget_columns(parsed), BudgetColumns(state="budgetless", budgets=()))

    def test_scaffolded_html_passes_deck_doctor_budgetless_path(self) -> None:
        result = subprocess.run(
            ["bash", str(SCRIPT), "warm", self.slug, "Budget Scaffold", "8"],
            cwd=SKILL,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        html_path = self.deck_dir / f"{self.slug}-slides.html"
        self.assertTrue(html_path.is_file(), result.stdout)
        html_text = html_path.read_text(encoding="utf-8")
        # No Python script emits data-budget (agent HTML-emit contract) — the
        # bundled runtime JS legitimately mentions the attribute *name* (e.g.
        # inside readSlideBudgets()), so scope the check to actual usage on a
        # <section ...> start tag rather than the substring anywhere in the
        # bundle.
        self.assertIsNone(
            re.search(r"<section[^>]*\bdata-budget\s*=", html_text),
            "scaffolded slide sections must carry no data-budget attribute (agent's job)",
        )

        # Deck Doctor without a spec arg — the scaffolded base HTML's slide
        # count won't yet match the generated 8-row spec (slide authoring is
        # the agent's next step), so this exercises exactly the unconditional
        # HTML-only budgetless path (PLAN.md Workstream A step 3).
        doctor = subprocess.run(
            [sys.executable, str(DECK_DOCTOR), str(html_path)],
            cwd=SKILL,
            capture_output=True,
            text=True,
        )
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        self.assertIn("DECK HEALTHY", doctor.stdout)


if __name__ == "__main__":
    unittest.main()
