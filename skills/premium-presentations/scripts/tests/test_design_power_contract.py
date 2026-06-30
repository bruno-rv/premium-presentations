#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
COMMON_PATH = ROOT / "scripts" / "_common.py"
STUDIO_PATH = ROOT / "assets" / "studio" / "index.html"
DEMO_PATH = ROOT / "assets" / "templates" / "preview-design-power.html"


def load_common():
    spec = importlib.util.spec_from_file_location("premium_common", COMMON_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {COMMON_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DesignPowerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.common = load_common()

    def test_runtime_contract_includes_design_power_assets(self) -> None:
        self.assertIn("premium-design-power.css", self.common.REQUIRED_CSS)
        self.assertIn("premium-design-power.js", self.common.REQUIRED_JS)
        self.assertIn("premium-design-power.js", self.common.JS_BUNDLE_ORDER)

    def test_studio_exposes_visual_design_lab(self) -> None:
        html = STUDIO_PATH.read_text(encoding="utf-8")

        for marker in (
            'id="theme-composer"',
            'id="component-playground"',
            'id="layout-variants"',
            'id="density-checker"',
            'id="motion-profiles"',
            'id="data-visualization"',
            'id="visual-assets"',
            'premium-design-power.js',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, html)

    def test_demo_deck_exercises_all_visual_design_power_features(self) -> None:
        self.assertTrue(DEMO_PATH.is_file(), "expected 3-slide design-power demo deck")
        html = DEMO_PATH.read_text(encoding="utf-8")

        self.assertEqual(html.count('<section class="slide'), 3)
        for marker in (
            'data-motion-profile="cinematic"',
            'data-theme-composer-preset',
            'dp-layout--decision-matrix',
            'dp-component--checklist',
            'dp-viz--line',
            'dp-viz--funnel',
            'dp-viz--heatmap',
            'dp-viz--sankey',
            'data-visual-asset=',
            'premium-design-power.css',
            'premium-design-power.js',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, html)


if __name__ == "__main__":
    unittest.main()
