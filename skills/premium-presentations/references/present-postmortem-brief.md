# {TITLE} — Blameless Postmortem Brief

> Recipe-specific Content-First Brief for `/present-postmortem`. Mirrors the
> mandatory brief in `SKILL.md` / `slide-spec-template.md`, with
> postmortem-appropriate field mappings so the generated spec ships 0
> placeholder strings. Fill every `{…}` field from the user-supplied incident
> doc and, only if explicitly requested, opt-in git/CI corroboration — never
> from assumption. **Document-only by default.**

---

## Argument contract

```text
/present-postmortem <incident-file> [--git-range <ref>..<ref>] [--ci-log <file>] [--keep-identifiers]
```

`<incident-file>` is **required** — a missing argument is a loud failure, not
a silent no-op. Validate it (and `--ci-log`, when given) with
`recipe_source_guard.py validate-file`: the path must resolve (symlinks
followed, then the resolved target re-checked and rejected if non-regular),
be readable, be ≤ 10 MB, and decode as UTF-8 text. `--git-range` endpoints are
**never** used as raw refs — each side is resolved to a verified commit SHA
via `recipe_source_guard.py resolve-ref` (which wraps `git rev-parse
--verify` and rejects option-like refs) before any git command touches them.

Corroboration (`--git-range`, `--ci-log`) is **opt-in only**. Absent those
flags, the deck is built from the incident doc alone.

---

## Lesson Metadata (postmortem mapping)

| Field | Source | Value |
|-------|--------|-------|
| **Code / Title** | the incident's title/ID from the doc | {TITLE} |
| **Duration** | estimated from slide count (~1 min/slide) | {N} min |
| **Instructor** | omit — dropped for this recipe (avoids naming an individual) | — |
| **Module** | omit — dropped for this recipe, not a placeholder | — |
| **Layer** | omit — dropped for this recipe, not a placeholder | — |
| **Hook** | the moment the incident was first noticed/declared | "{HOOK}" |
| **Closing** | the lesson the team carries forward | "{CLOSING}" |

---

## Content-First Brief

| Field | Answer |
|-------|--------|
| **Topic archetype** | tangible process (fixed for this recipe) |
| **Hero moment** | the root-cause reveal — the single fact that reframes the whole incident |
| **Audience's wrong assumption at entry** | what the team believed was true before the root cause was found |
| **Exclusion list** | data-story components not grounded in the incident doc's own numbers |
| **Narrative arc type** | before → after shift (fixed for this recipe) |

---

## Provenance & precedence

Only sources actually supplied are ranked: **incident doc > git > CI log.**
Corroborating sources may **confirm** a claim from the incident doc, or be
**cited as an explicit conflict** ("the incident doc states X; the git range
shows Y") — they never silently override the doc. A corroboration source that
cannot be validated or resolved is dropped with a note, not treated as a
build failure, unless the incident doc itself is invalid (loud failure).

---

## PII minimization (default) and credential redaction

**Default: PII-minimized, internal-audience deck.** `recipe_source_guard.py`
redacts, on every source it touches:

- Credentials: AWS keys, `ghp_`/`gho_` tokens, private-key blocks, bearer
  tokens, connection-string passwords.
- PII: labeled person names (`Reporter:`, `Engineer:`, `Customer:`, etc.),
  email addresses, phone numbers, IP addresses, and labeled customer/tenant/
  account identifiers — replaced with role labels ("on-call engineer") or
  generic pseudonyms ("Customer A").

`--keep-identifiers` is an **explicit opt-in** to retain direct identifiers;
absent that flag, every slide uses roles/pseudonyms, never real names. This
redaction is **best-effort pattern matching** — unlabeled or novel identifier
formats may still pass through; ambiguous cases need manual review or an
explicit user-supplied pseudonymization map (documented limitation, not
silently claimed as complete). The generated deck is marked
**internal-audience** by default regardless of `--keep-identifiers`.

---

## Fixed Arc (timeline → impact → root cause → remediation → lessons)

| Act | Title | What the audience experiences |
|-----|-------|-------------------------------|
| 0 | Hook | The moment the incident was noticed — blameless framing from slide one |
| 1 | Timeline | What happened, in order, with timestamps from the doc |
| 2 | Impact | Who/what was affected, in the doc's own terms (no invented severity) |
| 3 | Root Cause | The reframing fact — corroborated or flagged as conflicting when applicable |
| 4 | Remediation | What was fixed, and what is still open |
| 5 | Lessons | The takeaway the team carries forward |
| 6 | Close | Anchor phrase — the lesson, restated |

**Blameless tone rule:** every act names systems, processes, and decisions —
never a person as the cause. Individuals appear only as roles.

**"Not documented" rule:** any arc section without direct evidence in the
incident doc (or validated corroboration) renders as an explicit "Not
documented" line. Never invent a timestamp, impact number, or root cause.

---

## Slide Map

Populate using the same `# | ID | Act | Type | Title | Key Content | Visual
Pattern | Why Panel | Voiceover Beat | Speaker Notes` shape as
`slide-spec-template.md`. The Timeline act is the natural home for a `TL
timeline` pattern; Root Cause often pairs with `compare-paradigm` (before vs.
after understanding). Every row carries Speaker Notes.

---

## Evidence Data

Timeline entries, impact figures, and root-cause facts pulled verbatim (post-
redaction) from the incident doc, plus any corroborating git/CI evidence
explicitly cited as confirming or conflicting — no invented statistics.

---

*Recipe brief format: premium-presentations `/present-postmortem` — funnels
into the existing `new-deck.sh` → spec → generate → `deck_doctor.py` pipeline
verbatim. All source validation, corroboration-ref resolution, and redaction
are owned entirely by `recipe_source_guard.py`.*
