# Premium Presentations — Creative components

Portable patterns for Premium Presentations decks. Use with `assets/shared/premium-components.css` linked after `premium-deck.css`.

**When generating decks:** pick 2–4 “hero” visual slides per act (journey, compare, timeline, stage card) — not every slide needs a custom component.

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

## Shared utilities (CSS only)

| Class | Effect |
|-------|--------|
| `shimmer-text`, `shimmer-gold` | Animated gradient titles |
| `gradient-text`, `gradient-gold` | Static gradient text |
| `slide__glow`, `slide__glow--gold` | Radial background halo |
| `geo-particle`, `geo-particle--1`… | Floating accent dots |
| `content-center-wrap` | Vertically center slide body |
| `flow-r`, `flow-cw` | Animated SVG connector strokes |
| `pulse-glow`, `pulse-gold` (inline `animation:`) | Breathing card glow |
| `tag-red`, `tag-gold`, `tag-orange`, `tag-cyan` | Extra tag colors |
| `why-panel` | Bordered takeaway block with uppercase lead label and short body |

## Compare modifiers

Use semantic modifiers on `.compare-panel` instead of inline colors:

| Modifier | Meaning | Accent |
|----------|---------|--------|
| `compare-panel--down` | Cost, constraint, legacy path, downside | red |
| `compare-panel--up` | Better path, uplift, improvement | blue |
| `compare-panel--vector` | Vector-search side of a comparison | blue |
| `compare-panel--graph` | Graph side of a comparison | violet |

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
| Flowchart / sequence / ER | `slide--diagram` + Mermaid (`premium-mermaid.js`) |
| Branded journey / neon nodes / metaphor | Custom SVG (P14, P9) |
| Tabular metrics | `stats-row`, `bar-chart`, or `data-table` |

## Link in deck HTML

```html
<link rel="stylesheet" href="../../shared/premium-components.css">
```

`scripts/bundle_deck.py` inlines this automatically when the link is present in a deck under `assets/decks/`.
