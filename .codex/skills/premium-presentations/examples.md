# Premium Presentations — Examples

Decks are **one standalone `.html` file** (engine inlined via `bundle-deck.sh`). Scaffold with `new-deck.sh`, then edit slides in place.

## Re-bundle after changing `shared/`

```bash
./scripts/bundle-deck.sh decks/my-talk/my-talk-slides.linked.html -o decks/my-talk/my-talk-slides.html
# or --in-place on a file that still has ../../shared/ links
```

## Mermaid diagram slide (content only — engine is already in the file)

Add diagram markup inside a bundled deck; re-bundle from a `.linked.html` source if you changed `shared/premium-mermaid.js`.

## Slide patterns

Minimal copy-paste patterns below. Layout CSS: `shared/premium-deck.css`. **Illustrative components** (journey, compare, timeline, code window): `shared/premium-components.css` + [components.md](components.md) + `templates/components/*.snippet.html`.

## Title slide

```html
<section class="slide slide--title">
  <div class="reveal"><p class="slide__subtitle">MÓDULO 01 — EXEMPLO</p></div>
  <h1 class="slide__display reveal">
    Título linha 1<br><span class="shimmer-gold">Linha 2</span>
  </h1>
  <p class="slide__body reveal" style="max-width:42rem;margin-top:1rem">
    Subtítulo editorial em uma frase.
  </p>
</section>
```

## Hook quote

```html
<section class="slide slide--quote">
  <div class="reveal"><div class="slide__quote-mark">&ldquo;</div></div>
  <div class="reveal">
    <blockquote>
      Frase de abertura com <strong style="color:var(--gold)">ênfase</strong>.
    </blockquote>
  </div>
  <div class="reveal"><cite>Luan Moreno</cite></div>
</section>
```

## Content slide + why panel

```html
<section class="slide">
  <p class="slide__label reveal">ATO 1 — CONTEXTO</p>
  <h2 class="slide__heading reveal">Uma ideia por slide</h2>
  <div class="content-center-wrap">
    <p class="slide__body reveal">Corpo editorial curto. Sem parágrafos longos.</p>
    <div class="reveal" style="margin-top:1.5rem">
      <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:.8rem 1.5rem">
        <p style="font-family:var(--font-display);font-style:italic;color:var(--gold)">Por que isso importa?</p>
        <p style="font-size:.88rem;color:var(--text-dim);line-height:1.5">
          Uma frase de implicação prática.
        </p>
      </div>
    </div>
  </div>
</section>
```

## Stat row

```html
<div class="stats-row reveal">
  <div class="stat-card">
    <div class="stat-val" style="color:var(--accent)">70h</div>
    <div class="stat-lbl">Duração</div>
  </div>
  <!-- repeat 3–4 cards -->
</div>
```

## Act divider

```html
<section class="slide slide--divider">
  <span class="slide__number reveal">02</span>
  <p class="slide__label reveal">ATO 2</p>
  <h2 class="slide__heading reveal">Nome do ato</h2>
</section>
```

## Closing quote

```html
<section class="slide slide--quote">
  <div class="reveal"><div class="slide__quote-mark" style="color:var(--gold)">&ldquo;</div></div>
  <div class="reveal"><blockquote>Frase de fechamento.</blockquote></div>
</section>
```

## Diagram slide (centered Excalidraw canvas)

```html
<section class="slide slide--diagram">
  <header class="slide__diagram-header">
    <p class="slide__label reveal">Pipeline</p>
    <h2 class="slide__heading reveal">Fluxo RAG</h2>
  </header>
  <div class="diagram-stage">
    <div class="mermaid-wrap reveal">
      <pre class="mermaid">
flowchart LR
  A[Ingest] --> B[Chunk] --> C[Embed] --> D[Retrieve]
      </pre>
    </div>
  </div>
</section>
```
