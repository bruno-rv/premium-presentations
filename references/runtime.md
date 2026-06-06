# Premium Presentations — Reference

## Contents

- Shared runtime
- Diagram slides
- Theme discovery, visuals, and chrome
- Theme extension pattern
- Mermaid and theme changes
- SlideEngine
- File naming
- Anti-patterns

## Shared runtime (`shared/`)

| File | Role |
|------|------|
| `premium-themes.css` | `html[data-theme="..."]` CSS variables; source of truth for discovered themes |
| `premium-deck.css` | Slide layout, typography, tables, KPIs |
| `premium-components.css` | Creative blocks: shimmer, compare-split, timeline, glass/code, journey SVG, bars, setup-flow — see [components.md](components.md) |
| `premium-controls.js` | Theme `<select>`, theme visual injection, 3D background, curtain, timer/PDF controls |
| `premium-controller.js` | Shared deck state, navigation API, and presenter/clicker event bridge |
| `premium-diagrams.css` | Diagram slide layout + Excalidraw-style canvas |
| `premium-mermaid.js` | Mermaid `handDrawn` theme + auto-fit + clip detection + theme re-render |

### Diagram slides (required markup)

Use `templates/diagram-slide.snippet.html`. Validator enforces:

- `slide--diagram` → `slide__diagram-header` → `diagram-stage` → `mermaid-wrap` → `<pre class="mermaid">`
- `premium-diagrams.css` + `premium-mermaid.js` (inlined when bundled)
- No `max-height: 52vh|62vh` on `.mermaid-wrap` (clips content)
- Runtime: `fitMermaidDiagrams`, `bindMermaidFit`, `bindDiagramZoom`, `reportDiagramFit`
- **Diagram zoom:** scroll/pinch on canvas, drag to pan when zoomed, toolbar **+ / − / %**, double-click reset; **`+` `−` `0`** on diagram slides
| `slide-engine.js` | `SlideEngine` — scroll-snap nav; dot labels from heading, blockquote, cite, `data-nav-title`, etc.; auto-hide after 5s (click dot rail to show again; hover still peeks) |

Decks link with `../../shared/…` from `decks/<slug>/`.

**Theme discovery:** run `./scripts/list-themes.py`, or inspect `html[data-theme="..."]` selectors in `shared/premium-themes.css`. Do not hardcode the current theme names in generators or skill instructions.

**Runtime contract:** run `./scripts/validate-runtime-contract.py` after any
template, theme, bundler, or shared runtime edit. It verifies discovered theme
scaffold templates, preview templates, and generated deck HTML files carry the
common CSS/JS stack, plus red brand modules where the active template/deck is
red.

**Live theme switch:** `PremiumPresentations.setTheme('<theme>')` or UI control. The control panel discovers themes from loaded CSS. Dispatches `premium-theme-change` on `<html>`.

**Theme visuals:** `.slide--title` receives a `hero` visual; `.slide--divider` receives a `map` visual. Default assets follow `shared/assets/chatgpt-theme-visuals/<theme>-<role>.png`. Override with `data-theme-visual-<theme>-<role>` or `window.PremiumThemeVisuals`; disable per slide with `data-theme-visual="off"`.

**3D background:** `PremiumPresentations.setParallax(true)` or UI button / **`3`**; sets `data-parallax="on"`. Disabled when `prefers-reduced-motion`.

**Panel:** **`H`** hide/show; unhide pins panel open (`is-open`). **`3`** toggles parallax.

## Theme Extension Pattern

To add a theme:

1. Add `html[data-theme="<theme>"]` tokens in `shared/premium-themes.css`.
2. Optionally add `templates/<theme>-base.html` for theme-specific chrome.
3. Optionally add visuals in `shared/assets/chatgpt-theme-visuals/` using
   `<theme>-hero.png` and `<theme>-map.png`.
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

Prefer `shared/slide-engine.js`:

```javascript
document.addEventListener('DOMContentLoaded', () => new SlideEngine());
```

`SlideEngine` builds progress bar, dots, counter, hints; handles keyboard, touch, `IntersectionObserver` for `.visible` / `.reveal`.

---

## File naming (this repo)

| Pattern | Example |
|---------|---------|
| Deck folder | `decks/{slug}/` |
| HTML | `{slug}-slides.html` |
| Spec (8+ slides) | `{slug}-slide-spec.md` |

---

## Anti-patterns

- Reveal.js / Slidev
- Multiple ideas per slide
- Missing `prefers-reduced-motion` (in `premium-deck.css`)
- Course-specific branding unless explicitly requested
- Fragment stepping libraries (use `.reveal` stagger only)
