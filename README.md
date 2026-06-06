# Premium Presentations

HTML slide decks with live theme switching, optional 3D parallax background, and shared SlideEngine.

Repository: [bruno-rv/premium-presentations.git](https://github.com/bruno-rv/premium-presentations.git)

## Quick start

```bash
# Scaffold (spec auto-created when slides ≥ 8)
./scripts/new-deck.sh warm rag-vector-graph "My Title" 15

# Validate structure
./scripts/validate-deck.sh decks/rag-vector-graph/rag-vector-graph-slides.html decks/rag-vector-graph/rag-vector-graph-slide-spec.md

# Open
open app/index.html
open decks/rag-vector-graph/rag-vector-graph-slides.html
```

Serve locally if Mermaid fails on `file://`:

```bash
python3 -m http.server 8765
# http://localhost:8765/decks/rag-vector-graph/rag-vector-graph-slides.html
```

## Scripts

| Script | Purpose |
|--------|---------|
| `new-deck.sh` | Scaffold deck → **standalone** `*-slides.html` + optional spec |
| `bundle-deck.sh` | Inline `shared/` CSS/JS into one HTML file |
| `bundle-all-decks.sh` | Re-bundle decks that still link to `../../shared/` |
| `validate-deck.sh` | Lint deck + **diagram layout rules** (structure, fit JS, anti-clip CSS) |

## Standalone decks (one file per presentation)

Each deck is a **single HTML file** (all engine CSS/JS inlined). Open it directly or email it — no `shared/` folder required on the machine that presents it.

```bash
./scripts/new-deck.sh warm my-talk "My Title" 12   # writes standalone decks/my-talk/my-talk-slides.html
./scripts/bundle-deck.sh decks/my-talk/my-talk-slides.linked.html --in-place  # after editing shared/
```

Optional `*.linked.html` sources (with `../../shared/` links) are for maintainers who edit the framework and re-bundle. Slide **content** lives in the standalone `*-slides.html`.

**External deps (CDN):** Google Fonts, and Mermaid on diagram decks.

## Shared runtime (source for bundler)

| File | Purpose |
|------|---------|
| `shared/premium-themes.css` | Editorial · Warm · Red tokens |
| `shared/premium-deck.css` | Slide layout, typography, tables |
| `shared/premium-components.css` | Illustrative components (journey, compare, timeline, code window, bars) — see skill `components.md` |
| `shared/premium-diagrams.css` | Diagram slides — centered Excalidraw-style canvas |
| `shared/premium-mermaid.js` | Mermaid hand-drawn theme + theme-change re-render |
| `shared/premium-controls.js` | Theme switch + 3D background toggle |
| `shared/premium-annotations.css` | Marker + laser styles (theme contrast) |
| `shared/premium-annotations.js` | Marker + laser behavior |
| `shared/slide-engine.js` | Navigation |

**Controls (left edge, hover to expand):** Theme · **Marker** · **Clear** · **Laser** · **3D background**.

**Shortcuts:** `M` marker · `L` laser · `C` clear · `H` hide/show tools (opens pinned) · `3` 3D parallax.

## Extras (Cluster A — Live + Cluster B — Distribution)

Engine modules in `shared/premium-{timer,presenter,clicker,tts,search,og-cover}.js` + `shared/premium-extras.css`. Auto-bundled by `bundle-deck.py` when the template links them.

| Shortcut | Feature |
|----------|---------|
| `B` / `.` | Blackout / curtain |
| `⇧T` | Speaker timer (start/pause) |
| `⇧P` | Presenter view (popup with notes + peek + timer) |
| `⇧C` | Clicker / WebHID bind (keyboard fallback always active) |
| `⇧R` | TTS read-aloud |
| `⇧E` | Export PDF (print-CSS) |
| `⌘K` / `/` | Search / jump-to-slide |
| `?embedded=1` | Embed mode (hides chrome, postMessage API) |

**Extras scripts:**
- `./scripts/og-cover.sh <deck.html>` — render slide 1 as 1200×630 PNG for OG/Twitter unfurl.

**Notes per slide:** add `<aside class="notes">…</aside>` inside any `<section class="slide">`; the presenter view will display it.

## Skill

This repository is also a root-level skill: it contains `SKILL.md`,
`agents/openai.yaml`, `reference/`, `scripts/`, `templates/`, and `shared/`.
Copy or clone the whole `premium-presentations/` folder into a Claude, Cursor,
or Codex skills directory to deploy it as one self-contained skill.

Platform-specific copies are also checked in under
`.cursor/skills/premium-presentations/`, `.codex/skills/premium-presentations/`,
and `.claude/skills/premium-presentations/`. They are mirrored convenience
packages; the root folder is the primary skill package.

### Skill structure

The root skill follows
[Claude skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices):

| Path | Purpose |
|------|---------|
| `SKILL.md` | Concise entry point and trigger metadata |
| `reference/` | One-level, progressively loaded guidance files |
| `scripts/` | Deterministic scaffolding, bundling, and validation |
| `templates/` | Deck and component source templates |
| `shared/` | Runtime CSS, JavaScript, and theme assets |
| `decks/` | Complete example decks and generated artifacts |

Long reference files include a `Contents` section so an agent can preview scope
before loading details. Avoid adding new nested reference directories unless a
domain grows large enough to justify a separate directly linked file. Keep new
agent-facing docs under `reference/`; reserve `docs/` for project history and
planning artifacts that should not be loaded by default.

Repository reference: [bruno-rv/premium-presentations.git](https://github.com/bruno-rv/premium-presentations.git). Red theme: [themes-red.md](.cursor/skills/premium-presentations/themes-red.md).

```bash
./scripts/new-deck.sh red my-show "Show Review" 12
```
