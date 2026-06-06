# Premium Presentations

HTML slide decks with live theme switching, optional 3D parallax background, and shared SlideEngine.

Repository: [bruno-rv/premium-presentations.git](https://github.com/bruno-rv/premium-presentations.git)

This repository root is the skill directory. Its folder name must remain
`premium-presentations`, matching the `name` field in `SKILL.md`.

## Quick start

```bash
# Scaffold (spec auto-created when slides ≥ 8)
./scripts/new-deck.sh warm rag-vector-graph "My Title" 15

# Validate starter structure
./scripts/validate-deck.sh decks/rag-vector-graph/rag-vector-graph-slides.html

# Open
open assets/studio/index.html
open decks/rag-vector-graph/rag-vector-graph-slides.html
```

Serve locally if Mermaid fails on `file://`:

```bash
python3 -m http.server 8765
# http://localhost:8765/decks/rag-vector-graph/rag-vector-graph-slides.html
```

## Skill Scripts

Run these from the repository root.

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

When scaffolding with a slide count of 8 or more, `new-deck.sh` also creates a
planning spec. Validate against that spec after the deck HTML has been authored
to the planned slide count.

**External deps (CDN):** Google Fonts, and Mermaid on diagram decks.

## Shared Runtime

| File | Purpose |
|------|---------|
| `shared/premium-themes.css` | Editorial · Warm · Red tokens |
| `shared/premium-deck.css` | Slide layout, typography, tables |
| `shared/premium-components.css` | Illustrative components (journey, compare, timeline, code window, bars) |
| `shared/premium-diagrams.css` | Diagram slides and centered Excalidraw-style canvas |
| `shared/premium-mermaid.js` | Mermaid hand-drawn theme and theme-change re-render |
| `shared/premium-controls.js` | Theme switch and 3D background toggle |
| `shared/premium-annotations.css` | Marker and laser styles |
| `shared/premium-annotations.js` | Marker and laser behavior |
| `shared/slide-engine.js` | Navigation |

**Controls (left edge, hover to expand):** Theme · **Marker** · **Clear** · **Laser** · **3D background**.

**Shortcuts:** `M` marker · `L` laser · `C` clear · `H` hide/show tools (opens pinned) · `3` 3D parallax.

## Extras (Cluster A — Live + Cluster B — Distribution)

Engine modules in `shared/premium-{timer,presenter,clicker,tts,search,og-cover}.js` plus `shared/premium-extras.css`. Auto-bundled by `bundle-deck.py` when the template links them.

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

The canonical skill package is this repository root. It contains `SKILL.md`,
`agents/openai.yaml`, `references/`, `scripts/`, `templates/`, `shared/`,
`assets/`, and `decks/`.

For filesystem-based clients, clone or copy this repository as the skill
directory named `premium-presentations`. Do not commit generated vendor mirrors
such as `.claude/skills/`, `.cursor/skills/`, `.codex/skills/`, or
`.agents/skills/`.

For Claude.ai ZIP upload, zip the `premium-presentations/` directory itself, not
only its contents, so the archive contains `premium-presentations/SKILL.md`.

### Skill structure

The canonical skill follows
[Claude skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices):

| Path | Purpose |
|------|---------|
| `SKILL.md` | Concise entry point and trigger metadata |
| `references/` | One-level, progressively loaded guidance files |
| `scripts/` | Deterministic scaffolding, bundling, validation, and Node test metadata |
| `assets/studio/` | Static local gallery for previews and example decks |
| `templates/` | Deck and component source templates |
| `shared/` | Runtime CSS, JavaScript, and theme assets |
| `decks/` | Complete example decks and generated artifacts |

Long reference files include a `Contents` section so an agent can preview scope
before loading details. Avoid adding new nested reference directories unless a
domain grows large enough to justify a separate directly linked file. Keep new
agent-facing docs under `references/`.

The root-level resource directories are intentional because the repository root
is the skill package. Do not add another generic wrapper folder.

Repository reference: [bruno-rv/premium-presentations.git](https://github.com/bruno-rv/premium-presentations.git). Red theme: [themes-red.md](references/themes-red.md).

```bash
./scripts/new-deck.sh red my-show "Show Review" 12
```
