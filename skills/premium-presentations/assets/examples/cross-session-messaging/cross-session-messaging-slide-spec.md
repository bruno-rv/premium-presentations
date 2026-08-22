# CROSS SESSION MESSAGING — Slide Generation Spec

> Read BEFORE generating `cross-session-messaging-slides.html`.

---

## Lesson Metadata

| Field | Value |
|-------|-------|
| **Code** | CROSS SESSION MESSAGING |
| **Title** | Cross-Session Messaging |
| **Title (Split)** | Line 1: "Cross-Session" / Line 2: "Messaging" (shimmer on line 2) |
| **Subtitle** | Claude Code · coordination between independent sessions |
| **Module** | 02 — Session coordination |
| **Duration** | 15 min |
| **Instructor** | Bruno Rodrigues Veloso |
| **Layer** | 2 — Applied AI engineering |
| **Mode** | Live |
| **Hook** | "A message can cross sessions. Context does not." |
| **Closing** | "Use messaging to coordinate; keep context and trust boundaries explicit." |

---

## Teaching Objective

The learner can explain what Claude Code cross-session messaging transports, how
local and remote delivery differ, and which controls protect the trust boundary.
The tone is precise and operational: this is a coordination channel between
independent sessions, not a shared memory system.

**Anchor phrase:** "A message can cross sessions. Context does not."

---

## Content-First Brief

**Complete this section before touching the Slide Map. Component selection is invalid without it.**

| Field | Answer |
|-------|--------|
| **Topic archetype** | tangible process |
| **Hero moment** | The transport diagram makes the boundary visible: discovery and delivery move text between sessions, while files, history, permissions, and context stay put. Use a two-lane custom SVG map. |
| **Audience's wrong assumption at entry** | A second Claude Code session is not automatically another worker with shared context. It is an independent peer that can exchange plain-text messages. |
| **Exclusion list** | RAG/vector-search patterns, agent-team internals, and persistent memory/database architecture. They are adjacent systems, not documented capabilities of this feature. |
| **Narrative arc type** | problem→solution |

**Novel component rule:** If the hero moment requires a visual that no catalog pattern covers, invent one. Name it (e.g., `ReAct-Loop-Wheel`), describe its structure in Design Directives > Signature visual, and flag it for catalog addition after review. Forcing a poor-fit catalog pattern is worse than adding a new one.

---

## Narrative Arc

Derive acts from the topic's natural phases — not from a generic "intro → body → conclusion" template.

| Act | Title | Time range | What the audience experiences |
|-----|-------|------------|-------------------------------|
| 0 | Hook | 00:00–01:30 | A short message is useful only when the boundary is explicit. |
| 1 | The boundary | 01:30–04:30 | A peer session is independent; only the message crosses. |
| 2 | The transport | 04:30–08:30 | Local sockets and Remote Control are different delivery paths. |
| 3 | The controls | 08:30–12:30 | Delivery can be accepted, held, or refused without bypassing permissions. |
| N | Close | 12:30–15:00 | Repeat the anchor phrase and turn it into a coordination rule. |

Divider slides mark act boundaries. Acts must reflect the topic's content phases, not template slots.

---

## Overlap Avoidance

| Already covered | Where | This lesson differs |
|-----------------|-------|---------------------|
| RAG / vector databases | Existing RAG example | This deck covers live coordination, not retrieval or persistent knowledge. |
| Subagents / agent teams | Claude Code agent workflows | This deck covers independent peer sessions and their message channel. |

**Key rule:** stay on the documented boundary. Show what a message does and
does not carry; do not imply shared files, shared history, semantic search, or
automatic context synchronization.

---

## Slide Map

| # | ID | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes | Budget (mm:ss) | Budget (ms) |
|---|----|-----|------|-------|-------------|----------------|-----------|----------------|---------------|----------------|-------------|
| 1 | slide-1 | 0 | Title | Opening | Cross-session messaging as a coordination channel | slide--title | N/A | "A second session can help — if we are precise about what crosses the boundary." | Set the scope: independent Claude Code sessions, not subagents or a shared memory store. Promise one operational model the audience can use immediately. |  |  |
| 2 | slide-2 | 0 | Hook Quote | Boundary | The anchor phrase: a message crosses, context does not | slide--quote | N/A | "A message can cross sessions. Context does not." | Read the anchor twice, with a pause between the two clauses. Use it as the test for every diagram that follows. |  |  |
| 3 | slide-3 | 1 | Content | A peer, not a subagent | Independent session, plain-text message, no automatic history/files | STG stage-card | "Name the boundary before you use the channel." | Define the mental model before showing tools. The key word is independent. | Walk through the three terms on the card. Emphasize that the receiver gets a message and sender identity, not the sender's working tree or conversation. |  |  |
| 4 | slide-4 | 1 | Divider | Act 1 — The boundary | What can cross? | DIV+ divider-act | N/A | "First, separate the message from the context around it." | Take a breath and preview the boundary test. |  |  |
| 5 | slide-5 | 1 | Content | Message ≠ context transfer | SendMessage carries text; it does not move conversation history, files, or permissions | P9 compare-paradigm | "The payload is small by design." | Contrast the payload with the missing context. | Point to the left column first, then the right. Make the absence explicit: no file transfer, no history transfer, no permission approval. |  |  |
| 6 | slide-6 | 2 | Content | Find, send, receive | ListAgents discovers peers; SendMessage delivers a plain-text message | FLOW+ live-flow | "Discovery and delivery are separate steps." | Narrate the handoff as a four-node loop. | Let the animated phase label lead. Pause on ListAgents and SendMessage: they solve different problems. |  |  |
| 7 | slide-7 | 2 | Content | Three truths to hold | Text only, no hidden context, normal approvals remain | STAT stats-row + WHY | "Coordination gets lighter; trust boundaries stay intact." | Let the three constraints land before discussing transports. | Read each card as a guardrail, not a limitation to work around. The system does not let an inbound message approve permissions or run slash commands. |  |  |
| 8 | slide-8 | 2 | Divider | Act 2 — The transport | Local socket or Remote Control? | DIV+ divider-act | N/A | "The route changes when the peer leaves this machine." | Mark the shift from semantics to transport. Preview the same-machine and remote cases. |  |  |
| 9 | slide-9 | 2 | Content | Same message, different route | Same-machine sockets vs Remote Control through Anthropic servers; remote/web sessions are reply-only | data-table | "Transport is part of the trust model." | Compare the three documented environments. | Use the table row by row. Call out the reply-only edge case so nobody designs a one-way workflow that cannot start. |  |  |
| 10 | slide-10 | 3 | Content | Delivery has three states | Accept, hold for approval, or refuse via crossSessionInbound | PIPE pipeline-vertical | "A message can arrive without becoming trusted action." | Follow the policy path top to bottom. | The receiving session remains in control. Connect hold/refuse to the team's operating policy, not to prompt engineering. |  |  |
| 11 | slide-11 | 3 | Content | What actually travels | A two-lane transport diagram with local inbox sockets and the Remote Control path | slide--diagram (custom SVG) | "The message is the bridge; the contexts stay on their own islands." | Trace one local and one remote path. | Let the diagram render. Point out what is deliberately absent: shared vector store, shared files, and synchronized conversation history. |  |  |
| 12 | slide-12 | 3 | Divider | Act 3 — The controls | Make the boundary explicit | DIV+ divider-act | N/A | "Now turn the model into an operating rule." | Transition from architecture to configuration. Tell the audience the final slide is about safe defaults, not feature discovery. |  |  |
| 13 | slide-13 | 3 | Content | Guard the boundary | crossSessionInbound, isolatePeerMachines, and organization-wide tool denial | GL glass-code | "The safest channel is the one whose edges are intentional." | Show a restrictive configuration posture and support prerequisites. | Zoom into the two controls. Explain that denying ListAgents/SendMessage disables the feature, while isolatePeerMachines requires approval before leaving the machine. |  |  |
| 14 | slide-14 | 3 | Closing Quote | Closing | Coordination without context confusion | slide--quote | N/A | "A message can cross sessions. Context does not." | Repeat the anchor phrase verbatim. Close with the source URL and the practical next step: decide which peers may talk, which messages require approval, and what context must be carried explicitly. |  |  |

**Visual Pattern rule:** every Content row names one concrete pattern from the
routing table in [components.md](components.md) — never leave it generic and
never plan a bare heading + paragraph slide. Vary patterns: ≥5 distinct ones
in a 12+ slide deck, no pattern on more than 2 consecutive slides.

**Speaker Notes rule:** every slide row carries a Speaker Notes entry, and
the generation skill renders each entry as `<aside class="notes">…</aside>`
as the last child inside the `.slide` section. Notes **explain — they never
direct**. Each entry is a concise, plain-language explanation of every
concept displayed on the slide: what it is, why it exists, how it behaves —
the answer to "explain this clearly," not stage directions. No delivery or
staging cues, no slide narration or orientation, no unexplained jargon; one
idea per sentence, typically 3–6 sentences (fewer on title, quote, and
divider slides). Full rule: `references/slide-spec-template.md`.

**Slide Budget columns (optional, Tier 2):** `Budget (mm:ss)` / `Budget (ms)`
declare the planned dwell time for each slide (the *Slide Budget*, per
CONTEXT.md — not to be confused with the *Color semantics budget* under
Design Directives below, which is a visual-design constraint with nothing to
do with time; never shorten either term to plain "budget"). The atomic
header pair has exactly three valid column states, enforced by
`validate_deck.py`/`deck_doctor.py`:

1. **Budgetless** — both columns absent, or both present with every cell
   empty. No gate, no runtime budgets; the presenter popup falls back to its
   "vs average" comparison.
2. **Budgeted** — both columns present and every row populated with a valid
   value. `Budget (ms)` is authoritative: a decimal integer with no sign or
   whitespace, minimum `1000` (sub-second budgets rejected), maximum
   `7200000` (2h/slide), within JS safe-integer range. `Budget (mm:ss)` is
   the derived display and must equal `floor(ms/1000)` rendered zero-padded
   (`^\d{2,}:[0-5]\d$`) — e.g. `50000` ms ↔ `00:50`.
3. **Anything else** (one column present without the other, only some rows
   populated, or any invalid/mismatched value) is a **validation failure** —
   the doctor exits non-zero.

`spec_generator.py` scaffolds both headers with empty cells (budgetless by
default); filling them in is an authoring step. When a spec is budgeted, the
generation skill emits `data-budget="<ms>"` — the verbatim `Budget (ms)`
value — on the matching `<section class="slide" id="…">` for every slide
(see SKILL.md's HTML-emit contract). No Python script emits `data-budget`;
`spec_generator.py` only scaffolds the two empty columns.

---

## Glossary (optional)

If the deck introduces domain terms that benefit from hover definitions, list them here. The generator will emit a `<script type="application/json" id="glossary">` block and wrap in-text mentions with `.term-link` buttons. Omit this section if the deck does not need term popups.

| Key | Title | Body |
|-----|-------|------|
| `ListAgents` | Peer discovery | Lists independent Claude Code sessions that can receive messages. |
| `SendMessage` | Cross-session delivery | Sends a plain-text message to another session. |
| `crossSessionInbound` | Inbound policy | Controls whether incoming messages are accepted, held, or refused. |
| `isolatePeerMachines` | Machine boundary | Requires approval before messages leave the current machine. |
| `Remote Control` | Remote transport | The path used for sessions on other machines or Claude Code on the web. |

---

## Evidence Data

Source: [Claude Code — Message your other Claude Code sessions](https://code.claude.com/docs/en/cross-session-messaging), checked 2026-08-08; page metadata reports a 2026-08-07 modification.

| Claim | Evidence used |
|-------|--------------|
| The feature coordinates independent sessions with plain-text messages. | The source distinguishes independent sessions from subagents/agent-team teammates and documents cross-session messaging. |
| Discovery and delivery are separate tools. | `ListAgents` discovers peers; `SendMessage` delivers messages; `/list-agents` and `/peers` expose discovery. |
| Local and remote transport differ. | Same-machine sessions use per-session inbox sockets; other machines and web sessions use Remote Control through Anthropic servers. |
| Remote/web sessions are reply-only. | A local session cannot initiate a new exchange with a cross-machine or web session. |
| The receiving side remains in control. | Inbound messages can be accepted, held, or refused; messages cannot approve permissions, change configuration, or execute slash commands. |
| The feature is bounded by explicit controls. | `crossSessionInbound`, `isolatePeerMachines`, and denying `ListAgents`/`SendMessage` are documented controls. |
| Support is version/platform gated. | The source lists Claude Code v2.1.224+, macOS or Linux including WSL2, and unsupported native Windows/cloud cases. |

Interpretation boundary: the source does not describe RAG, embeddings, vector
databases, graph traversal, or persistent knowledge storage. The deck must not
present cross-session messaging as any of those systems.

---

## Design Directives

### Palette

No theme overrides. Use the editorial theme tokens: blue for active delivery,
gold for the trust boundary, green for accepted, and red for blocked/refused.

### Color semantics budget

Assign each accent color a semantic role for this deck only. Every use of that color in the deck must carry that meaning — no decorative reuse.

| Color token | Semantic role in this deck |
|-------------|---------------------------|
| `var(--accent)` / blue | active peer discovery and delivery path |
| `var(--gold)` | explicit boundary and anchor phrase |
| `var(--red)` | refused delivery or unsupported path |
| `var(--green)` | accepted / delivered state |

Omit rows that this deck does not use. Adding colors not in this budget requires a justification comment in the HTML.

### Signature visual (HERO slide)

The hero visual is the two-lane transport map on slide 11, supported by the
FLOW+ discovery/delivery loop on slide 6. Both show the same boundary at
different zoom levels.

### Tone

Tutorial with a live-ops edge: short definitions, one transport map, and a
closing configuration decision.

---

*Spec format: premium-presentations compatible*
