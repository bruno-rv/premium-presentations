# Design Principles

Use these principles when creating or revising Premium Presentations decks.

## Content-First Rule

**Before drafting the Slide Map, complete the Content-First Brief in the spec.** This is not optional.

The routing table in `components.md` (content-type → component) is a tool, not a starting point. It fires only after the narrative arc, hero moment, audience assumption, exclusion list, and arc type are locked. Skipping the brief produces structurally identical decks regardless of topic — the same skeleton in different clothes.

Checklist before opening the Slide Map:

- [ ] Topic archetype named (abstract concept / process / data story / historical / debate)
- [ ] Hero moment identified — the one slide the audience must carry out, and which component best surfaces it
- [ ] Audience's wrong assumption at entry written out
- [ ] Exclusion list set — 2–3 components that would feel forced on this topic
- [ ] Narrative arc type chosen — acts reflect the topic's content phases, not the default "intro → body → conclusion" rhythm
- [ ] Color semantics budget set — each accent color has one semantic role for this deck

---

## Audience

Presentation authors and technical speakers use this skill to build polished
HTML slide decks that open directly, bundle for sharing, and support live
presentation controls. The audience usually watches projected or screen-shared
slides, so clarity at room distance matters more than app-like density.

## Product Purpose

Premium Presentations provides reusable HTML deck templates, shared theme
tokens, controls, annotations, presenter tools, and bundling scripts. A strong
deck feels deliberate at thumbnail size, readable in a live room, and robust
enough to present without local setup friction.

## Style

Editorial, technical, high-polish.

## Avoid

- Generic SaaS deck templates.
- Text-heavy conference slides.
- Decorative chrome that competes with the idea.
- Nested card grids.
- Low-contrast muted text.
- AI-default palettes that make unrelated decks feel interchangeable.
- Reveal.js / Slidev or other external slide frameworks — use the bundled
  SlideEngine runtime.
- Fragment stepping libraries — use `.reveal` stagger only.
- Multiple ideas per slide.
- Bare heading + paragraph slides (title/quote/divider exempt).
- Sparse single-component slides — one-sentence preamble floating over one
  stats block reads as an empty box.
- Missing `prefers-reduced-motion` support (provided by `premium-deck.css`).
- Course-specific branding unless explicitly requested.
- Closing footer-note rows, "NEXT:" citations, or lesson-pill rows.
- Sparse `compare-split` panels (badge+title+one line only). `compare-split`
  is `flex:1; align-items:stretch` by design — it stretches to fill the
  slide's remaining height regardless of content, so thin panels read as
  dead space, and a `.compare-callout` gets pinned to the stretched bottom
  edge where it can collide with fixed chrome. Fill each panel with a
  3–5 item `<ul>` of concrete facts, or add `style="flex:none"` on
  `.compare-split` to size it to its own content instead. `deck_doctor.py`
  warns on this; fix before delivery.
- Decorative shapes with no text and no recognizable connective structure
  (bordered rects/bars standing in for "text lines," floating unlabeled
  boxes). They read as broken/empty UI, not deliberate design. A visual
  element must either carry real visible text/labels, form a recognizable
  connected diagram (nodes + lines), or be removed in favor of a
  single-column content slide.

## Density

- Every content slide has a visual anchor from the routing table in
  [components.md](components.md) — never a heading plus one paragraph in
  empty space.
- Per-slide limits: content 5–6 bullets max; stats/dashboard 3–6 KPIs;
  table ≤8 rows; flow/pipeline 3–6 nodes.
- Variety: a 12+ slide deck uses ≥5 distinct visual patterns, and no
  pattern repeats on more than 2 consecutive slides.

## Principles

- One slide, one dominant read.
- Theme choices should change mood without breaking the shared layout grammar.
- Controls and presentation chrome should support the speaker, then disappear
  for the audience.
- Visual systems should be distinctive at contact-sheet scale.
- Proof objects, diagrams, and readable labels beat paragraphs.
- Aim for WCAG AA contrast, visible focus states, keyboard operability,
  reduced-motion support, and slide text large enough for projection.
