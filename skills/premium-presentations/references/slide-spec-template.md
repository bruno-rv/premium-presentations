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

**Anchor phrase:** "{One sentence that burns the core idea — repeated verbatim twice in the deck, once early, once at close.}"

---

## Content-First Brief

**Complete this section before touching the Slide Map. Component selection is invalid without it.**

| Field | Answer |
|-------|--------|
| **Topic archetype** | abstract concept / tangible process / data story / historical narrative / debate — pick one |
| **Hero moment** | The one slide the audience must carry out. What is the insight? Which component surfaces it best? |
| **Audience's wrong assumption at entry** | What do they think they know that this deck corrects? Drives the opening hook angle. |
| **Exclusion list** | 2–3 components that would feel forced or generic on this topic. Do not use them. |
| **Narrative arc type** | linear progression / before→after shift / exploration→synthesis / problem→solution — pick one |

**Novel component rule:** If the hero moment requires a visual that no catalog pattern covers, invent one. Name it (e.g., `ReAct-Loop-Wheel`), describe its structure in Design Directives > Signature visual, and flag it for catalog addition after review. Forcing a poor-fit catalog pattern is worse than adding a new one.

---

## Narrative Arc

Derive acts from the topic's natural phases — not from a generic "intro → body → conclusion" template.

| Act | Title | Time range | What the audience experiences |
|-----|-------|------------|-------------------------------|
| 0 | Hook | 00:00–{N}:{N} | {Opening emotion / wrong assumption challenged} |
| 1 | {Act name} | {N}:{N}–{N}:{N} | {What shifts in the audience's mental model} |
| 2 | {Act name} | {N}:{N}–{N}:{N} | … |
| … | … | … | … |
| N | Close | {N}:{N}–end | {Anchor phrase repeated; call to action or takeaway} |

Divider slides mark act boundaries. Acts must reflect the topic's content phases, not template slots.

---

## Overlap Avoidance

| Already covered | Where | This lesson differs |
|-----------------|-------|---------------------|
| {concept} | {AL-x} | {one-line boundary} |

**Key rule:** {Trailer vs deep-dive rule for this lesson.}

---

## Slide Map

| # | ID | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes |
|---|----|-----|------|-------|-------------|----------------|-----------|----------------|---------------|
| 1 | slide-1 | 0 | Title | … | … | slide--title | N/A | "{First words the presenter says}" | … |
| 2 | slide-2 | 0 | Hook Quote | … | … | slide--quote | N/A | "{Delivery cue for the quote}" | … |
| 3 | slide-3 | 1 | Content | … | … | FLOW+ live-flow \| PIPE pipeline-vertical \| P9 compare-paradigm \| P14 journey \| TL timeline \| STG stage-card \| GL glass-code \| TERM terminal \| BAR bar-chart \| FLOW setup-flow \| STAT stats-row \| CHK checklist \| kpi-row \| content-grid+aside-card \| data-table | "{Why this matters}" | "{What the presenter says — not a repeat of slide text}" | … |
| … | … | … | … | … | … | … | … | … | … |
| N | slide-N | N | Closing Quote | … | … | slide--quote | N/A | "{Anchor phrase delivery}" | … |

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

### Color semantics budget

Assign each accent color a semantic role for this deck only. Every use of that color in the deck must carry that meaning — no decorative reuse.

| Color token | Semantic role in this deck |
|-------------|---------------------------|
| `var(--accent)` / blue | {e.g., "current state / active path"} |
| `var(--gold)` | {e.g., "success / resolution / anchor phrase"} |
| `var(--danger)` / red | {e.g., "failure mode / anti-pattern / warning"} |
| `var(--green)` | {e.g., "correct exit / validated state"} |

Omit rows that this deck does not use. Adding colors not in this budget requires a justification comment in the HTML.

### Signature visual (HERO slide)

{Pick from [components.md](components.md): FLOW+ live-flow, P14 journey-path, P9 compare-paradigm, DIV+ act divider, TL timeline, STG stage-card, GL glass-code-window, PIPE pipeline-vertical, TERM terminal-window, BAR bar-chart, FLOW setup-flow. Copy markup from `assets/templates/components/*.snippet.html`.}

### Tone

{Energy level: trailer / tutorial / live demo.}

---

*Spec format: premium-presentations compatible*
