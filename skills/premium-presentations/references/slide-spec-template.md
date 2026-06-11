# {CODE} — Slide Generation Spec

> Read BEFORE generating `{code}-slides.html`.

---

## Lesson Metadata

| Field | Value |
|-------|-------|
| **Code** | {CODE} |
| **Title** | {Full title} |
| **Title (Split)** | Line 1: "…" / Line 2: "…" (shimmer on line 2) |
| **Subtitle** | {One line under title} |
| **Module** | {NN — Module name} |
| **Duration** | {N} min |
| **Instructor** | {Name} |
| **Layer** | {N — Layer name} |
| **Mode** | Self-Paced \| Live |
| **Hook** | "{Opening quote — emotional promise}" |
| **Closing** | "{Closing takeaway}" |

---

## Teaching Objective

{What the learner must feel/know when done. Tone and pacing. Seconds per slide if short lesson.}

---

## Overlap Avoidance

| Already covered | Where | This lesson differs |
|-----------------|-------|---------------------|
| {concept} | {AL-x} | {one-line boundary} |

**Key rule:** {Trailer vs deep-dive rule for this lesson.}

---

## Slide Map

| # | Type | Title | Key Content | Visual Pattern | Why Panel | Speaker Notes |
|---|------|-------|-------------|----------------|-----------|---------------|
| 1 | Title | … | … | slide--title | N/A | … |
| 2 | Hook Quote | … | … | slide--quote | N/A | … |
| 3 | Content | … | … | FLOW+ live-flow \| PIPE pipeline-vertical \| P9 compare-paradigm \| P14 journey \| TL timeline \| STG stage-card \| GL glass-code \| TERM terminal \| BAR bar-chart \| FLOW setup-flow \| STAT stats-row \| CHK checklist \| kpi-row \| content-grid+aside-card \| data-table | "{Why this matters}" | … |
| … | … | … | … | … | … | … |
| N | Closing Quote | … | … | slide--quote | N/A | … |

**Visual Pattern rule:** every Content row names one concrete pattern from the
routing table in [components.md](components.md) — never leave it generic and
never plan a bare heading + paragraph slide. Vary patterns: ≥5 distinct ones
in a 12+ slide deck, no pattern on more than 2 consecutive slides.

**Speaker Notes rule:** every slide row carries a Speaker Notes entry — 2–4
sentences of what the presenter says aloud (delivery cues, transitions, the
"why" behind the slide). Notes are distinct from on-slide text; they describe
pacing, emphasis, or context the audience never reads. The generation skill
renders each entry as `<aside class="notes">…</aside>` as the last child
inside the `.slide` section.

---

## Glossary (optional)

If the deck introduces domain terms that benefit from hover definitions, list them here. The generator will emit a `<script type="application/json" id="glossary">` block and wrap in-text mentions with `.term-link` buttons. Omit this section if the deck does not need term popups.

| Key | Title | Body |
|-----|-------|------|
| {TERM} | {Full name or expansion} | {One-sentence definition.} |

---

## Evidence Data

{Tables, quotes, stats, quotes with attribution — facts the slides must use.}

---

## Design Directives

### Palette

{MANDATORY token overrides if the selected theme requires deck-specific additions beyond shared theme tokens.}

### Signature visual (HERO slide)

{Pick from [components.md](components.md): FLOW+ live-flow, P14 journey-path, P9 compare-paradigm, DIV+ act divider, TL timeline, STG stage-card, GL glass-code-window, PIPE pipeline-vertical, TERM terminal-window, BAR bar-chart, FLOW setup-flow. Copy markup from `assets/templates/components/*.snippet.html`.}

### Tone

{Energy level: trailer / tutorial / live demo.}

---

*Spec format: premium-presentations compatible*
