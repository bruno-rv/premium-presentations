#!/usr/bin/env python3
"""Tests for bundle_deck.py — conditional-module inclusion and wants_* matchers."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLER_PATH = ROOT / "scripts" / "bundle_deck.py"
SHARED = ROOT / "assets" / "shared"


def load_bundler():
    spec = importlib.util.spec_from_file_location("bundle_deck", BUNDLER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {BUNDLER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Minimal deck fixtures
# ---------------------------------------------------------------------------

_SHARED_LINK = '../../shared/'

def _make_minimal_deck(*, extra_body: str = '', extra_head: str = '') -> str:
    """A minimal two-slide deck that links to shared/ assets (not yet bundled)."""
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-themes.css">'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-extras.css">'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-components.css">'
        f'{extra_head}'
        '</head><body>'
        '<div id="deck">'
        '<section class="slide slide--title"><h1>Title</h1>'
        '<aside class="notes">Notes.</aside></section>'
        '<section class="slide slide--quote"><blockquote>Quote</blockquote>'
        '<aside class="notes">Notes.</aside></section>'
        '</div>'
        f'<script src="{_SHARED_LINK}slide-engine.js"></script>'
        f'<script src="{_SHARED_LINK}premium-controls.js"></script>'
        f'{extra_body}'
        '</body></html>'
    )


def _deck_with_term_links() -> str:
    return _make_minimal_deck(
        extra_body=(
            '<script type="application/json" id="glossary">'
            '{"RAG":{"title":"RAG","body":"Retrieval-Augmented Generation"}}'
            '</script>'
            '<section class="slide">'
            '<button class="term-link" data-term="RAG">RAG</button>'
            '<aside class="notes">Notes.</aside></section>'
        )
    )


def _deck_without_term_links() -> str:
    # No data-term attributes, no id="glossary" — plain deck.
    return _make_minimal_deck()


def _deck_with_live_flow() -> str:
    return _make_minimal_deck(
        extra_body=(
            '<section class="slide">'
            '<div class="live-flow">flow content</div>'
            '<aside class="notes">Notes.</aside></section>'
        )
    )


def _deck_without_live_flow() -> str:
    return _make_minimal_deck()


# ---------------------------------------------------------------------------
# Helper: bundle a deck string via bundle_deck.bundle_html()
# ---------------------------------------------------------------------------

def bundle_string(bundler, html: str, html_path: Path) -> str:
    return bundler.bundle_html(html, html_path)


class BundleGlossaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (SHARED / "premium-glossary.js").is_file():
            raise unittest.SkipTest("premium-glossary.js not found — skipping")
        cls.bundler = load_bundler()

    def _bundle(self, html: str) -> str:
        # Use a real deck slot under the project root so ../../shared/ resolves
        # to the actual assets/shared/ directory.
        deck_dir = ROOT / "assets" / "decks" / "_test_bundle_tmp"
        deck_dir.mkdir(parents=True, exist_ok=True)
        path = deck_dir / "deck.html"
        try:
            path.write_text(html, encoding="utf-8")
            return bundle_string(self.bundler, html, path)
        finally:
            path.unlink(missing_ok=True)
            try:
                deck_dir.rmdir()
            except OSError:
                pass

    def test_deck_with_term_links_includes_glossary(self) -> None:
        bundled = self._bundle(_deck_with_term_links())
        # The inlined script block marker written by build_classic_scripts().
        self.assertIn("/* --- premium-glossary.js --- */", bundled,
                      "Deck WITH term-links should have premium-glossary.js inlined")

    def test_deck_without_term_links_excludes_glossary(self) -> None:
        bundled = self._bundle(_deck_without_term_links())
        # If the JS was wrongly bundled its inlined marker will be present.
        self.assertNotIn("/* --- premium-glossary.js --- */", bundled,
                         "Deck WITHOUT term-links must NOT have premium-glossary.js inlined "
                         "(CSS selector text must not trigger false positive)")


class BundleFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (SHARED / "premium-flow.js").is_file():
            raise unittest.SkipTest("premium-flow.js not found — skipping")
        cls.bundler = load_bundler()

    def _bundle(self, html: str) -> str:
        deck_dir = ROOT / "assets" / "decks" / "_test_bundle_tmp"
        deck_dir.mkdir(parents=True, exist_ok=True)
        path = deck_dir / "deck.html"
        try:
            path.write_text(html, encoding="utf-8")
            return bundle_string(self.bundler, html, path)
        finally:
            path.unlink(missing_ok=True)
            try:
                deck_dir.rmdir()
            except OSError:
                pass

    def test_deck_with_live_flow_includes_flow(self) -> None:
        bundled = self._bundle(_deck_with_live_flow())
        self.assertIn("/* --- premium-flow.js --- */", bundled,
                      "Deck WITH live-flow class should have premium-flow.js inlined")

    def test_deck_without_live_flow_excludes_flow(self) -> None:
        bundled = self._bundle(_deck_without_live_flow())
        # CSS comments may mention "premium-flow.js" — check for the JS inlined marker.
        self.assertNotIn("/* --- premium-flow.js --- */", bundled,
                         "Deck WITHOUT live-flow must NOT have premium-flow.js inlined "
                         "(CSS comment text must not trigger false positive)")


class WantsMatcher_Tests(unittest.TestCase):
    """Unit tests for the wants_* predicate functions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.bundler = load_bundler()

    def test_wants_glossary_on_data_term_attr(self) -> None:
        html = '<button class="term-link" data-term="RAG">RAG</button>'
        self.assertTrue(self.bundler.wants_premium_glossary(html))

    def test_wants_glossary_on_id_glossary(self) -> None:
        html = '<script type="application/json" id="glossary">{}</script>'
        self.assertTrue(self.bundler.wants_premium_glossary(html))

    def test_wants_glossary_false_on_css_class_selector(self) -> None:
        # CSS text that mentions ".term-link" must NOT trigger the matcher.
        html = '<style>.term-link { color: red; } .pp-notes-terms { } </style>'
        self.assertFalse(self.bundler.wants_premium_glossary(html))

    def test_wants_flow_on_class_attr(self) -> None:
        html = '<div class="live-flow step">content</div>'
        self.assertTrue(self.bundler.wants_premium_flow(html))

    def test_wants_flow_false_on_css_text(self) -> None:
        html = '<style>.live-flow { display: flex; }</style>'
        self.assertFalse(self.bundler.wants_premium_flow(html))

    def test_wants_journey_on_class_attr(self) -> None:
        html = '<div class="journey-stage active">Stage 1</div>'
        self.assertTrue(self.bundler.wants_premium_journey(html))

    def test_wants_journey_false_on_css_text(self) -> None:
        html = '<style>.journey-stage { font-weight: bold; }</style>'
        self.assertFalse(self.bundler.wants_premium_journey(html))


if __name__ == "__main__":
    unittest.main()
