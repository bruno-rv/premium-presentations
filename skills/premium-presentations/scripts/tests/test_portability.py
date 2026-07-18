#!/usr/bin/env python3
"""Focused tests for bundled-deck offline portability validation."""
from __future__ import annotations

import sys
import unittest
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import validate_portability  # noqa: E402


class PortabilityValidatorTests(unittest.TestCase):
    def test_allows_embedded_data_and_fragment_references(self) -> None:
        html = """<!doctype html><html><head><style>
        .hero { background-image: url('data:image/webp;base64,UklGRg=='); }
        .mark { clip-path: url(#clip); }
        /* .old { background: url(ignored-remote.png); } @import "ignored.css"; */
        </style></head><body>
        <img src="data:image/png;base64,AAAA" alt="">
        <iframe srcdoc="&lt;img src='data:image/png;base64,BBBB'&gt;"></iframe>
        <svg><rect fill="url(#gradient)"></rect><use href="#mark"></use></svg>
        </body></html>"""
        self.assertEqual(validate_portability.validate_portability(html), [])

    def test_rejects_relative_remote_and_srcset_fetches(self) -> None:
        html = """<!doctype html><html><head>
        <link rel="stylesheet" href="theme.css">
        <style>.hero { background: url(https://cdn.example/hero.webp); }</style>
        <style>@import "print-theme.css";</style>
        <style>/* @import "ignored-comment.css"; .x { fill: url(ignored.svg); } */</style>
        </head><body>
        <img src="images/photo.png" srcset="data:image/png;base64,AAAA 1x, photo@2x.png 2x">
        <img srcset="data:image/png;base64,BBBB, descriptorless-remote.png 2x">
        <img src="">
        <video poster="poster.jpg"><source src="clip.mp4"></video>
        <iframe src="https://example.com/embed"></iframe>
        <iframe srcdoc="&lt;img src='nested-frame.png'&gt;"></iframe>
        <table background="legacy-grid.png"><tr><td></td></tr></table>
        <svg><rect fill="url(patterns.svg#dots)"></rect><image href="diagram-texture.png"></image></svg>
        </body></html>"""
        errors = validate_portability.validate_portability(html)
        joined = "\n".join(errors)
        for reference in (
            "theme.css",
            "https://cdn.example/hero.webp",
            "print-theme.css",
            "images/photo.png",
            "photo@2x.png",
            "descriptorless-remote.png",
            "poster.jpg",
            "clip.mp4",
            "https://example.com/embed",
            "nested-frame.png",
            "legacy-grid.png",
            "patterns.svg#dots",
            "diagram-texture.png",
        ):
            self.assertIn(reference, joined)
        self.assertIn("<img> src references non-embedded asset ''", joined)
        self.assertNotIn("ignored-comment.css", joined)
        self.assertNotIn("ignored.svg", joined)

    def test_ignores_normal_anchor_navigation(self) -> None:
        html = '<a href="https://example.com">source</a><a href="#slide-2">next</a>'
        self.assertEqual(validate_portability.validate_portability(html), [])

    def test_recursively_scans_nested_iframe_srcdoc(self) -> None:
        inner = '<img src="deep-frame.png">'
        middle = f'<iframe srcdoc="{escape(inner, quote=True)}"></iframe>'
        outer = f'<iframe srcdoc="{escape(middle, quote=True)}"></iframe>'
        errors = validate_portability.validate_portability(outer)
        self.assertIn("deep-frame.png", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
