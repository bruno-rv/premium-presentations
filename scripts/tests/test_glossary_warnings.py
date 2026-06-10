#!/usr/bin/env python3
"""Tests for validate_deck.py glossary warning detection logic."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent.parent
VALIDATOR_PATH = ROOT / "scripts" / "validate_deck.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_deck", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHARED_CSS_MARKERS = """
prefers-reduced-motion: reduce {}
.premium-controller {}
"""

SHARED_JS_MARKERS = "\n".join(
    f"/* --- {name} --- */"
    for name in [
        "premium-controller.js", "premium-controls.js", "premium-annotations.js",
        "premium-timer.js", "premium-tts.js", "premium-search.js", "premium-clicker.js",
        "premium-og-cover.js", "premium-slide-content.js", "premium-presenter.js",
        "slide-engine.js",
    ]
)


def _make_deck_html_raw_glossary(*, term_links: list[str], raw_glossary: str) -> str:
    """Build a deck HTML fixture with a custom (possibly malformed) glossary block."""
    buttons = " ".join(
        f'<button class="term-link" type="button" data-term="{k}">{k}</button>'
        for k in term_links
    )
    glossary_block = f'<script type="application/json" id="glossary">{raw_glossary}</script>'
    slide1 = (
        f'<section class="slide"><div class="stats-row"><div class="stat-card">'
        f'{buttons}<aside class="notes">Notes.</aside></div></div></section>'
    )
    slide2 = (
        '<section class="slide slide--quote">'
        '<blockquote>"Quote."</blockquote>'
        '<aside class="notes">Notes.</aside>'
        '</section>'
    )
    return (
        f'<!doctype html><html lang="en"><head>'
        f'<style>{SHARED_CSS_MARKERS}</style>'
        f'</head><body>'
        f'<div id="deck">{slide1}{slide2}</div>'
        f'{glossary_block}'
        f'<script>{SHARED_JS_MARKERS}\nnew SlideEngine();</script>'
        f'</body></html>'
    )


def _make_deck_html(*, term_links: list[str], with_json_block: bool, known_keys: list[str] | None = None) -> str:
    """Build a complete, minimal valid deck HTML fixture."""
    keys = known_keys if known_keys is not None else ["RAG", "LLM"]
    glossary_dict = {k: {"title": k, "body": "Definition."} for k in keys}
    json_str = json.dumps(glossary_dict)

    buttons = " ".join(
        f'<button class="term-link" type="button" data-term="{k}">{k}</button>'
        for k in term_links
    )
    glossary_block = (
        f'<script type="application/json" id="glossary">{json_str}</script>'
        if with_json_block
        else ""
    )
    # Two slides so the validator doesn't warn about missing notes only once
    slide1 = (
        f'<section class="slide"><div class="stats-row"><div class="stat-card">'
        f'{buttons}<aside class="notes">Notes.</aside></div></div></section>'
    )
    slide2 = (
        '<section class="slide slide--quote">'
        '<blockquote>"Quote."</blockquote>'
        '<aside class="notes">Notes.</aside>'
        '</section>'
    )
    return (
        f'<!doctype html><html lang="en"><head>'
        f'<style>{SHARED_CSS_MARKERS}</style>'
        f'</head><body>'
        f'<div id="deck">{slide1}{slide2}</div>'
        f'{glossary_block}'
        f'<script>{SHARED_JS_MARKERS}\nnew SlideEngine();</script>'
        f'</body></html>'
    )


def run_validate(html: str) -> tuple[int, str]:
    """Write html to a temp file, run validate(), return (exit_code, captured_output)."""
    validator = load_validator()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fixture.html"
        path.write_text(html, encoding="utf-8")
        buf = StringIO()
        with patch("builtins.print", side_effect=lambda *a, **kw: buf.write(" ".join(str(x) for x in a) + "\n")):
            rc = validator.validate(path)
        return rc, buf.getvalue()


class GlossaryWarningTests(unittest.TestCase):
    def test_no_warning_when_no_term_links(self) -> None:
        html = _make_deck_html(term_links=[], with_json_block=False)
        _, out = run_validate(html)
        glossary_lines = [l for l in out.splitlines() if "glossary" in l.lower() or "term-link" in l.lower()]
        self.assertEqual([], glossary_lines, f"Unexpected glossary output: {glossary_lines}")

    def test_no_warning_when_all_keys_in_dict(self) -> None:
        html = _make_deck_html(term_links=["RAG", "LLM"], with_json_block=True)
        _, out = run_validate(html)
        glossary_lines = [l for l in out.splitlines() if ("glossary" in l.lower() or "term-link" in l.lower()) and "WARN" in l]
        self.assertEqual([], glossary_lines, f"Unexpected glossary warning: {glossary_lines}")

    def test_warning_when_term_links_but_no_json_block(self) -> None:
        html = _make_deck_html(term_links=["RAG"], with_json_block=False)
        _, out = run_validate(html)
        warn_lines = [l for l in out.splitlines() if "WARN" in l and ("glossary" in l.lower() or "term-link" in l.lower())]
        self.assertGreater(len(warn_lines), 0, f"Expected glossary WARN, got output:\n{out}")

    def test_warning_is_not_error(self) -> None:
        html = _make_deck_html(term_links=["RAG"], with_json_block=False)
        rc, out = run_validate(html)
        fail_lines = [l for l in out.splitlines() if "FAIL" in l and ("glossary" in l.lower() or "term-link" in l.lower())]
        self.assertEqual([], fail_lines, "Glossary issue should be WARN, not FAIL")

    def test_warning_for_missing_key_in_dict(self) -> None:
        html = _make_deck_html(term_links=["RAG", "UNKNOWN_KEY"], with_json_block=True)
        _, out = run_validate(html)
        warn_lines = [l for l in out.splitlines() if "WARN" in l and "UNKNOWN_KEY" in l]
        self.assertGreater(len(warn_lines), 0, f"Expected warning about UNKNOWN_KEY:\n{out}")

    def test_no_warning_for_key_that_exists(self) -> None:
        html = _make_deck_html(term_links=["RAG"], with_json_block=True)
        _, out = run_validate(html)
        rag_warn = [l for l in out.splitlines() if "WARN" in l and "RAG" in l and "missing" in l.lower()]
        self.assertEqual([], rag_warn, f"RAG should not produce a warning: {rag_warn}")

    def test_multiple_missing_keys_in_single_warning(self) -> None:
        html = _make_deck_html(term_links=["RAG", "GHOST1", "GHOST2"], with_json_block=True)
        _, out = run_validate(html)
        warn_lines = [l for l in out.splitlines() if "WARN" in l and ("GHOST1" in l or "GHOST2" in l)]
        self.assertGreater(len(warn_lines), 0, f"Expected warning about GHOST keys:\n{out}")


class GlossaryMalformedJsonTests(unittest.TestCase):
    """Finding 4 — malformed or structurally invalid JSON in id="glossary"."""

    def test_malformed_json_produces_warning(self) -> None:
        html = _make_deck_html_raw_glossary(
            term_links=["RAG"],
            raw_glossary='{bad json here',
        )
        _, out = run_validate(html)
        warn_lines = [l for l in out.splitlines() if "WARN" in l and "glossary" in l.lower()]
        self.assertGreater(len(warn_lines), 0, f"Expected WARN for malformed JSON:\n{out}")

    def test_malformed_json_is_not_error(self) -> None:
        html = _make_deck_html_raw_glossary(
            term_links=["RAG"],
            raw_glossary='{bad json here',
        )
        rc, out = run_validate(html)
        fail_lines = [l for l in out.splitlines() if "FAIL" in l and "glossary" in l.lower()]
        self.assertEqual([], fail_lines, "Malformed JSON should produce WARN, not FAIL")

    def test_non_object_json_produces_warning(self) -> None:
        # Valid JSON but not a dict — should warn about non-object dictionary.
        html = _make_deck_html_raw_glossary(
            term_links=["RAG"],
            raw_glossary='["RAG", "LLM"]',
        )
        _, out = run_validate(html)
        warn_lines = [l for l in out.splitlines() if "WARN" in l and "glossary" in l.lower()]
        self.assertGreater(len(warn_lines), 0, f"Expected WARN for non-object JSON:\n{out}")

    def test_entry_missing_title_produces_warning(self) -> None:
        html = _make_deck_html_raw_glossary(
            term_links=["RAG"],
            raw_glossary=json.dumps({"RAG": {"body": "Some body text."}}),
        )
        _, out = run_validate(html)
        warn_lines = [l for l in out.splitlines() if "WARN" in l and "title" in l.lower()]
        self.assertGreater(len(warn_lines), 0, f"Expected WARN about missing title:\n{out}")

    def test_entry_missing_body_produces_warning(self) -> None:
        html = _make_deck_html_raw_glossary(
            term_links=["RAG"],
            raw_glossary=json.dumps({"RAG": {"title": "RAG Title"}}),
        )
        _, out = run_validate(html)
        warn_lines = [l for l in out.splitlines() if "WARN" in l and "body" in l.lower()]
        self.assertGreater(len(warn_lines), 0, f"Expected WARN about missing body:\n{out}")

    def test_malformed_json_warns_even_without_term_links(self) -> None:
        # Dictionary validation must not be gated on term-links existing —
        # a malformed dict in a deck with zero links should still warn.
        html = _make_deck_html_raw_glossary(
            term_links=[],
            raw_glossary='{bad json here',
        )
        _, out = run_validate(html)
        warn_lines = [l for l in out.splitlines() if "WARN" in l and "glossary" in l.lower()]
        self.assertGreater(len(warn_lines), 0, f"Expected WARN for malformed dict without links:\n{out}")

    def test_valid_dict_without_term_links_no_warning(self) -> None:
        html = _make_deck_html_raw_glossary(
            term_links=[],
            raw_glossary=json.dumps({"RAG": {"title": "RAG", "body": "Retrieval-Augmented Gen."}}),
        )
        _, out = run_validate(html)
        warn_lines = [l for l in out.splitlines() if "WARN" in l and "glossary" in l.lower()]
        self.assertEqual([], warn_lines, f"Valid dict without links should not warn:\n{out}")

    def test_complete_valid_entry_no_warning(self) -> None:
        html = _make_deck_html_raw_glossary(
            term_links=["RAG"],
            raw_glossary=json.dumps({"RAG": {"title": "RAG", "body": "Retrieval-Augmented Gen."}}),
        )
        _, out = run_validate(html)
        warn_lines = [
            l for l in out.splitlines()
            if "WARN" in l and ("glossary" in l.lower() or "RAG" in l)
        ]
        self.assertEqual([], warn_lines, f"Complete valid entry should produce no warning:\n{out}")


if __name__ == "__main__":
    unittest.main()
