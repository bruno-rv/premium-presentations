# Red Presentation Theme

The Red theme is the framework's clean white-ground identity for broadcast-style and operational decks.

## Theme

| Theme | `data-theme` | Use for |
|-------|--------------|---------|
| **Red** | `red` | White-ground decks with sharp red accents, silver UI surfaces, and Barlow typography |

## Tokens

| Token | Value | Notes |
|-------|-------|-------|
| Accent red | `#FF0230` | Header accents, progress, highlights |
| Text | `#1A1A1A` | Body copy on white |
| Surface | `#F5F5F7` | Panels and metadata blocks |
| Silver | `#B8BEC6` / `#6B7280` | Secondary UI and muted labels |

## Typography

| Role | Font |
|------|------|
| Display | Barlow Condensed |
| Body | Barlow |
| Mono | IBM Plex Mono |

## Visual Patterns

| Pattern | Class / component |
|---------|-------------------|
| Red header bar + mark | `premium-red-chrome.js`, `premium-red-brand.css` |
| Red mark SVG | `assets/shared/assets/red-mark.svg` |
| Title accent | `.shimmer-gold` renders as flat `var(--accent)` |
| Focus Frame | `.focus-frame` |
| Mermaid | White canvas, red border |

### Red Chrome Attributes

| Attribute | Effect |
|-----------|--------|
| `data-red-hero="on"` | Large red mark on `.slide--title` |
| `data-red-chrome="off"` | Hide top bar |
| `data-red-bar-right="Q2 2026"` | Right label on bar |
| `data-red-bar-mark="off"` | Hide the mark in the bar |

## Scaffold

```bash
./scripts/new-deck.sh red my-deck "Deck Title" 12
```

Template: `assets/templates/red-base.html`.

## Switch at runtime

Theme control -> **Red**, or `PremiumPresentations.setTheme('red')`.
