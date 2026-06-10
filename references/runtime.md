# Premium Presentations — Runtime Reference

## Contents

- Shared runtime module table
- Diagram slides
- Theme discovery, visuals, and chrome
- Theme extension pattern
- Mermaid and theme changes
- SlideEngine
- File naming

## Shared runtime (`assets/shared/`)

Every generated deck carries the core modules. Conditional modules are listed
at the bottom of each table.

### CSS

| File | Role |
|------|------|
| `premium-themes.css` | `html[data-theme="..."]` CSS variables only; source of truth for discovered themes |
| `premium-deck.css` | Deck structure, slide typography, tables, KPIs, scroll chrome, controls panel, 3D parallax background |
| `premium-components.css` | Creative slide blocks: shimmer, compare-split, timeline, glass/code, journey SVG, bars, setup-flow, divider — see [components.md](components.md) |
| `premium-diagrams.css` | Diagram slide layout, Excalidraw-style canvas, zoom/pan viewport, Mermaid error panel |
| `premium-annotations.css` | Marker tool and laser pointer styles |
| `premium-extras.css` | Runtime chrome beyond layout: curtain, PDF export, embed mode, speaker timer pill, presenter popup UI, clicker status toast |
| `premium-red-brand.css` | Red theme only: brand bar and red mark classes |

### JS

| File | Role |
|------|------|
| `slide-engine.js` | `SlideEngine` — scroll-snap navigation and the `window.PremiumDeckControls` API; progress bar, dots (labels from heading/blockquote/cite/`data-nav-title`), counter, hints, keyboard/touch, `IntersectionObserver` for `.visible`/`.reveal`; dots auto-hide after 5s |
| `premium-controller.js` | Two-window focus-ownership state machine (`deck`/`popup`/`none`) exposed as `window.PremiumController`; presenter/clicker windows coordinate through it |
| `premium-controls.js` | Theme `<select>` + live switching, theme visual injection, 3D background, curtain, controls panel DOM, non-nav keyboard shortcuts |
| `premium-annotations.js` | Marker tool + laser pointer |
| `premium-timer.js` | Speaker countdown timer, pace tracking, alerts |
| `premium-tts.js` | SpeechSynthesis read-aloud |
| `premium-search.js` | Cmd+K fuzzy slide search |
| `premium-clicker.js` | WebHID clicker support + Shift+C keyboard binding |
| `premium-og-cover.js` | PNG slide export for OG covers |
| `premium-presenter.js` | Presenter popup lifecycle, BroadcastChannel/postMessage/localStorage bridge, presenter UI DOM |
| `premium-mermaid.js` | Conditional (Mermaid markup): CDN load, `handDrawn` theme, auto-fit, clip detection, zoom/pan, theme re-render |
| `premium-journey.js` | Conditional (`.journey-stage` markup): SVG path journey animation |
| `premium-red-chrome.js` | Conditional (red decks): brand bar + hero mark injection |

Linked decks use `../../shared/…` from `assets/decks/<slug>/`.

### Diagram slides (required markup)

Use `assets/templates/diagram-slide.snippet.html`. Validator enforces:

- `slide--diagram` → `slide__diagram-header` → `diagram-stage` → `mermaid-wrap` → `<pre class="mermaid">`
- `premium-diagrams.css` + `premium-mermaid.js` (inlined when bundled)
- No `max-height: 52vh|62vh` on `.mermaid-wrap` (clips content)
- Runtime: `fitMermaidDiagrams`, `bindMermaidFit`, `bindDiagramZoom`, `reportDiagramFit`
- **Diagram zoom:** scroll/pinch on canvas, drag to pan when zoomed, toolbar **+ / − / %**, double-click reset; **`+` `−` `0`** on diagram slides

**Theme discovery:** run `./scripts/list-themes.py`, or inspect `html[data-theme="..."]` selectors in `assets/shared/premium-themes.css`. Do not hardcode the current theme names in generators or skill instructions.

**Runtime contract:** run `./scripts/validate_runtime_contract.py` after any
template, theme, bundler, or shared runtime edit. It verifies discovered theme
scaffold templates, preview templates, and generated deck HTML files carry the
common CSS/JS stack, plus red brand modules where the active template/deck is
red, plus `premium-journey.js` when a file contains `.journey-stage` markup.

**Live theme switch:** `PremiumPresentations.setTheme('<theme>')` or UI control. The control panel discovers themes from loaded CSS. Dispatches `premium-theme-change` on `<html>`.

**Theme visuals:** `.slide--title` receives a `hero` visual; `.slide--divider` receives a `map` visual. Default assets follow `assets/shared/assets/theme-visuals/<theme>-<role>.webp`. Override with `data-theme-visual-<theme>-<role>` or `window.PremiumThemeVisuals`; disable per slide with `data-theme-visual="off"`.

**3D background:** `PremiumPresentations.setParallax(true)` or UI button / **`3`**; sets `data-parallax="on"`. Disabled when `prefers-reduced-motion`.

**Panel:** **`H`** hide/show; unhide pins panel open (`is-open`). **`3`** toggles parallax.

## Theme Extension Pattern

To add a theme:

1. Add `html[data-theme="<theme>"]` tokens in `assets/shared/premium-themes.css`.
2. Optionally add `assets/templates/<theme>-base.html` for theme-specific chrome
   (themes without one fall back to `assets/templates/premium-base.html`).
3. Optionally add visuals in `assets/shared/assets/theme-visuals/` using
   `<theme>-hero.webp` and `<theme>-map.webp`.
4. Load custom webfonts through template `<link>` tags or
   `data-theme-fonts-<theme>="https://..."` on `<html>`.
5. Optionally add a focused `themes-<theme>.md` reference if the theme has
   non-obvious rules.

Optional fixed **brand bar** for any theme (only if user requests custom branding):

```html
<div class="deck-bar">
  <div class="deck-bar__left">Organization</div>
  <div class="deck-bar__center">Tagline</div>
  <div class="deck-bar__right">Speaker · Year</div>
</div>
```

Use generic class names — not tied to any course product.

If a `themes-*.md` file exists for the selected theme, read it before building
theme-specific slides.

### Mermaid + theme change

```html
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  async function renderMermaid() { /* themeVariables per data-theme */ mermaid.initialize({...}); await mermaid.run(); }
  document.addEventListener('DOMContentLoaded', async () => {
    await renderMermaid();
    new SlideEngine();
    document.documentElement.addEventListener('premium-theme-change', renderMermaid);
  });
</script>
```

---

## SlideEngine

Prefer `assets/shared/slide-engine.js`:

```javascript
document.addEventListener('DOMContentLoaded', () => new SlideEngine());
```

`SlideEngine` builds progress bar, dots, counter, hints; handles keyboard, touch, `IntersectionObserver` for `.visible` / `.reveal`.

---

## File naming (this repo)

| Pattern | Example |
|---------|---------|
| Deck folder | `assets/decks/{slug}/` |
| HTML | `{slug}-slides.html` |
| Spec (8+ slides) | `{slug}-slide-spec.md` |

For deck anti-patterns (framework choices, branding, motion), see
[design.md](design.md).
