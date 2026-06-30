# Premium Presentations — Creative components

Portable patterns for Premium Presentations decks. Use with `assets/shared/premium-components.css` linked after `premium-deck.css`.

**When generating decks (hard rule):** every content slide names a component from the routing table below — bare heading + paragraph slides are not allowed (title, quote, and divider slides are exempt). Give 2–4 hero slides per act the heavier components (FLOW+, P14, P9, STG); anchor the remaining content slides with lighter patterns (STAT, kpi-row, content-grid + aside-card, PIPE, why-panel, data-table).

## Quick reference

| ID | Component | Use when | Snippet |
|----|-----------|----------|---------|
| **P14** | Journey path | Curriculum / roadmap / phases | `assets/templates/components/journey-path.snippet.html` |
| **P9** | Compare split | A vs B, workflow vs agentic, era shift | `assets/templates/components/compare-paradigm.snippet.html` |
| **DIV+** | Act divider | Section break with ghost number + shimmer title (use `<div class="slide__number">` inside `slide--divider` — sized via `premium-components.css`, not corner watermark) | `assets/templates/components/divider-act.snippet.html` |
| **TL** | Timeline grid | 3 eras / milestones on one line | `assets/templates/components/timeline.snippet.html` |
| **STG** | Stage card | Deep dive: copy + diagram column | `assets/templates/components/stage-card.snippet.html` |
| **GL** | Glass + code | CLAUDE.md, config, spec preview | `assets/templates/components/glass-code-window.snippet.html` |
| **BAR** | Bar chart | 80/20, before/after metrics | `assets/templates/components/bar-chart.snippet.html` |
| **FLOW** | Setup flow | 3–4 activation steps with arrows | `assets/templates/components/setup-flow.snippet.html` |
| **STAT** | Stats row | 3 KPIs with accent top bar | `assets/templates/components/stats-row.snippet.html` |
| **CHK** | Checklist grid | Closure / readiness (2 columns) | `assets/templates/components/checklist.snippet.html` |
| **WHY** | Why panel | Short takeaway / implication callout | CSS-only: `.why-panel` |
| **FLOW+** | Live flow | Animated architecture / data-flow with phase spotlight (requires `premium-flow.js`) | `assets/templates/components/live-flow.snippet.html` |
| **PIPE** | Pipeline vertical | Sequential stages / medallion layers, 3–6 steps top-down | `assets/templates/components/pipeline-vertical.snippet.html` |
| **TERM** | Terminal window | CLI demos, commands, logs | `assets/templates/components/terminal-window.snippet.html` |
| **RAIL** | Accent rail | Left-edge gradient rail on text-leaning content slides | CSS-only: `slide--rail` modifier |
| **GLOSS** | Glossary term links | Inline term buttons with definition popup — use when a slide deck introduces many specialized terms (requires `premium-glossary.js`) | `assets/templates/components/glossary.snippet.html` |
| **DP-LAY** | Design Power layouts | Executive summary, evidence wall, process ladder, decision matrix, before/after | `PremiumDesignPower.layouts.render(...)` |
| **DP-VIZ** | Data visualization | Line, scatter, waterfall, funnel, heatmap, Sankey-style flow, KPI trend | `PremiumDesignPower.dataViz.render(...)` |
| **DP-COMP** | Design Power components | Runtime-rendered checklist, stats, compare, timeline, code blocks | `PremiumDesignPower.components.render(...)` |

## Routing: content type → component

Pick the slide's visual from its content type. When two fit, prefer the one
not yet used on the previous two slides.

| Content type | Component |
|--------------|-----------|
| Architecture / "how it works" / request-response path | **FLOW+** live flow (Mermaid `slide--diagram` if >8 nodes) |
| Sequential process, top-down narrative | **PIPE** pipeline-vertical |
| 3–4 activation steps, horizontal | **FLOW** setup-flow |
| A vs B, tradeoff, era shift | **P9** compare split |
| Metrics / KPIs | **STAT** stats row or `kpi-row` (+ **BAR** for proportions) |
| History, eras, milestones | **TL** timeline grid |
| Deep-dive concept (copy + diagram) | **STG** stage card |
| Config, spec, code preview | **GL** glass + code |
| CLI session, commands, logs | **TERM** terminal window |
| Roadmap / curriculum / phases | **P14** journey path |
| Readiness, closure checklist | **CHK** checklist grid |
| Data / comparison matrix | `data-table` in `table-scroll` |
| Data story / trend / funnel / matrix / flow volume | **DP-VIZ** data visualization |
| Deck design decision / tradeoff / prioritized roadmap | **DP-LAY** decision matrix or evidence wall |
| Text-leaning slide with aside | `content-grid` + `aside-card`, add **RAIL** |
| Single takeaway / implication | **WHY** why panel (appended after the main visual) |

## Layout primitives (`premium-deck.css`)

| Class | Effect |
|-------|--------|
| `slide--content` + `content-grid` | 2-column text + aside layout |
| `aside-card` | Bordered aside card with mono header + `→` list |
| `slide--split` + `split` | Equal 2-panel split; `panel` for each side |
| `kpi-row` / `kpi` / `kpi-val` / `kpi-lbl` | Lightweight 3-up KPI grid (lighter than STAT) |
| `table-scroll` + `data-table` | Scrollable themed data table |
| `why-panel` | Bordered takeaway block with uppercase lead label and short body |

## Visual Design Power (`premium-design-power.css/js`)

Use `window.PremiumDesignPower` when a deck or the Studio needs generated,
portable visual blocks rather than hand-authored markup.

| API | Provides |
|-----|----------|
| `themeComposer.buildThemeCss(config)` | Sanitized `html[data-theme="..."]` CSS token block |
| `themeComposer.applyTheme(config, document)` | Injects the token block and switches the active deck theme |
| `components.render(name, data)` | Checklist, stats, compare, timeline, and code snippets |
| `layouts.render(name, data)` | Executive summary, evidence wall, process ladder, before/after, decision matrix |
| `density.analyzeSlide(slide)` | Word/reveal/card metrics plus density warnings |
| `motionProfiles.apply(name, document)` | Deck-level motion variables and 3D defaults |
| `dataViz.render(type, data)` | Line, scatter, waterfall, funnel, heatmap, Sankey-style flow, KPI trend |
| `assets.audit(documentOrElement)` | Portable visual-asset inventory and warnings |

## Shared utilities (CSS only)

| Class | Effect |
|-------|--------|
| `shimmer-text`, `shimmer-gold` | Gradient titles (static by default; add `shimmer-text--live` to animate) |
| `gradient-text`, `gradient-gold` | Static gradient text |
| `slide__glow`, `slide__glow--gold` | Radial background halo |
| `geo-particle` + `geo-particle--1/2/3` | Floating accent dots (positioned variants) |
| `content-center-wrap` | Vertically center slide body |
| `flow-r`, `flow-cw` | Animated SVG connector strokes |
| `pulse-glow`, `pulse-gold`, `pulse-green` (inline `animation:`) | Breathing card glow |
| `stage-card--pulse` | Pulsing border glow on a stage card |
| `tag-red`, `tag-gold`, `tag-orange`, `tag-cyan` | Extra tag colors |

## Animation guidance

- **Entrance:** `.reveal` stagger on slide children — the only stepping mechanism.
- **Ambient:** `geo-particle` dots and `slide__glow` halos on title/divider slides only.
- **Emphasis:** `pulse-glow` family sparingly — max one pulsing element per slide.
- **Diagram motion:** `flow-r`/`flow-cw` strokes on SVG paths; FLOW+ arrow shimmer.
- **Titles:** `shimmer-text--live` opt-in, divider/title slides only.
- **3D depth tiers:** under `data-3d="depth"` the runtime auto-elevates the
  component vocabulary (stage-card, glass-card/code-window, compare panels,
  terminal-window at 48px; stat cards, timeline cols, setup steps, flow nodes,
  pipeline stages, checklist items, KPIs at 32px; why-panel, aside-card,
  tables at 24px; labels at 8px). Opt out per element with `data-flat`.
- All of the above are disabled automatically under `prefers-reduced-motion`.

## Compare modifiers

Use semantic modifiers on `.compare-panel` instead of inline colors:

| Modifier | Meaning | Accent |
|----------|---------|--------|
| `compare-panel--down` | Cost, constraint, legacy path, downside | red |
| `compare-panel--up` | Better path, uplift, improvement | blue |
| `compare-panel--vector` | Vector-search side of a comparison | blue |
| `compare-panel--graph` | Graph side of a comparison | violet |

## Live flow (FLOW+)

`.live-flow` container holding `.flow-node` (`__icon`, `__title`, `__sub`) and
`.flow-arrow` (`__line` > `__shimmer`, `__label`) children plus an optional
`.live-flow__banner`. `premium-flow.js` reads `data-flow-phases` (JSON array of
phase objects) and `data-flow-interval` (ms) and cycles `.is-active` across
nodes/arrows — glow on the active node, traveling shimmer on the active arrow.
The bundler inlines `premium-flow.js` automatically when `.live-flow` is
present. Start from the snippet; keep 3–6 nodes.

## Why panel

Use a `.why-panel` after the main visual when the audience needs one crisp
interpretation or consequence.

```html
<div class="why-panel reveal">
  <strong>Why it matters</strong>
  <p>One sentence that turns the diagram into a decision.</p>
</div>
```

## Spec authoring

In `*-slide-spec.md`, set **Visual Pattern** to component ID (e.g. `P9 Compare split`) so builders pull the right snippet.

Example row:

```markdown
| 5 | Concept | Era shift 2026 | Experimentation vs Production | P9 compare-paradigm | Why production wins |
```

## SVG guidance

- Inline `<svg>` inside `.stage-card__visual`, `.journey-stage`, or compare panels.
- Journey slides use `.journey-stage > svg` with `circle.journey-node` markers;
  `premium-journey.js` builds the path and moving dots from those nodes.
- Use `class="flow-r"` on dashed paths for motion.
- Theme-aware strokes: `stroke="var(--accent)"`, `fill="var(--gold-dim)"`.
- Keep `viewBox` fixed; let CSS scale width to 100%.

## Mermaid vs custom SVG

| Need | Use |
|------|-----|
| Simple flowchart | `slide--diagram` + portable Mermaid fallback (`premium-mermaid.js`) |
| Sequence / ER / class / state diagram | Full Mermaid preloaded locally as `window.mermaid`, or custom SVG |
| Branded journey / neon nodes / metaphor | Custom SVG (P14, P9) |
| Tabular metrics | `stats-row`, `bar-chart`, or `data-table` |

## Link in deck HTML

```html
<link rel="stylesheet" href="../../shared/premium-components.css">
```

`scripts/bundle_deck.py` inlines this automatically when the link is present in a deck under `assets/decks/`.
