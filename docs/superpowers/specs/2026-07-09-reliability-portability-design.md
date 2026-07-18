# Reliability, Portability, and Theme Homage Design

Date: 2026-07-09
Status: Approved for implementation

## Objective

Make Premium Presentations safe and predictable for both Claude Code and Codex while guaranteeing that every discovered theme carries its homage visuals into every newly generated standalone deck.

## Design principles

- Theme installation is atomic: CSS and both homage images are installed together or nothing changes.
- Theme discovery is fail-closed: the CSS theme set, visual manifest, and files must agree exactly.
- Newly scaffolded decks are transactional and self-contained.
- Presenter synchronization accepts messages only from trusted peers and sessions.
- LAN sharing exposes only the generated deck and requires a room token for control traffic.
- The doctor rejects non-portable references that would break an offline deck.
- Claude Code and Codex metadata are validated independently in CI.

## Theme homage contract

The canonical theme registry remains the union of theme CSS files and
`assets/shared/assets/theme-visuals/manifest.json`, but the sets must be identical.
Every theme entry must contain exactly these roles:

```json
{
  "theme-name": {
    "assets": [
      {"role": "hero", "src": "theme-name-hero.webp"},
      {"role": "map", "src": "theme-name-map.webp"}
    ]
  }
}
```

The referenced files must be safe basenames, distinct underlying assets,
structurally valid WebP files with positive dimensions, and present in the
visual directory. Runtime theme discovery and bundling must stop with an
actionable error when this contract is broken. No filename guessing or
visual-embedding bypass is allowed for a standalone deck with visual slides.

`scripts/generate_theme.py` installs a persisted theme through a staging directory. It validates the source hero and map images, creates CSS and normalized filenames, updates a staged manifest, validates the complete staged registry, then replaces the final files. If any validation or write fails, the existing theme registry is unchanged.

Dry-run output may still preview CSS without images. Persisted generation requires both `--hero-image` and `--map-image`.

## Transactional deck scaffolding

`scripts/new-deck.sh` renders into a temporary directory under `assets/decks/`. A small Python renderer performs literal placeholder substitution with context-safe HTML escaping. The scaffold is bundled and validated before an atomic rename to its final name. A trap removes staging data on any failure, so partial decks are never left behind.

Titles such as `R&D | <Q3> "Launch"` must render correctly in metadata, headings, and attributes without shell, sed, or HTML injection.

## Presenter trust boundary

Direct `window.postMessage` traffic is accepted only when origin, source window, and session all match the expected peer. HTTP(S) sends use `location.origin`; file-based decks may use `*`, with source and session checks still required. BroadcastChannel and storage transports keep their existing same-deck session protocol.

The presenter popup may adopt its opener during the initial handshake, but control and snapshot messages require the established session. Remote speaker notes are sanitized through a deliberately small HTML allowlist before insertion.

## LAN sharing

The share command copies only the bundled deck to a temporary serving directory as `index.html`; it never serves the source deck directory. It generates a cryptographically random room token and adds it to presenter and follower URLs. The sync server requires that token on every `/slide` read or write and compares it in constant time. The follower preserves the token in polling requests.

## Offline portability

A new portability validator scans the bundled document for fetchable references in HTML elements, `srcset`, and CSS `url()` values. Data URIs and internal anchors are allowed. Relative, local, and remote fetches are rejected unless explicitly represented as embedded data. `deck_doctor.py` runs this validator as part of its standard gate.

## Compatibility and CI

Claude Code metadata uses only schema-valid plugin paths; Codex keeps its existing `.codex-plugin` metadata. Tests assert that both manifests point to real skills and commands, that package metadata is consistent, and that every documented test suite is included in an aggregate test command. CI runs Python, Node, bundling, runtime contracts, theme visual validation, Claude strict validation, and browser-backed smoke tests.

## Deferred roadmap

The next product features remain:

1. Spec-aware partial slide regeneration with stable slide identity.
2. A polished safe-share/follow experience built on the hardened token protocol.
3. A user-facing atomic theme package installer and gallery built on the registry contract.

This implementation establishes the reliability and security foundations for those features without silently expanding into their full product designs.
