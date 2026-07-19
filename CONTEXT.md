# CONTEXT — Ubiquitous Language

Glossary only. No implementation details.

## Terms

**Slide Budget** — The planned dwell time for a single slide, expressed in the Slide Map as `Budget (mm:ss)` (human display) and `Budget (ms)` (authoritative machine value). A deck either budgets every slide or none ("all-or-nothing"). Distinct from *Color semantics budget*.

**Color semantics budget** — The cap on accent-color usage declared in a spec's Design Directives. A visual-design constraint; has nothing to do with time. Never shorten either term to plain "budget" in specs or UI copy.

**Delta vs plan / Delta vs average** — Rehearsal-coach comparison semantics. "vs plan" is only claimed when the deck carries Slide Budgets; otherwise the comparison is "vs average" (total time ÷ slide count). The two are never mixed within one deck.

**Timed scroll** — Teleprompter mode in which the scroll rate is derived from the current slide's Slide Budget rather than a manual constant. Engages automatically when a deck carries Slide Budgets; decks without budgets keep manual scroll.

**Recipe** — A slash command (e.g. `/present-pr`) that maps a real source artifact (diff, codebase, incident doc) into a filled Brief and then runs the standard deck pipeline unchanged. Recipes never invent facts and never bypass the validation gate.

**Brief** — A recipe-specific Content-First Brief template (under `references/`) whose fields map the recipe's source artifact onto the standard spec sections (Narrative Arc, Slide Map, Evidence Data).
