#!/usr/bin/env python3
"""Shared fail-closed contract for theme homage visuals.

Every CSS theme must have exactly one ``hero`` and one ``map`` WebP in the
manifest. Theme installation is staged and validated as a complete candidate,
then committed with rollback if any target replacement fails.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from _common import SHARED, THEMES_CSS, discover_themes

VISUALS_DIR = SHARED / "assets" / "theme-visuals"
MANIFEST_PATH = VISUALS_DIR / "manifest.json"
REQUIRED_ROLES = frozenset({"hero", "map"})
_SAFE_WEBP_BASENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.webp$")


class ThemeVisualsError(ValueError):
    """Raised when the CSS/manifest/assets contract is incomplete or unsafe."""


def validate_webp(path: Path) -> tuple[int, int]:
    """Validate a WebP RIFF container and return its positive dimensions."""
    if not path.is_file():
        raise ThemeVisualsError(f"theme visual does not exist: {path}")
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ThemeVisualsError(f"theme visual is not a valid WebP file: {path}")
    riff_end = int.from_bytes(data[4:8], "little") + 8
    if riff_end != len(data):
        raise ThemeVisualsError(f"theme visual is not a valid WebP file: {path}")

    dimensions: tuple[int, int] | None = None
    offset = 12
    while offset < riff_end:
        if offset + 8 > riff_end:
            raise ThemeVisualsError(f"theme visual is not a valid WebP file: {path}")
        kind = data[offset:offset + 4]
        chunk_size = int.from_bytes(data[offset + 4:offset + 8], "little")
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        padded_end = payload_end + (chunk_size & 1)
        if payload_end > riff_end or padded_end > riff_end:
            raise ThemeVisualsError(f"theme visual is not a valid WebP file: {path}")
        payload = data[payload_start:payload_end]

        current: tuple[int, int] | None = None
        if kind == b"VP8 ":
            if len(payload) < 10 or payload[3:6] != b"\x9d\x01\x2a":
                raise ThemeVisualsError(f"theme visual is not a valid WebP file: {path}")
            current = (
                int.from_bytes(payload[6:8], "little") & 0x3FFF,
                int.from_bytes(payload[8:10], "little") & 0x3FFF,
            )
        elif kind == b"VP8L":
            if len(payload) < 5 or payload[0] != 0x2F:
                raise ThemeVisualsError(f"theme visual is not a valid WebP file: {path}")
            bits = int.from_bytes(payload[1:5], "little")
            if bits >> 29:
                raise ThemeVisualsError(f"theme visual is not a valid WebP file: {path}")
            current = ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
        elif kind == b"VP8X":
            if len(payload) < 10:
                raise ThemeVisualsError(f"theme visual is not a valid WebP file: {path}")
            current = (
                int.from_bytes(payload[4:7], "little") + 1,
                int.from_bytes(payload[7:10], "little") + 1,
            )

        if current is not None:
            if current[0] <= 0 or current[1] <= 0:
                raise ThemeVisualsError(f"theme visual is not a valid WebP file: {path}")
            dimensions = dimensions or current
        offset = padded_end

    if offset != riff_end or dimensions is None:
        raise ThemeVisualsError(f"theme visual is not a valid WebP file: {path}")
    return dimensions


def _read_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise ThemeVisualsError(f"theme visuals manifest does not exist: {manifest_path}")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ThemeVisualsError(
            f"cannot read theme visuals manifest {manifest_path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise ThemeVisualsError("theme visuals manifest root must be a JSON object")
    return raw


def load_and_validate_registry(
    css_path: Path = THEMES_CSS,
    visuals_dir: Path = VISUALS_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> dict[str, dict[str, Path]]:
    """Validate and return ``{theme: {role: resolved_asset_path}}``.

    The theme set is exact in both directions. Each manifest theme has exactly
    the two required roles, each role is unique, sources are safe basenames,
    and both distinct files have a WebP container signature.
    """
    css_path = Path(css_path)
    visuals_dir = Path(visuals_dir)
    manifest_path = Path(manifest_path)
    if not css_path.is_file():
        raise ThemeVisualsError(f"theme CSS does not exist: {css_path}")

    css_themes = set(discover_themes(css_path))
    raw = _read_manifest(manifest_path)
    visuals_root = visuals_dir.resolve()
    manifest_themes = set(raw)
    if css_themes != manifest_themes:
        missing = sorted(css_themes - manifest_themes)
        extra = sorted(manifest_themes - css_themes)
        raise ThemeVisualsError(
            "theme-set mismatch between CSS and visual manifest "
            f"(missing from manifest={missing}, missing from CSS={extra})"
        )

    registry: dict[str, dict[str, Path]] = {}
    for theme in sorted(css_themes):
        metadata = raw.get(theme)
        if not isinstance(metadata, dict):
            raise ThemeVisualsError(f"manifest theme {theme!r} must be an object")
        assets = metadata.get("assets")
        if not isinstance(assets, list):
            raise ThemeVisualsError(f"manifest theme {theme!r} assets must be a list")

        role_map: dict[str, Path] = {}
        source_names: set[str] = set()
        asset_identities: set[tuple[int, int]] = set()
        for entry in assets:
            if not isinstance(entry, dict):
                raise ThemeVisualsError(f"manifest theme {theme!r} has a non-object asset")
            role = entry.get("role")
            src = entry.get("src")
            if role in role_map:
                raise ThemeVisualsError(f"manifest theme {theme!r} has duplicate role {role!r}")
            if role not in REQUIRED_ROLES:
                raise ThemeVisualsError(
                    f"manifest theme {theme!r} must contain exactly the roles hero and map"
                )
            if not isinstance(src, str) or not _SAFE_WEBP_BASENAME_RE.fullmatch(src):
                raise ThemeVisualsError(
                    f"manifest theme {theme!r} role {role!r} src must be a safe WebP basename"
                )
            if Path(src).name != src or Path(src).is_absolute():
                raise ThemeVisualsError(
                    f"manifest theme {theme!r} role {role!r} src must be a safe WebP basename"
                )
            if src in source_names:
                raise ThemeVisualsError(
                    f"manifest theme {theme!r} hero and map must reference distinct files"
                )
            source_names.add(src)
            asset_path = (visuals_dir / src).resolve()
            if not asset_path.is_relative_to(visuals_root):
                raise ThemeVisualsError(
                    f"manifest theme {theme!r} role {role!r} escapes theme visuals directory"
                )
            validate_webp(asset_path)
            stat = asset_path.stat()
            identity = (stat.st_dev, stat.st_ino)
            if identity in asset_identities:
                raise ThemeVisualsError(
                    f"manifest theme {theme!r} hero and map resolve to the same underlying asset"
                )
            asset_identities.add(identity)
            role_map[role] = asset_path

        if set(role_map) != REQUIRED_ROLES:
            raise ThemeVisualsError(
                f"manifest theme {theme!r} must contain exactly the roles hero and map"
            )
        registry[theme] = role_map
    return registry


def _replace_staged(staged: Path, target: Path) -> None:
    """Replace one target; kept separate so rollback behavior is testable."""
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staged, target)


def _manifest_with_theme(
    current: dict[str, Any], theme: str, hero_name: str, map_name: str
) -> dict[str, Any]:
    candidate = json.loads(json.dumps(current))
    old = candidate.get(theme)
    metadata = dict(old) if isinstance(old, dict) else {}
    metadata.setdefault("visualIdentity", f"custom homage for {theme}")
    metadata["assets"] = [
        {"role": "hero", "src": hero_name},
        {"role": "map", "src": map_name},
    ]
    candidate[theme] = metadata
    return candidate


def install_theme_atomic(
    *,
    theme: str,
    candidate_css: str,
    css_path: Path,
    hero_image: Path,
    map_image: Path,
    visuals_dir: Path = VISUALS_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> None:
    """Install CSS, normalized homage images, and manifest as one transaction.

    A complete staged registry is validated before targets are touched. If a
    replacement fails, every target is restored byte-for-byte and newly
    created targets are removed.
    """
    css_path = Path(css_path)
    hero_image = Path(hero_image)
    map_image = Path(map_image)
    visuals_dir = Path(visuals_dir)
    manifest_path = Path(manifest_path)
    validate_webp(hero_image)
    validate_webp(map_image)
    if hero_image.resolve() == map_image.resolve():
        raise ThemeVisualsError("hero and map inputs must be distinct WebP files")

    # The current repository must be coherent before extending or replacing it.
    load_and_validate_registry(css_path, visuals_dir, manifest_path)
    current_manifest = _read_manifest(manifest_path)
    hero_name = f"{theme}-hero.webp"
    map_name = f"{theme}-map.webp"
    candidate_manifest = _manifest_with_theme(current_manifest, theme, hero_name, map_name)

    css_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".theme-install-", dir=css_path.parent) as tmp:
        stage = Path(tmp)
        stage_css = stage / css_path.name
        stage_visuals = stage / "theme-visuals"
        stage_visuals.mkdir()
        for item in visuals_dir.iterdir():
            if item.is_file() and item.name != manifest_path.name:
                shutil.copy2(item, stage_visuals / item.name)
        stage_manifest = stage_visuals / "manifest.json"
        stage_css.write_text(candidate_css, encoding="utf-8")
        shutil.copy2(hero_image, stage_visuals / hero_name)
        shutil.copy2(map_image, stage_visuals / map_name)
        stage_manifest.write_text(
            json.dumps(candidate_manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        load_and_validate_registry(stage_css, stage_visuals, stage_manifest)

        targets = [
            (stage_visuals / hero_name, visuals_dir / hero_name),
            (stage_visuals / map_name, visuals_dir / map_name),
            (stage_manifest, manifest_path),
            (stage_css, css_path),
        ]
        backups: dict[Path, bytes | None] = {
            target: target.read_bytes() if target.is_file() else None
            for _, target in targets
        }
        try:
            for staged, target in targets:
                _replace_staged(staged, target)
            # Validate the committed filesystem view while rollback state is
            # still available. A failure here is as transactional as a failed
            # replacement: no partial registry may remain installed.
            load_and_validate_registry(css_path, visuals_dir, manifest_path)
        except BaseException:
            for target, previous in backups.items():
                if previous is None:
                    target.unlink(missing_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(previous)
            raise
