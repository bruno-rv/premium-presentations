#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
VALIDATOR_PATH = ROOT / "scripts" / "validate_runtime_contract.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("runtime_contract", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator()

    def html_with_runtime(self, body: str, *, include_journey: bool = False) -> str:
        modules = list(self.validator.REQUIRED_CSS) + list(self.validator.REQUIRED_JS)
        if include_journey:
            modules.append("premium-journey.js")
        markers = "\n".join(f"/* --- {name} --- */" for name in modules)
        return f"<!doctype html><html><head><style>{markers}</style></head><body>{body}</body></html>"

    def check_temp_html(self, html: str) -> list[str]:
        with tempfile.TemporaryDirectory(dir=ROOT / "scripts") as tmp:
            path = Path(tmp) / "fixture.html"
            path.write_text(html, encoding="utf-8")
            errors: list[str] = []
            self.validator.check_file(path, errors)
            return errors

    def test_journey_stage_requires_premium_journey_runtime(self) -> None:
        html = self.html_with_runtime('<div class="journey-stage"><svg></svg></div>')

        errors = self.check_temp_html(html)

        self.assertIn("premium-journey.js", "\n".join(errors))

    def test_regular_decks_do_not_require_premium_journey_runtime(self) -> None:
        html = self.html_with_runtime("<section class='slide'></section>")

        errors = self.check_temp_html(html)

        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
