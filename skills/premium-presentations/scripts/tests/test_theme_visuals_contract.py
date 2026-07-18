#!/usr/bin/env python3
"""Fail-closed contract tests for the theme homage visual registry."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from theme_visuals import ThemeVisualsError, load_and_validate_registry  # noqa: E402

BUILTIN_VISUALS = ROOT / "assets" / "shared" / "assets" / "theme-visuals"


def _webp(path: Path, name: str = "editorial-hero.webp") -> None:
    shutil.copy2(BUILTIN_VISUALS / name, path)


class ThemeVisualRegistryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.css = base / "premium-themes.css"
        self.visuals = base / "theme-visuals"
        self.visuals.mkdir()
        self.manifest = self.visuals / "manifest.json"
        self.css.write_text(
            'html[data-theme="alpha"] { --bg: #000; }\n', encoding="utf-8"
        )
        _webp(self.visuals / "alpha-hero.webp", "editorial-hero.webp")
        _webp(self.visuals / "alpha-map.webp", "editorial-map.webp")
        self._write_manifest(
            {
                "alpha": {
                    "assets": [
                        {"role": "hero", "src": "alpha-hero.webp"},
                        {"role": "map", "src": "alpha-map.webp"},
                    ]
                }
            }
        )

    def _write_manifest(self, data: dict) -> None:
        self.manifest.write_text(json.dumps(data), encoding="utf-8")

    def _load(self):
        return load_and_validate_registry(self.css, self.visuals, self.manifest)

    def test_valid_registry_returns_exact_role_paths(self) -> None:
        registry = self._load()
        self.assertEqual(set(registry), {"alpha"})
        self.assertEqual(set(registry["alpha"]), {"hero", "map"})
        self.assertEqual(
            registry["alpha"]["hero"], (self.visuals / "alpha-hero.webp").resolve()
        )

    def test_css_theme_missing_from_manifest_is_rejected(self) -> None:
        self.css.write_text(
            self.css.read_text(encoding="utf-8")
            + 'html[data-theme="beta"] { --bg: #fff; }\n',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ThemeVisualsError, "theme-set mismatch"):
            self._load()

    def test_manifest_theme_missing_from_css_is_rejected(self) -> None:
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["beta"] = data["alpha"]
        self._write_manifest(data)
        with self.assertRaisesRegex(ThemeVisualsError, "theme-set mismatch"):
            self._load()

    def test_missing_role_is_rejected(self) -> None:
        self._write_manifest(
            {"alpha": {"assets": [{"role": "hero", "src": "alpha-hero.webp"}]}}
        )
        with self.assertRaisesRegex(ThemeVisualsError, "exactly the roles"):
            self._load()

    def test_duplicate_role_is_rejected(self) -> None:
        self._write_manifest(
            {
                "alpha": {
                    "assets": [
                        {"role": "hero", "src": "alpha-hero.webp"},
                        {"role": "hero", "src": "alpha-map.webp"},
                    ]
                }
            }
        )
        with self.assertRaisesRegex(ThemeVisualsError, "duplicate role"):
            self._load()

    def test_unsafe_source_basename_is_rejected(self) -> None:
        self._write_manifest(
            {
                "alpha": {
                    "assets": [
                        {"role": "hero", "src": "../alpha-hero.webp"},
                        {"role": "map", "src": "alpha-map.webp"},
                    ]
                }
            }
        )
        with self.assertRaisesRegex(ThemeVisualsError, "safe WebP basename"):
            self._load()

    def test_roles_must_reference_distinct_files(self) -> None:
        self._write_manifest(
            {
                "alpha": {
                    "assets": [
                        {"role": "hero", "src": "alpha-hero.webp"},
                        {"role": "map", "src": "alpha-hero.webp"},
                    ]
                }
            }
        )
        with self.assertRaisesRegex(ThemeVisualsError, "distinct"):
            self._load()

    def test_missing_file_is_rejected(self) -> None:
        (self.visuals / "alpha-map.webp").unlink()
        with self.assertRaisesRegex(ThemeVisualsError, "does not exist"):
            self._load()

    def test_invalid_webp_bytes_are_rejected(self) -> None:
        (self.visuals / "alpha-map.webp").write_bytes(b"not-a-webp")
        with self.assertRaisesRegex(ThemeVisualsError, "valid WebP"):
            self._load()

    def test_header_only_riff_webp_is_rejected(self) -> None:
        (self.visuals / "alpha-map.webp").write_bytes(b"RIFF\x04\x00\x00\x00WEBP")
        with self.assertRaisesRegex(ThemeVisualsError, "valid WebP"):
            self._load()

    def test_truncated_chunk_payload_is_rejected(self) -> None:
        source = (BUILTIN_VISUALS / "editorial-map.webp").read_bytes()
        (self.visuals / "alpha-map.webp").write_bytes(source[:-17])
        with self.assertRaisesRegex(ThemeVisualsError, "valid WebP"):
            self._load()

    def test_symlink_escape_is_rejected(self) -> None:
        outside = self.visuals.parent / "outside.webp"
        _webp(outside)
        (self.visuals / "alpha-map.webp").unlink()
        (self.visuals / "alpha-map.webp").symlink_to(outside)
        with self.assertRaisesRegex(ThemeVisualsError, "escapes theme visuals directory"):
            self._load()

    def test_contained_symlink_alias_for_both_roles_is_rejected(self) -> None:
        (self.visuals / "alpha-map.webp").unlink()
        (self.visuals / "alpha-map.webp").symlink_to(self.visuals / "alpha-hero.webp")
        with self.assertRaisesRegex(ThemeVisualsError, "same underlying asset"):
            self._load()

    def test_contained_hardlink_alias_for_both_roles_is_rejected(self) -> None:
        (self.visuals / "alpha-map.webp").unlink()
        os.link(self.visuals / "alpha-hero.webp", self.visuals / "alpha-map.webp")
        with self.assertRaisesRegex(ThemeVisualsError, "same underlying asset"):
            self._load()


if __name__ == "__main__":
    unittest.main()
