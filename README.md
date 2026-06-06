# Premium Presentations

HTML slide decks with live theme switching, optional 3D parallax background, and shared SlideEngine.

Repository: [bruno-rv/premium-presentations.git](https://github.com/bruno-rv/premium-presentations.git)

The repository root only carries repository metadata. The actual skill and deck
framework live under `skill/`.

## Quick start

```bash
cd skill

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

Run these from `skill/`.

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

These paths are under `skill/`.

| File | Purpose |
|------|---------|
| `skill/shared/premium-themes.css` | Editorial · Warm · Red tokens |
| `skill/shared/premium-deck.css` | Slide layout, typography, tables |
| `skill/shared/premium-components.css` | Illustrative components (journey, compare, timeline, code window, bars) |
| `skill/shared/premium-diagrams.css` | Diagram slides and centered Excalidraw-style canvas |
| `skill/shared/premium-mermaid.js` | Mermaid hand-drawn theme and theme-change re-render |
| `skill/shared/premium-controls.js` | Theme switch and 3D background toggle |
| `skill/shared/premium-annotations.css` | Marker and laser styles |
| `skill/shared/premium-annotations.js` | Marker and laser behavior |
| `skill/shared/slide-engine.js` | Navigation |

**Controls (left edge, hover to expand):** Theme · **Marker** · **Clear** · **Laser** · **3D background**.

**Shortcuts:** `M` marker · `L` laser · `C` clear · `H` hide/show tools (opens pinned) · `3` 3D parallax.

## Extras (Cluster A — Live + Cluster B — Distribution)

Engine modules in `skill/shared/premium-{timer,presenter,clicker,tts,search,og-cover}.js` plus `skill/shared/premium-extras.css`. Auto-bundled by `bundle-deck.py` when the template links them.

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

The canonical skill package lives in `skill/`. It contains `SKILL.md`,
`agents/openai.yaml`, `reference/`, `scripts/`, `templates/`, `shared/`,
`assets/`, and `decks/`. Copy the `skill/` directory to a skills directory as
`premium-presentations/` to deploy it as one self-contained skill.

Do not commit generated vendor mirrors. Claude, Cursor, Codex, and other agents
should consume the same `skill/` payload by copying or packaging that directory.

### Skill structure

The canonical skill follows
[Claude skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices):

| Path | Purpose |
|------|---------|
| `skill/SKILL.md` | Concise entry point and trigger metadata |
| `skill/reference/` | One-level, progressively loaded guidance files |
| `skill/scripts/` | Deterministic scaffolding, bundling, validation, and Node test metadata |
| `skill/assets/studio/` | Static local gallery for previews and example decks |
| `skill/templates/` | Deck and component source templates |
| `skill/shared/` | Runtime CSS, JavaScript, and theme assets |
| `skill/decks/` | Complete example decks and generated artifacts |

Long reference files include a `Contents` section so an agent can preview scope
before loading details. Avoid adding new nested reference directories unless a
domain grows large enough to justify a separate directly linked file. Keep new
agent-facing docs under `skill/reference/`.

Root-level files are intentionally limited to repository entry points and
repository metadata. The skill payload is inside `skill/`.

Repository reference: [bruno-rv/premium-presentations.git](https://github.com/bruno-rv/premium-presentations.git). Red theme: [themes-red.md](skill/reference/themes-red.md).

```bash
cd skill
./scripts/new-deck.sh red my-show "Show Review" 12
```
