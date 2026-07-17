# Spec-aware Partial Regeneration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a provider-neutral, fail-closed CLI that lets Claude Code or Codex replace slides selected by edited Slide Map rows while preserving every untargeted slide byte-for-byte and keeping theme homage images embedded.

**Architecture:** `slide_spec.py` owns Markdown Slide Map identity and canonicalization, `slide_html.py` owns exact HTML section spans and fragment structure, and `partial_regen.py` owns embedded state, planning, transactions, backups, apply, and rollback. The implementation reuses the shared parser from `validate_deck.py`, validates every staged deck with Deck Doctor, and never invokes a model or provider API.

**Tech Stack:** Python 3.12 standard library (`argparse`, `dataclasses`, `hashlib`, `html.parser`, `json`, `os`, `pathlib`, `tempfile`, `unittest`), existing Node 18+ test runner, existing Playwright Chromium smoke tooling, Claude Code plugin validator, Codex plugin validator.

## Global Constraints

- Release 1 supports replacement of existing slides only; insertion, deletion, and reordering return exit code `2` and require full regeneration.
- Initialization stays explicit: `init` is read-only and only `init --apply` mutates the deck/spec pair.
- The CLI is provider-neutral, performs no model calls, and requires no Claude or OpenAI API key.
- Stable IDs match `[A-Za-z0-9_-]{1,128}`, are unique, appear in the Slide Map immediately after `#`, and are the section's real DOM `id`; do not add `data-slide-id`.
- Preserve a valid existing section ID at the same ordinal; otherwise generate `slide-N` with a 1-based ordinal. Reject conflicting, duplicate, malformed, or count-mismatched inputs.
- The deck and spec must be regular, non-symlink files in the same resolved directory.
- Embed one deterministic, non-executable JSON manifest with `id="premium-regen-state"` outside `#deck`; store basenames only and escape `<` as `\u003c`.
- Preserve all bytes outside replaced slide spans and the regenerated state block. Prove every untargeted slide hash remains unchanged.
- Require the fragment ID set to equal the complete planned change set. Each fragment contains exactly one slide section, the exact stable ID and decoded `data-nav-title`, no global tags or controls, and one direct final `aside.notes`.
- New conditional runtime capabilities or glossary keys require full regeneration. Existing runtime/theme assets, including embedded theme homage backgrounds, must remain unchanged and valid.
- Backups live beneath `DECK.parent/.partial-regen/backups/<UTC-timestamp>/`; metadata contains basenames and SHA-256 hashes only.
- Use exit code `0` for success/preview/no changes/rollback, `1` for invalid input/validation/I/O, `2` for full regeneration required, and `3` for baseline slide drift.
- A durable `prepared` transaction journal blocks every command except the matching rollback until recovery completes.
- Add no third-party dependency. Follow TDD and commit only the files named by each task; the worktree already contains unrelated user changes.
- For a modified file that was already dirty before this feature, stage only reviewed feature hunks with `git add -p`; if a hunk cannot be separated safely, leave it uncommitted and report it to the primary agent. Never stage an entire pre-dirty file.

---

## File and Interface Map

- `skills/premium-presentations/scripts/slide_spec.py`: parse, canonicalize, diff, and materialize stable IDs in Slide Map Markdown.
- `skills/premium-presentations/scripts/slide_html.py`: locate exact authored slide spans, assign IDs during initialization, validate fragments, and splice replacements.
- `skills/premium-presentations/scripts/partial_regen.py`: embedded state, plan results, CLI parsing, file safety, backups, journals, initialization, apply, and rollback.
- `skills/premium-presentations/scripts/validate_deck.py`: consume `parse_slide_map()` for spec row count so validator and CLI semantics cannot diverge.
- `skills/premium-presentations/scripts/spec_generator.py` and `skills/premium-presentations/references/slide-spec-template.md`: emit deterministic IDs for newly scaffolded specs.
- `skills/premium-presentations/scripts/tests/test_slide_spec.py`: legacy/current/new table parsing, canonicalization, diffing, and ID materialization.
- `skills/premium-presentations/scripts/tests/test_slide_html.py`: exact span parsing, safe fragment validation, ID assignment, and byte-preserving splices.
- `skills/premium-presentations/scripts/tests/test_partial_regen.py`: state, plan, init/apply transactions, failure injection, backups, and rollback.
- `skills/premium-presentations/scripts/tests/test_partial_regen_e2e.py`: public CLI round trip and browser-facing artifact assertions.
- `README.md`, `skills/premium-presentations/SKILL.md`, and `skills/premium-presentations/references/runtime.md`: identical Claude Code/Codex workflow and refusal guidance.

---

### Task 1: Shared Slide Map parser and deterministic IDs

**Files:**

- Create: `skills/premium-presentations/scripts/slide_spec.py`
- Create: `skills/premium-presentations/scripts/tests/test_slide_spec.py`
- Modify: `skills/premium-presentations/scripts/validate_deck.py` at the current Slide Map counting block
- Modify: `skills/premium-presentations/scripts/spec_generator.py` at `TABLE_HEADER`, `slide_row()`, and `generate_spec()`
- Modify: `skills/premium-presentations/references/slide-spec-template.md` at `## Slide Map`
- Modify: `skills/premium-presentations/scripts/tests/test_slide_map_parsing.py`
- Modify: `skills/premium-presentations/scripts/tests/test_spec_generator.py`

**Interfaces:**

- Consumes: Markdown text and the existing `validate_deck.validate(html_path, spec_path, strict_variety=False)` call path.
- Produces:

```python
@dataclass(frozen=True)
class SlideSpecRow:
    slide_id: str
    ordinal: int
    fields: Mapping[str, str]
    line_no: int
    raw_line: str

@dataclass(frozen=True)
class SlideSpec:
    headers: tuple[str, ...]
    rows: tuple[SlideSpecRow, ...]
    header_line_no: int
    separator_line_no: int

@dataclass(frozen=True)
class RowChange:
    slide_id: str
    fields: tuple[str, ...]

@dataclass(frozen=True)
class SpecDiff:
    changes: tuple[RowChange, ...]
    structural_reasons: tuple[str, ...]

def parse_slide_map(text: str, *, require_ids: bool = False) -> SlideSpec
def canonical_row(row: SlideSpecRow) -> bytes
def canonical_fields(fields: Mapping[str, str]) -> bytes
def decoded_title(row: SlideSpecRow) -> str
def diff_rows(baseline: SlideSpec, edited: SlideSpec) -> SpecDiff
def rewrite_slide_map_ids(text: str, ids: Sequence[str]) -> str
```

- [ ] **Step 1: Write failing parser and identity tests**

Create `test_slide_spec.py` with table-driven fixtures that exercise legacy 5-column, legacy 7-column, current 9-column, and ID-bearing 10-column maps. Include escaped pipes and an unknown `Audience Risk` column in the canonical data.

```python
from __future__ import annotations

import unittest

from slide_spec import (
    SlideSpecError,
    canonical_row,
    diff_rows,
    parse_slide_map,
    rewrite_slide_map_ids,
)


MAP = """## Slide Map

| # | ID | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes | Audience Risk |
|---|----|-----|------|-------|-------------|----------------|-----------|----------------|---------------|---------------|
| 1 | intro | 0 | Title | Opening \\| Promise | Set the frame | slide--title | N/A | Welcome | Pause once. | Low |
| 2 | proof | 1 | Content | Evidence | Compare results | BAR bar-chart | Decision | Explain the delta | Name the baseline. | High |

## Evidence Data
"""


class SlideSpecTests(unittest.TestCase):
    def test_parses_ids_escaped_pipe_and_unknown_column(self) -> None:
        spec = parse_slide_map(MAP, require_ids=True)
        self.assertEqual([row.slide_id for row in spec.rows], ["intro", "proof"])
        self.assertEqual(spec.rows[0].fields["Title"], "Opening | Promise")
        self.assertEqual(spec.rows[1].fields["Audience Risk"], "High")

    def test_canonical_row_ignores_markdown_spacing(self) -> None:
        compact = MAP.replace("| 2 | proof |", "|2|proof|")
        self.assertEqual(
            canonical_row(parse_slide_map(MAP, require_ids=True).rows[1]),
            canonical_row(parse_slide_map(compact, require_ids=True).rows[1]),
        )

    def test_diff_reports_fields_by_stable_id(self) -> None:
        edited = MAP.replace("Compare results", "Compare verified results")
        diff = diff_rows(
            parse_slide_map(MAP, require_ids=True),
            parse_slide_map(edited, require_ids=True),
        )
        self.assertEqual(diff.structural_reasons, ())
        self.assertEqual(diff.changes[0].slide_id, "proof")
        self.assertEqual(diff.changes[0].fields, ("Key Content",))

    def test_rewrite_adds_ids_without_changing_other_cells(self) -> None:
        legacy = """## Slide Map
| # | Act | Type | Title | Key Content |
|---|-----|------|-------|-------------|
| 1 | 0 | Title | Opening \\| Promise | Set the frame |
| 2 | 1 | Content | Evidence | Compare results |"""
        rewritten = rewrite_slide_map_ids(legacy, ["intro", "proof"])
        parsed = parse_slide_map(rewritten, require_ids=True)
        self.assertEqual([row.slide_id for row in parsed.rows], ["intro", "proof"])
        self.assertEqual(parsed.rows[0].fields["Title"], "Opening | Promise")

    def test_rewrite_updates_existing_id_column_without_duplicating_it(self) -> None:
        rewritten = rewrite_slide_map_ids(MAP, ["opening", "evidence"])
        parsed = parse_slide_map(rewritten, require_ids=True)
        self.assertEqual(parsed.headers.count("ID"), 1)
        self.assertEqual([row.slide_id for row in parsed.rows], ["opening", "evidence"])

    def test_rejects_invalid_identity_inputs(self) -> None:
        cases = {
            "duplicate": MAP.replace("| proof |", "| intro |"),
            "malformed": MAP.replace("| proof |", "| proof space |"),
            "missing": MAP.replace("| proof |", "|  |"),
            "nonsequential ordinal": MAP.replace("| 2 | proof |", "| 4 | proof |"),
        }
        for label, text in cases.items():
            with self.subTest(label=label), self.assertRaises(SlideSpecError):
                parse_slide_map(text, require_ids=True)


if __name__ == "__main__":
    unittest.main()
```

Add legacy fixtures to the same file with headers `# / Type / Title / Key Content / Visual Pattern` and `# / Type / Title / Key Content / Visual Pattern / Voiceover Beat / Speaker Notes`. Assert both parse with empty IDs when `require_ids=False` and fail when `require_ids=True`.

Add cases with one, two, and three backslashes before a pipe, CRLF input, no final newline, duplicate normalized headers, and two matching `## Slide Map` headings. Assert odd/even escaping is correct, newline style and trailing-newline presence survive `rewrite_slide_map_ids()`, and the last exact-depth Slide Map section wins.

- [ ] **Step 2: Run the focused tests and verify the red state**

Run:

```bash
cd skills/premium-presentations/scripts
python3 -m unittest tests.test_slide_spec tests.test_slide_map_parsing tests.test_spec_generator
```

Expected: `test_slide_spec` fails to import because `slide_spec.py` does not exist; the existing generator assertions also lack the new ID column.

- [ ] **Step 3: Implement the parser, canonical form, diff, and ID rewriter**

Use normalized names only for lookup and retain trimmed display headers as `fields` keys. Reject duplicate normalized headers, missing `#`, non-sequential ordinals, non-table data, and multiple data rows with the same ID.

```python
ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


class SlideSpecError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _pipe_boundaries(line: str) -> list[int]:
    boundaries: list[int] = []
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            boundaries.append(index)
    return boundaries


def _split_pipe_row(line: str) -> list[str]:
    boundaries = _pipe_boundaries(line)
    if len(boundaries) < 2 or line[: boundaries[0]].strip() or line[boundaries[-1] + 1 :].strip():
        raise SlideSpecError("Slide Map rows must start and end with an unescaped pipe")
    cells: list[str] = []
    for start, end in zip(boundaries, boundaries[1:]):
        raw = line[start + 1 : end].strip()
        cells.append(re.sub(r"\\([\\|])", r"\1", raw))
    return cells


def _insert_after_first_cell(line: str, value: str) -> str:
    boundaries = _pipe_boundaries(line)
    if len(boundaries) < 2:
        raise SlideSpecError("Cannot add ID column to malformed Slide Map row")
    escaped = value.replace("\\", "\\\\").replace("|", "\\|")
    close = boundaries[1]
    return f"{line[:close + 1]} {escaped} |{line[close + 1:]}"


def canonical_fields(fields: Mapping[str, str]) -> bytes:
    semantic = {
        key: value
        for key, value in fields.items()
        if _normalized(key) not in {"#", "id"}
    }
    return json.dumps(
        semantic,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_row(row: SlideSpecRow) -> bytes:
    return canonical_fields(row.fields)


def decoded_title(row: SlideSpecRow) -> str:
    return html.unescape(row.fields.get("Title", ""))
```

In `parse_slide_map()`, select the last exact-depth `## Slide Map` section when present, otherwise select the last table whose first normalized header is `#`. Record 1-based line numbers, require each data row width to equal the header width, wrap each row field dictionary in `MappingProxyType`, and return tuples. Give each failure a stable code such as `no_slide_map`, `missing_id`, `duplicate_id`, `invalid_id`, `duplicate_header`, or `malformed_row`. In `diff_rows()`, return structural reasons in this fixed order: `slide_count_changed`, `identity_set_changed`, `identity_order_changed`; only compare semantic row fields when no structural reason exists, and list changed fields in edited-header order.

In `rewrite_slide_map_ids()`, require `len(ids) == len(spec.rows)` and validate the full ID set. When the selected map lacks `ID`, insert `ID` after the first header cell, `---` after the first separator cell, and the corresponding ID after each ordinal cell. When `ID` already exists, replace each ID cell in place by using its unescaped delimiter offsets; do not add another column. This must accept new generated specs, fill empty IDs during explicit initialization, and preserve every byte outside the selected ID cells/table insertions.

- [ ] **Step 4: Integrate the shared parser into generation and validation**

Change the generator header exactly as follows, preserving the current title escaping and speaker-note behavior:

```python
TABLE_HEADER = (
    "| # | ID | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes |\n"
    "|---|----|-----|------|-------|-------------|----------------|-----------|----------------|---------------|"
)
```

In the existing `slide_row()` return expression, insert `slide-{i}` immediately after the ordinal and leave every later expression unchanged. Update the `generate_spec()` table-header regular expression to accept an optional existing `ID` column and replace the entire detected table once. Mirror the exact 10-column header in `references/slide-spec-template.md` and add `slide-1`, `slide-2`, `slide-3`, and `slide-N` to its example rows. Update `test_spec_generator.py` so its header trigger includes `ID`, `Visual Pattern` moves from cell index 5 to 6, and `Speaker Notes` moves from 8 to 9.

Replace the hand-written counting loop in `validate_deck.py` with:

```python
from slide_spec import SlideSpecError, parse_slide_map

# Inside validate(), after reading spec text:
try:
    parsed_spec = parse_slide_map(spec)
except SlideSpecError as exc:
    err(f"Invalid Slide Map: {exc}")
else:
    expected = len(parsed_spec.rows)
    if expected != slides:
        err(f"Slide count mismatch: HTML has {slides}, spec slide map has {expected}")
```

Retain the current absent-map warning by having `parse_slide_map()` raise `SlideSpecError("no Slide Map table found")` and translating only that message to the warning; every malformed detected map is an error.

- [ ] **Step 5: Run the parser/generator/validator gate**

Run:

```bash
cd skills/premium-presentations/scripts
python3 -m unittest tests.test_slide_spec tests.test_slide_map_parsing tests.test_spec_generator
```

Expected: all selected tests pass. The generated Slide Map has ten cells, legacy fixtures still count correctly, and malformed detected maps fail validation.

- [ ] **Step 6: Commit Task 1**

```bash
git add skills/premium-presentations/scripts/slide_spec.py \
  skills/premium-presentations/scripts/tests/test_slide_spec.py
git add -p skills/premium-presentations/scripts/validate_deck.py \
  skills/premium-presentations/scripts/spec_generator.py \
  skills/premium-presentations/references/slide-spec-template.md \
  skills/premium-presentations/scripts/tests/test_slide_map_parsing.py \
  skills/premium-presentations/scripts/tests/test_spec_generator.py
git diff --cached --check
git commit -m "feat: add stable slide map identities"
```

---

### Task 2: Exact HTML spans and fragment safety

**Files:**

- Create: `skills/premium-presentations/scripts/slide_html.py`
- Create: `skills/premium-presentations/scripts/tests/test_slide_html.py`
- Modify: `skills/premium-presentations/scripts/validate_deck.py` at the current HTML slide-count expression
- Modify: `skills/premium-presentations/scripts/tests/test_slide_map_parsing.py`

**Interfaces:**

- Consumes: `SlideSpecRow` from Task 1.
- Produces:

```python
@dataclass(frozen=True)
class SlideSpan:
    slide_id: str
    title: str
    start: int
    end: int
    raw: str

@dataclass(frozen=True)
class JsonScriptSpan:
    element_id: str
    start: int
    end: int
    content_start: int
    content_end: int
    content: str
    inside_deck: bool

def parse_slide_spans(html: str) -> list[SlideSpan]
def parse_json_script_span(html: str, element_id: str) -> JsonScriptSpan
def assign_slide_ids(html: str, ids: Sequence[str]) -> str
def validate_fragment(fragment: str, expected: SlideSpecRow) -> list[str]
def splice_sections(html: str, replacements: Mapping[str, str]) -> str
```

- [ ] **Step 1: Write failing exact-span, assignment, and fragment tests**

Create a fixture where a slide contains a nested non-slide `<section>`, a `<template>` containing section text, a `<script>` string containing `</section>`, and a comment containing `<section>`. Verify exact raw slices and byte preservation.

```python
from __future__ import annotations

import unittest
from types import MappingProxyType

from slide_html import (
    SlideHtmlError,
    assign_slide_ids,
    parse_json_script_span,
    parse_slide_spans,
    splice_sections,
    validate_fragment,
)
from slide_spec import SlideSpecRow


DECK = """<!doctype html><html><body><div id="deck">
<section class="slide" id="intro" data-nav-title="Opening"><h1>Opening</h1><section class="detail"><p>Nested</p></section><template><div>Template</div></template><aside class="notes">Say opening.</aside></section>
<!-- between -->
<section data-nav-title="Proof" class="wide slide" id="proof"><script>const closing = "</section>";</script><h2>Proof</h2><aside class="notes">Explain proof.</aside></section>
</div></body></html>"""


def expected(slide_id: str, title: str) -> SlideSpecRow:
    return SlideSpecRow(slide_id, 1, MappingProxyType({"Title": title}), 1, "")


class SlideHtmlTests(unittest.TestCase):
    def test_exact_spans_ignore_raw_text_and_nested_markup(self) -> None:
        spans = parse_slide_spans(DECK)
        self.assertEqual([span.slide_id for span in spans], ["intro", "proof"])
        self.assertEqual([DECK[span.start:span.end] for span in spans], [span.raw for span in spans])
        self.assertIn('const closing = "</section>";', spans[1].raw)

    def test_json_state_span_is_real_unique_and_outside_deck(self) -> None:
        fake = '<script>const fake = \'<script type="application/json" id="premium-regen-state">{}<\/script>\';</script>'
        state = '<script type="application/json" id="premium-regen-state">{"version":1}</script>'
        source = DECK.replace("</body>", fake + state + "</body>")
        span = parse_json_script_span(source, "premium-regen-state")
        self.assertEqual(span.content, '{"version":1}')
        self.assertFalse(span.inside_deck)
        with self.assertRaises(SlideHtmlError):
            parse_json_script_span(DECK.replace("</div></body>", state + "</div></body>"), "premium-regen-state")

    def test_splice_preserves_every_untargeted_byte(self) -> None:
        replacement = '<section class="slide" id="proof" data-nav-title="Proof"><h2>Verified</h2><aside class="notes">Explain proof.</aside></section>'
        updated = splice_sections(DECK, {"proof": replacement})
        before = {span.slide_id: span.raw for span in parse_slide_spans(DECK)}
        after = {span.slide_id: span.raw for span in parse_slide_spans(updated)}
        self.assertEqual(after["intro"], before["intro"])
        self.assertEqual(updated.replace(after["proof"], "TARGET"), DECK.replace(before["proof"], "TARGET"))

    def test_assigns_missing_ids_without_touching_section_bodies(self) -> None:
        no_ids = DECK.replace(' id="intro"', "").replace(' id="proof"', "")
        updated = assign_slide_ids(no_ids, ["slide-1", "slide-2"])
        spans = parse_slide_spans(updated)
        self.assertEqual([span.slide_id for span in spans], ["slide-1", "slide-2"])
        self.assertEqual([span.title for span in spans], ["Opening", "Proof"])

    def test_fragment_contract(self) -> None:
        valid = '<section class="slide" id="proof" data-nav-title="Proof &amp; Safety"><h2>Verified</h2><aside class="notes">Explain proof.</aside></section>'
        self.assertEqual(validate_fragment(valid, expected("proof", "Proof & Safety")), [])
        invalid = {
            "wrong id": valid.replace('id="proof"', 'id="other"'),
            "wrong title": valid.replace("Proof &amp; Safety", "Other"),
            "two roots": valid + valid,
            "script": valid.replace("<h2>", "<script></script><h2>"),
            "notes not final": valid.replace("</aside>", "</aside><p>After</p>"),
            "nested notes": valid.replace('<aside class="notes">Explain proof.</aside>', '<div><aside class="notes">Explain proof.</aside></div>'),
            "deck control": valid.replace("<h2>", '<div id="controls"></div><h2>'),
        }
        for label, fragment in invalid.items():
            with self.subTest(label=label):
                self.assertTrue(validate_fragment(fragment, expected("proof", "Proof & Safety")))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused tests and verify the red state**

Run:

```bash
cd skills/premium-presentations/scripts
python3 -m unittest tests.test_slide_html
```

Expected: import failure because `slide_html.py` does not exist.

- [ ] **Step 3: Implement the exact-offset parser and splicer**

Subclass `html.parser.HTMLParser(convert_charrefs=False)`. Convert `(line, column)` from `getpos()` to an absolute character offset with precomputed line starts. Track exactly one `div#deck`; accept authored slides only when `section.slide` is a direct child of that deck. At a slide start tag, store the start offset, parsed `id`, decoded `data-nav-title`, and a section depth of one. Increment depth for nested non-slide `<section>` starts. At the matching close, set `end` to the first `>` at or after the close-tag offset plus one. `HTMLParser` raw-text handling must own script/style content; do not search for slide closing tags with a regular expression.

```python
class SlideHtmlError(ValueError):
    pass


def _class_tokens(attrs: list[tuple[str, str | None]]) -> set[str]:
    values = [value or "" for name, value in attrs if name.casefold() == "class"]
    return {token for value in values for token in value.split()}


def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {name.casefold(): value or "" for name, value in attrs}


def splice_sections(source: str, replacements: Mapping[str, str]) -> str:
    spans = parse_slide_spans(source)
    by_id = {span.slide_id: span for span in spans}
    missing = sorted(set(replacements) - set(by_id))
    if missing:
        raise SlideHtmlError(f"replacement IDs not present in deck: {', '.join(missing)}")
    output = source
    for slide_id in sorted(replacements, key=lambda key: by_id[key].start, reverse=True):
        span = by_id[slide_id]
        output = output[: span.start] + replacements[slide_id] + output[span.end :]
    return output
```

Reject duplicate attributes on any authored slide tag, multiple/missing `#deck` roots, self-closing slide sections, unclosed slide sections, duplicate non-empty slide IDs, a slide outside `#deck`, and a slide nested inside another slide. `HTMLParser` already entity-decodes attribute values; `_attrs()` must not decode a second time. `assign_slide_ids()` requires a count match and valid unique IDs, preserves a matching existing valid ID, rejects a different/malformed existing ID, and injects ` id="escaped-id"` immediately before the first slide start tag's closing `>` without rewriting its body.

Use the same parser event/offset machinery for `parse_json_script_span()`. It must return exactly one real `script` whose decoded `id` matches and whose decoded `type` is `application/json`, include exact content offsets, ignore lookalike strings inside script/style raw text and comments, and reject a missing/duplicate match or any match nested inside `#deck`.

Replace `validate_deck.py`'s attribute-order-sensitive HTML count with the shared HTML parser:

```python
from slide_html import SlideHtmlError, parse_slide_spans

try:
    slides = len(parse_slide_spans(text))
except SlideHtmlError as exc:
    err(f"Invalid slide structure: {exc}")
    slides = 0
```

Add a regression deck whose slide tag starts with `id` before `class`; it must count exactly once.

- [ ] **Step 4: Implement structural fragment validation**

Use a second `HTMLParser` inspector. It must count top-level elements, maintain element depth, collect direct children of the root slide, and report stable messages in this order: root count/type, ID, title, forbidden tags, forbidden controls, direct notes count, notes finality, unclosed markup.

```python
FORBIDDEN_TAGS = frozenset({"html", "head", "body", "script", "style", "link"})
FORBIDDEN_IDS = frozenset({"deck", "controls", "presenter-popup", "premium-regen-state", "glossary"})
FORBIDDEN_CLASSES = frozenset({"premium-controller", "presenter-popup", "presenter-controls"})
SCRIPT_URL_ATTRIBUTES = frozenset({"href", "src", "action", "formaction", "xlink:href"})


def validate_fragment(fragment: str, expected: SlideSpecRow) -> list[str]:
    inspector = _FragmentInspector(fragment)
    inspector.feed(fragment)
    inspector.close()
    errors = list(inspector.errors)
    if inspector.root_count != 1 or inspector.root_tag != "section" or "slide" not in inspector.root_classes:
        errors.append("fragment must contain exactly one top-level section.slide")
    if inspector.root_id != expected.slide_id:
        errors.append(f"fragment id must be {expected.slide_id!r}")
    expected_title = decoded_title(expected)
    if inspector.root_title != expected_title:
        errors.append(f"data-nav-title must equal decoded Title {expected_title!r}")
    if inspector.direct_notes != 1:
        errors.append("fragment must contain exactly one direct aside.notes")
    final_tag, final_classes = inspector.direct_children[-1] if inspector.direct_children else ("", frozenset())
    if final_tag != "aside" or "notes" not in final_classes:
        errors.append("aside.notes must be the final direct child element")
    return list(dict.fromkeys(errors))
```

The inspector must reject duplicate attribute names, any forbidden tag at any depth, any `on*` event-handler attribute, a case/whitespace-normalized `javascript:` value in `SCRIPT_URL_ATTRIBUTES`, any element whose `id` is in `FORBIDDEN_IDS`, and any class intersection with `FORBIDDEN_CLASSES`. It must also reject non-whitespace text, comments, declarations, or processing instructions outside the single root section. Add explicit tests for duplicate `id`, `onclick`, and `href=" javascript:alert(1)"`.

For final-child validation, accept additional classes on the notes element: require the final tuple's tag to equal `aside` and require `notes` to be present in its class set. Do not require its class set to equal `{"notes"}`.

- [ ] **Step 5: Run Task 2 tests**

Run:

```bash
cd skills/premium-presentations/scripts
python3 -m unittest tests.test_slide_html tests.test_slide_map_parsing
```

Expected: all tests pass, including exact raw slice equality and all invalid fragment subtests.

- [ ] **Step 6: Commit Task 2**

```bash
git add skills/premium-presentations/scripts/slide_html.py \
  skills/premium-presentations/scripts/tests/test_slide_html.py
git add -p skills/premium-presentations/scripts/validate_deck.py \
  skills/premium-presentations/scripts/tests/test_slide_map_parsing.py
git diff --cached --check
git commit -m "feat: validate exact slide fragments"
```

---

### Task 3: Embedded regeneration state, initialization preview, and read-only plan

**Files:**

- Create: `skills/premium-presentations/scripts/partial_regen.py`
- Create: `skills/premium-presentations/scripts/tests/test_partial_regen.py`

**Interfaces:**

- Consumes: `SlideSpec`, `SlideSpecRow`, `canonical_fields()`, `canonical_row()`, `decoded_title()`, `diff_rows()`, `parse_slide_map()`, `rewrite_slide_map_ids()`, `SlideSpan`, `assign_slide_ids()`, `parse_json_script_span()`, and `parse_slide_spans()` from Tasks 1 and 2.
- Produces:

```python
STATE_ID = "premium-regen-state"

@dataclass(frozen=True)
class PlanResult:
    status: str
    reason_code: str
    changed: Mapping[str, tuple[str, ...]]
    messages: tuple[str, ...]

def load_state(html: str) -> Mapping[str, object]
def render_state(state: Mapping[str, object]) -> str
def envelope_hash(html: str) -> str
def _build_init_candidates(deck: Path, spec: Path) -> tuple[str, str, PlanResult]
def preview_init(deck: Path, spec: Path) -> PlanResult
def plan_pair(deck: Path, spec: Path, *, check_transactions: bool = True) -> PlanResult
def main(argv: Sequence[str] | None = None) -> int
```

- [ ] **Step 1: Write failing state, preview, and planning tests**

Build test pairs in `TemporaryDirectory()` with a two-slide deck and an ID-free Slide Map. Patch only exported filesystem/doctor seams in later transaction tests; these pure planning tests use real files.

```python
class PairFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write_uninitialized_pair(self) -> tuple[Path, Path]:
        deck = self.root / "lesson-slides.html"
        spec = self.root / "lesson-slide-spec.md"
        deck.write_text(
            '<!doctype html><html><body><div id="deck">\n'
            '<section class="slide" data-nav-title="Opening"><h1>Original body</h1><aside class="notes">Open the lesson.</aside></section>\n'
            '<section class="slide" data-nav-title="Proof"><h2>Evidence</h2><aside class="notes">Explain the proof.</aside></section>\n'
            '</div></body></html>',
            encoding="utf-8",
        )
        spec.write_text(
            "## Slide Map\n\n"
            "| # | Act | Type | Title | Key Content |\n"
            "|---|-----|------|-------|-------------|\n"
            "| 1 | 0 | Title | Opening | Establish context |\n"
            "| 2 | 1 | Content | Proof | Compare results |\n",
            encoding="utf-8",
        )
        return deck, spec

    def write_initialized_pair(self) -> tuple[Path, Path]:
        deck, spec = self.write_uninitialized_pair()
        deck_text, spec_text, _ = partial_regen._build_init_candidates(deck, spec)
        deck.write_text(deck_text, encoding="utf-8")
        spec.write_text(spec_text, encoding="utf-8")
        return deck, spec


class PlanningTests(PairFixture):
    def test_init_preview_is_read_only_and_deterministic(self) -> None:
        deck, spec = self.write_uninitialized_pair()
        before = (deck.read_bytes(), spec.read_bytes())
        before_mtimes = (deck.stat().st_mtime_ns, spec.stat().st_mtime_ns)
        before_tree = tuple(sorted(path.relative_to(deck.parent) for path in deck.parent.rglob("*")))
        result = partial_regen.preview_init(deck, spec)
        self.assertEqual(result.status, "initialization_preview")
        self.assertEqual(tuple(result.changed), ("slide-1", "slide-2"))
        self.assertEqual((deck.read_bytes(), spec.read_bytes()), before)
        self.assertEqual((deck.stat().st_mtime_ns, spec.stat().st_mtime_ns), before_mtimes)
        self.assertEqual(tuple(sorted(path.relative_to(deck.parent) for path in deck.parent.rglob("*"))), before_tree)

    def test_state_json_is_deterministic_and_script_safe(self) -> None:
        state = {
            "version": 1,
            "deck": "lesson-slides.html",
            "spec": "lesson-slide-spec.md",
            "order": ["slide-1"],
            "envelopeHash": "sha256:" + "a" * 64,
            "slides": {"slide-1": {
                "row": {"Title": "A </script> title"},
                "rowHash": "sha256:" + "b" * 64,
                "sectionHash": "sha256:" + "c" * 64,
            }},
        }
        first = partial_regen.render_state(state)
        second = partial_regen.render_state(dict(reversed(list(state.items()))))
        self.assertEqual(first, second)
        self.assertNotIn("</script> title", first)
        self.assertIn("\\u003c/script> title", first)

    def test_plan_reports_one_and_multiple_row_changes(self) -> None:
        deck, spec = self.write_initialized_pair()
        spec.write_text(spec.read_text().replace("Opening", "New Opening"), encoding="utf-8")
        one = partial_regen.plan_pair(deck, spec)
        self.assertEqual(one.status, "changes_planned")
        self.assertEqual(one.changed["slide-1"], ("Title",))
        spec.write_text(spec.read_text().replace("Compare results", "Compare verified results"), encoding="utf-8")
        two = partial_regen.plan_pair(deck, spec)
        self.assertEqual(tuple(two.changed), ("slide-1", "slide-2"))

    def test_plan_refuses_structural_change_and_slide_drift(self) -> None:
        deck, spec = self.write_initialized_pair()
        reordered = spec.read_text().replace("| 1 | slide-1 |", "| 1 | swap |", 1).replace("| 2 | slide-2 |", "| 2 | slide-1 |", 1).replace("| 1 | swap |", "| 1 | slide-2 |", 1)
        spec.write_text(reordered, encoding="utf-8")
        structural = partial_regen.plan_pair(deck, spec)
        self.assertEqual((structural.status, structural.reason_code), ("full_regeneration_required", "identity_order_changed"))
        deck, spec = self.write_initialized_pair()
        deck.write_text(deck.read_text().replace("Original body", "Manual body edit"), encoding="utf-8")
        drift = partial_regen.plan_pair(deck, spec)
        self.assertEqual((drift.status, drift.reason_code), ("baseline_drift", "section_hash_changed"))
```

Add public `main()` tests with redirected stdout for `init`, `plan`, and `plan --json`; assert JSON object keys are exactly `status`, `reasonCode`, `changed`, and `messages`, and assert exit codes `0`, `2`, and `3` for preview, structural refusal, and section drift.

- [ ] **Step 2: Run planning tests and verify the red state**

Run:

```bash
cd skills/premium-presentations/scripts
python3 -m unittest tests.test_partial_regen.PlanningTests
```

Expected: import failure because `partial_regen.py` does not exist.

- [ ] **Step 3: Implement deterministic state and envelope hashing**

Use SHA-256 labels with a fixed `sha256:` prefix. State slide rows contain all semantic fields except `#` and `ID`; section hashes cover exact UTF-8 bytes.

```python
def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def render_state(state: Mapping[str, object]) -> str:
    order = list(state["order"])
    source_slides = state["slides"]
    normalized = {
        "version": state["version"],
        "deck": state["deck"],
        "spec": state["spec"],
        "order": order,
        "envelopeHash": state["envelopeHash"],
        "slides": {
            slide_id: {
                "row": dict(sorted(source_slides[slide_id]["row"].items())),
                "rowHash": source_slides[slide_id]["rowHash"],
                "sectionHash": source_slides[slide_id]["sectionHash"],
            }
            for slide_id in order
        },
    }
    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    ).replace("<", "\\u003c")
    return f'<script type="application/json" id="{STATE_ID}">{payload}</script>'


def load_state(html_text: str) -> Mapping[str, object]:
    span = parse_json_script_span(html_text, STATE_ID)
    state = json.loads(span.content)
    if not isinstance(state, dict) or state.get("version") != 1:
        raise RegenInputError("unsupported premium regeneration state")
    return state


def envelope_hash(html_text: str) -> str:
    replacements = [
        (span.start, span.end, f"<!--premium-slide:{ordinal}-->")
        for ordinal, span in enumerate(parse_slide_spans(html_text), 1)
    ]
    state_span = parse_json_script_span(html_text, STATE_ID)
    replacements.append((state_span.start, state_span.end, "<!--premium-regen-state-->"))
    masked = html_text
    for start, end, sentinel in sorted(replacements, reverse=True):
        masked = masked[:start] + sentinel + masked[end:]
    return _sha256(masked.encode("utf-8"))
```

Before accepting state, validate exact top-level keys, deck/spec basenames, ordered unique IDs, `tuple(slides.keys()) == tuple(order)`, per-slide row dictionaries, and 71-character SHA-256 labels. Recompute every stored `rowHash` from `canonical_fields(row)` and reject a mismatch. Reject absolute paths or path separators in stored basenames. Replace/update the manifest only through the exact offsets returned by `parse_json_script_span()`; do not use regex substitution for state extraction or replacement.

- [ ] **Step 4: Implement input safety, ID selection, initialization preview, and planning**

Use `Path.lstat()` so symlinks cannot pass by resolving to regular files. Resolve parent directories and require equality.

```python
def validate_pair(deck: Path, spec: Path) -> tuple[Path, Path]:
    for label, path in (("deck", deck), ("spec", spec)):
        mode = path.lstat().st_mode
        if stat_module.S_ISLNK(mode) or not stat_module.S_ISREG(mode):
            raise RegenInputError(f"{label} must be a regular non-symlink file: {path}")
    if deck.resolve() == spec.resolve():
        raise RegenInputError("deck and spec must be distinct files")
    if deck.resolve().parent != spec.resolve().parent:
        raise RegenInputError("deck and spec must be in the same resolved directory")
    return deck.resolve(), spec.resolve()


def _select_init_ids(rows: Sequence[SlideSpecRow], spans: Sequence[SlideSpan]) -> tuple[str, ...]:
    if len(rows) != len(spans):
        raise RegenInputError("deck/spec slide count mismatch")
    chosen: list[str] = []
    for ordinal, (row, span) in enumerate(zip(rows, spans), 1):
        spec_id = row.slide_id
        deck_id = span.slide_id
        if spec_id and deck_id and spec_id != deck_id:
            raise RegenInputError(f"conflicting IDs at slide {ordinal}: {spec_id!r} != {deck_id!r}")
        candidate = deck_id or spec_id or f"slide-{ordinal}"
        if not ID_RE.fullmatch(candidate):
            raise RegenInputError(f"invalid slide ID at slide {ordinal}: {candidate!r}")
        chosen.append(candidate)
    if len(set(chosen)) != len(chosen):
        raise RegenInputError("initialization would create duplicate slide IDs")
    return tuple(chosen)
```

Implement `_build_init_candidates()` as a pure read/transform operation: rewrite the spec IDs, assign deck IDs, create a state dictionary, and insert the rendered block immediately before `</body>`; fail if `</body>` is absent or a state block already exists. Return candidate deck text, candidate spec text, and the same preview result used by `preview_init()`. The state dictionary stores `version`, `deck`, `spec`, `order`, `envelopeHash`, and `slides`, with each slide holding `row`, `rowHash`, and `sectionHash`.

Before choosing IDs, require each section's already-decoded `data-nav-title` to equal `decoded_title(row)` at that ordinal. Initialization may establish identity, but it may not bless an already misaligned deck/spec pair.

`plan_pair()` must check in this order: unresolved transaction, safe pair, valid state and matching basenames, spec identity structure, deck identity order/set, envelope hash, each current section hash, and row diffs. Return the first stable refusal reason. Use these status/reason pairs:

```python
PLAN_REASONS = {
    "no_changes": ("no_changes", "none"),
    "changes": ("changes_planned", "spec_rows_changed"),
    "count": ("full_regeneration_required", "slide_count_changed"),
    "set": ("full_regeneration_required", "identity_set_changed"),
    "order": ("full_regeneration_required", "identity_order_changed"),
    "envelope": ("full_regeneration_required", "global_envelope_changed"),
    "drift": ("baseline_drift", "section_hash_changed"),
    "missing_id": ("full_regeneration_required", "missing_identity"),
    "duplicate_id": ("full_regeneration_required", "duplicate_identity"),
    "invalid_id": ("full_regeneration_required", "invalid_identity"),
}
```

Once valid embedded state exists, catch `SlideSpecError` identity codes `missing_id`, `duplicate_id`, and `invalid_id` and return their exit-code-`2` full-regeneration results. Added/removed rows and changed order/set also return `2`. Reserve exit code `1` for a malformed non-identity table, malformed state, invalid arguments, validation failure, or I/O error.

- [ ] **Step 5: Implement the CLI shell for `init` and `plan`**

Create `argparse` subparsers for read-only `init` and `plan`, with required `--deck` and `--spec`, and `--json` only on `plan`. Task 4 adds the mutation flags and commands atomically with their implementation. Subclass `ArgumentParser` so syntax failures raise `RegenInputError` and return exit code `1`; reserve exit code `2` exclusively for the feature's full-regeneration result. Preserve `--help` exit code `0`. Map expected exceptions and results without tracebacks.

```python
class RegenArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise RegenInputError(message)
```

```python
def _exit_for(result: PlanResult) -> int:
    if result.status == "full_regeneration_required":
        return 2
    if result.status == "baseline_drift":
        return 3
    return 0


def _print_json(result: PlanResult) -> None:
    payload = {
        "status": result.status,
        "reasonCode": result.reason_code,
        "changed": {key: list(value) for key, value in result.changed.items()},
        "messages": list(result.messages),
    }
    print(json.dumps(payload, sort_keys=False, separators=(",", ":")))
```

Human output must state that Claude Code or Codex should generate one fragment per changed ID and must show the exact `ID=FILE` apply shape without creating files.

For `plan --json`, catch invalid state/input and emit exactly one deterministic JSON object before returning exit code `1`; do not mix human text or `argparse` usage into stdout.

- [ ] **Step 6: Run planning tests**

Run:

```bash
cd skills/premium-presentations/scripts
python3 -m unittest tests.test_partial_regen.PlanningTests
```

Expected: all planning tests pass. `init` and `plan` previews leave deck/spec bytes and directory listings unchanged.

- [ ] **Step 7: Commit Task 3**

```bash
git add skills/premium-presentations/scripts/partial_regen.py \
  skills/premium-presentations/scripts/tests/test_partial_regen.py
git commit -m "feat: plan spec-aware slide regeneration"
```

---

### Task 4: Transactional init, apply, backup, and rollback

**Files:**

- Modify: `skills/premium-presentations/scripts/partial_regen.py`
- Modify: `skills/premium-presentations/scripts/tests/test_partial_regen.py`

**Interfaces:**

- Consumes: Task 3 state/plan interfaces, `validate_fragment()` and `splice_sections()` from Task 2, `deck_doctor.main(argv)` from the existing validator, and conditional runtime helpers from `validate_runtime_contract.py`.
- Produces public commands:

```text
partial_regen.py init --deck DECK --spec SPEC --apply
partial_regen.py apply --deck DECK --spec SPEC --fragment ID=FILE
partial_regen.py rollback --deck DECK --backup BACKUP_DIRECTORY
```

Extend the Task 3 parser in this task: add `--apply` to `init`, add `apply` with repeatable required `--fragment`, and add `rollback` with required `--backup`. Keep invalid syntax at exit code `1` through `RegenArgumentParser`.

- [ ] **Step 1: Write failing mutation, capability, and rollback tests**

Extend `test_partial_regen.py` with real temporary files and fault injection at `_create_backup`, `_run_deck_doctor`, `_replace_file`, and `_validate_committed_pair`.

```python
class MutationTests(PairFixture):
    def setUp(self) -> None:
        super().setUp()
        doctor = mock.patch.object(partial_regen, "_run_deck_doctor", return_value=None)
        doctor.start()
        self.addCleanup(doctor.stop)

    def only_backup(self, deck: Path) -> Path:
        backups = sorted((deck.parent / ".partial-regen" / "backups").iterdir())
        self.assertEqual(len(backups), 1)
        return backups[0]

    def write_fragment(self, slide_id: str, title: str, body: str) -> Path:
        path = self.root / f"{slide_id}.html"
        path.write_text(
            f'<section class="slide" id="{slide_id}" data-nav-title="{title}">'
            f'<div class="content">{body}</div>'
            '<aside class="notes">Explain the updated evidence.</aside></section>',
            encoding="utf-8",
        )
        return path

    def write_ready_apply_pair(self) -> tuple[Path, Path, Path]:
        deck, spec = self.write_initialized_pair()
        spec.write_text(
            spec.read_text(encoding="utf-8").replace("Compare results", "Compare verified results"),
            encoding="utf-8",
        )
        return deck, spec, self.write_fragment("slide-2", "Proof", "Verified body")

    def test_init_apply_backs_up_both_files_and_commits_state(self) -> None:
        deck, spec = self.write_uninitialized_pair()
        original = {deck.name: deck.read_bytes(), spec.name: spec.read_bytes()}
        rc = partial_regen.main(["init", "--deck", str(deck), "--spec", str(spec), "--apply"])
        self.assertEqual(rc, 0)
        state = partial_regen.load_state(deck.read_text(encoding="utf-8"))
        self.assertEqual(state["order"], ["slide-1", "slide-2"])
        backup = self.only_backup(deck)
        metadata = json.loads((backup / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual([item["target"] for item in metadata["targets"]], [deck.name, spec.name])
        for name, content in original.items():
            self.assertEqual((backup / name).read_bytes(), content)
        self.assertEqual(metadata["status"], "committed")

    def test_apply_requires_exact_fragment_set_and_preserves_other_slide(self) -> None:
        deck, spec = self.write_initialized_pair()
        original = {span.slide_id: span.raw for span in parse_slide_spans(deck.read_text())}
        spec.write_text(spec.read_text().replace("Compare results", "Compare verified results"), encoding="utf-8")
        fragment = self.write_fragment("slide-2", "Proof", "Verified body")
        rc = partial_regen.main(["apply", "--deck", str(deck), "--spec", str(spec), "--fragment", f"slide-2={fragment}"])
        self.assertEqual(rc, 0)
        updated = {span.slide_id: span.raw for span in parse_slide_spans(deck.read_text())}
        self.assertEqual(updated["slide-1"], original["slide-1"])
        self.assertIn("Verified body", updated["slide-2"])

    def test_apply_rejects_new_runtime_and_glossary_capabilities(self) -> None:
        deck, spec = self.write_initialized_pair()
        spec.write_text(spec.read_text().replace("Compare results", "Compare verified results"), encoding="utf-8")
        fragments = {
            "journey": '<div class="journey-stage"></div>',
            "flow": '<div class="live-flow"></div>',
            "mermaid": '<pre class="mermaid">graph TD; A-->B;</pre>',
            "glossary": '<button class="term-link" data-term="NEW_TERM">Term</button>',
            "theme homage": '<div class="slide--title">Hero</div>',
        }
        for label, body in fragments.items():
            with self.subTest(label=label):
                fragment = self.write_fragment("slide-2", "Proof", body)
                rc = partial_regen.main(["apply", "--deck", str(deck), "--spec", str(spec), "--fragment", f"slide-2={fragment}"])
                self.assertEqual(rc, 2)

    def test_each_failure_seam_leaves_targets_byte_identical(self) -> None:
        seams = ("_create_backup", "_run_deck_doctor", "_replace_file", "_validate_committed_pair")
        for seam in seams:
            with self.subTest(seam=seam):
                deck, spec, fragment = self.write_ready_apply_pair()
                before = (deck.read_bytes(), spec.read_bytes())
                with mock.patch.object(partial_regen, seam, side_effect=OSError("injected failure")):
                    self.assertEqual(partial_regen.main(["apply", "--deck", str(deck), "--spec", str(spec), "--fragment", f"slide-2={fragment}"]), 1)
                self.assertEqual((deck.read_bytes(), spec.read_bytes()), before)

    def test_rollback_restores_exact_metadata_targets(self) -> None:
        deck, spec = self.write_uninitialized_pair()
        originals = (deck.read_bytes(), spec.read_bytes())
        self.assertEqual(partial_regen.main(["init", "--deck", str(deck), "--spec", str(spec), "--apply"]), 0)
        backup = self.only_backup(deck)
        self.assertEqual(partial_regen.main(["rollback", "--deck", str(deck), "--backup", str(backup)]), 0)
        self.assertEqual((deck.read_bytes(), spec.read_bytes()), originals)
```

Add separate tests for duplicate `--fragment` IDs, a missing planned fragment, an extra fragment, symlink fragment input, a wrong title/ID, global tags, missing/final notes, backup path traversal, backup symlink, unexpected target basename, backup hash mismatch, an unresolved prepared journal, and apply rollback leaving the edited spec untouched.

- [ ] **Step 2: Run mutation tests and verify the red state**

Run:

```bash
cd skills/premium-presentations/scripts
python3 -m unittest tests.test_partial_regen.MutationTests
```

Expected: failures because the mutation commands and transaction behavior are absent from the Task 3 CLI.

- [ ] **Step 3: Implement durable backup metadata and transaction primitives**

Use a UTC directory name with microseconds (`%Y%m%dT%H%M%S.%fZ`) and an exclusive-create retry suffix for timestamp collisions. Create backup files with exclusive mode, preserve each target's permission bits on staged replacements/restores, fsync each file, atomically write JSON metadata, and fsync the backup directory.

```python
def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _backup_root(deck: Path) -> Path:
    return deck.resolve().parent / ".partial-regen" / "backups"


def _replace_file(source: Path, target: Path) -> None:
    os.replace(source, target)
    _fsync_directory(target.parent)
```

Metadata schema is fixed:

```json
{"operation":"init","status":"prepared","targets":[{"backup":"lesson-slides.html","sha256":"sha256:0000000000000000000000000000000000000000000000000000000000000000","target":"lesson-slides.html"},{"backup":"lesson-slide-spec.md","sha256":"sha256:1111111111111111111111111111111111111111111111111111111111111111","target":"lesson-slide-spec.md"}],"version":1}
```

Write and fsync backup payloads, metadata, candidate files, and `status: prepared` before the first target replacement, then write `committed` after final validation. If automatic restoration succeeds after an exception, write `rolled_back`. Detect any `metadata.json` or `rollback-metadata.json` with `prepared` beneath the deck's backup root before `init`, `plan`, or `apply`; return exit code `1` and the exact backup directory to pass to `rollback`. Add failure injection for backup write, prepared-journal write, first replacement, second replacement, Deck Doctor, committed-view validation, and rollback's own replacement.

- [ ] **Step 4: Implement transactional initialization**

Stage the rewritten spec and initialized deck as sibling files, run Deck Doctor on the staged pair, create the two-file backup, mark prepared, replace deck then spec, validate the committed pair, and mark committed. On any post-prepare failure, restore both files from verified backup bytes in reverse replacement order; leave `prepared` only if restoration itself cannot complete.

```python
def _run_deck_doctor(deck: Path, spec: Path) -> None:
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        result = deck_doctor.main([str(deck), str(spec)])
    if result != 0:
        raise RegenValidationError(output.getvalue().strip())


def _validate_committed_pair(deck: Path, spec: Path) -> None:
    validate_pair(deck, spec)
    _run_deck_doctor(deck, spec)
    result = plan_pair(deck, spec, check_transactions=False)
    if result.status != "no_changes":
        raise RegenValidationError(f"committed pair did not establish a clean baseline: {result.reason_code}")
```

Ensure the initialized state is constructed from the final ID-bearing spec and final slide bytes, then compute `envelopeHash` after inserting a provisional state block; because the envelope masks the entire state block, replacing the provisional value with the final hash is deterministic.

- [ ] **Step 5: Implement exact-set apply and runtime/glossary refusal**

Parse each `--fragment` with `partition("=")`, reject empty/duplicate IDs, and require each path to be a regular non-symlink file. Call `plan_pair()` immediately before staging and require `set(fragment_ids) == set(plan.changed)`.

```python
CAPABILITY_MARKERS = {
    "journey": "premium-journey.js",
    "flow": "premium-flow.js",
    "glossary": "premium-glossary.js",
    "mermaid": "premium-mermaid",
    "theme_homage": "theme-visuals-embed",
}


def _fragment_capabilities(fragment: str) -> set[str]:
    capabilities: set[str] = set()
    if validate_runtime_contract.needs_journey_runtime(fragment):
        capabilities.add("journey")
    if validate_runtime_contract.needs_flow_runtime(fragment):
        capabilities.add("flow")
    if validate_runtime_contract.needs_glossary_runtime(fragment):
        capabilities.add("glossary")
    if re.search(r'\bclass=["\'][^"\']*\bmermaid\b', fragment, re.IGNORECASE):
        capabilities.add("mermaid")
    if re.search(r'\bclass=["\'][^"\']*\bslide--(?:title|divider)\b', fragment, re.IGNORECASE):
        capabilities.add("theme_homage")
    return capabilities


def _deck_capabilities(deck_html: str) -> set[str]:
    return {
        name
        for name, marker in CAPABILITY_MARKERS.items()
        if validate_runtime_contract.marker_present(deck_html, marker) or marker in deck_html
    }


def _fragment_glossary_keys(fragment: str) -> set[str]:
    return set(re.findall(r'\bdata-term\s*=\s*["\']([^"\']+)["\']', fragment, re.IGNORECASE))
```

Parse the deck's `script#glossary` JSON object and allow only existing case-sensitive keys. If a fragment needs a capability outside `_deck_capabilities()` or a glossary key outside the dictionary, return `full_regeneration_required` with `new_runtime_capability` or `new_glossary_key` and exit code `2`. In particular, a fragment that introduces `slide--title` or `slide--divider` requires the existing all-theme `theme-visuals-embed`; partial apply never rebundles or guesses sidecar images.

Validate every fragment against the edited row, splice all replacements, rebuild the state from edited rows and new target section hashes, and assert every non-target section raw byte string equals its pre-apply value. Assert the candidate envelope hash equals the stored baseline envelope before installing the updated state.

- [ ] **Step 6: Publish apply candidates atomically and implement rollback**

Run Deck Doctor against the candidate deck and edited spec before backup creation. Create a one-target apply backup, atomically replace the deck, validate the committed view, and restore the original deck if final validation fails. Do not replace or back up the edited spec during apply.

For rollback, resolve both requested backup and backup root, require `backup.is_relative_to(root)`, reject any symlink in the path from root to backup, load and validate metadata, verify each backup file hash, and require targets to equal `{deck.name}` or `{deck.name, state_spec_basename}` according to operation. Stage verified copies beside their targets. For a two-target restore, write `rollback-metadata.json` as prepared before replacement and committed after validation.

Before resolving either path, validate `--deck` with `lstat()` as an existing regular non-symlink file. Scan for prepared journals first: if one exists, `rollback` must accept only that exact backup directory; a different committed backup must refuse. If more than one prepared journal is found, refuse with exit code `1` and list each directory for manual inspection.

```python
def _safe_backup_directory(deck: Path, requested: Path) -> Path:
    mode = deck.lstat().st_mode
    if stat_module.S_ISLNK(mode) or not stat_module.S_ISREG(mode):
        raise RegenInputError("deck must be a regular non-symlink file")
    deck_parent = deck.resolve().parent
    root = deck_parent / ".partial-regen" / "backups"
    candidate = Path(os.path.abspath(requested))
    if not candidate.is_relative_to(root):
        raise RegenInputError("backup must be beneath the deck backup root")
    cursor = deck_parent
    for part in candidate.relative_to(deck_parent).parts:
        cursor /= part
        if cursor.is_symlink():
            raise RegenInputError("backup path must not contain symlinks")
    if not candidate.is_dir():
        raise RegenInputError("backup directory does not exist")
    if candidate.resolve() != candidate:
        raise RegenInputError("backup path must resolve without redirection")
    return candidate
```

Apply the same `lstat` rule to `metadata.json` and every backup payload before reading them. Reject a symlinked `.partial-regen`, `backups`, backup directory, metadata file, or payload even when its resolved target remains under the root.

After an apply rollback, leave the edited spec unchanged. The next `plan` must report the same changed ID set. After an init rollback, restore both original files and remove regeneration state by restoring the original deck bytes.

Before a two-target rollback, retain same-filesystem staged copies of the current deck/spec. If the second replacement or final hash/Deck Doctor validation fails, restore that pre-rollback view, fsync both files and the parent directory, and leave the rollback journal `prepared` only when this recovery also fails.

- [ ] **Step 7: Run transaction and full feature tests**

Run:

```bash
cd skills/premium-presentations/scripts
python3 -m unittest tests.test_partial_regen
python3 -m unittest tests.test_slide_spec tests.test_slide_html tests.test_slide_map_parsing tests.test_spec_generator
```

Expected: all selected tests pass. Each injected failure test proves exact original bytes, and prepared-journal tests refuse further work until rollback.

- [ ] **Step 8: Commit Task 4**

```bash
git add skills/premium-presentations/scripts/partial_regen.py \
  skills/premium-presentations/scripts/tests/test_partial_regen.py
git commit -m "feat: apply and roll back slide regeneration"
```

---

### Task 5: Claude/Codex guidance, end-to-end validation, and theme-homage regression

**Files:**

- Create: `skills/premium-presentations/scripts/tests/test_partial_regen_e2e.py`
- Modify: `skills/premium-presentations/SKILL.md` at `## Partial Regeneration`
- Modify: `README.md` in the usage/testing sections
- Modify: `skills/premium-presentations/references/runtime.md` in generation and validation guidance
- Modify: `skills/premium-presentations/scripts/tests/test_skill_layout.py`

**Interfaces:**

- Consumes: the public CLI from Task 4, `new-deck.sh`, `deck_doctor.py`, the existing theme discovery/embedded homage contract, and existing Claude/Codex plugin manifests.
- Produces: one documented workflow and one automated compatibility/E2E gate used by both agent environments.

- [ ] **Step 1: Write the failing public-command and documentation tests**

Create an end-to-end unittest that uses a temporary initialized fixture, invokes the CLI through `subprocess.run()`, edits one field, supplies one fragment, and validates the result through the public Deck Doctor command.

```python
class PartialRegenE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def copy_reviewable_fixture(self) -> tuple[Path, Path]:
        source = SKILL_ROOT / "assets" / "examples" / "rag-vector-graph"
        deck = self.root / "rag-vector-graph-slides.html"
        spec = self.root / "rag-vector-graph-slide-spec.md"
        shutil.copy2(source / deck.name, deck)
        shutil.copy2(source / spec.name, spec)
        return deck, spec

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "partial_regen.py"), *arguments],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def fragment_for(self, deck: Path, slide_id: str, new_title: str) -> Path:
        span = next(item for item in parse_slide_spans(deck.read_text(encoding="utf-8")) if item.slide_id == slide_id)
        fragment = span.raw.replace("Retrieval benchmark", new_title)
        path = self.root / f"{slide_id}.html"
        path.write_text(fragment, encoding="utf-8")
        return path

    def test_public_cli_round_trip_preserves_theme_homage_payload(self) -> None:
        deck, spec = self.copy_reviewable_fixture()
        original = deck.read_text(encoding="utf-8")
        start = original.index('<script>\n/* --- theme-visuals-embed --- */')
        end = original.index("</script>", start) + len("</script>")
        homage = original[start:end]
        self.run_cli("init", "--deck", str(deck), "--spec", str(spec), "--apply")
        spec.write_text(spec.read_text().replace("Retrieval benchmark", "Verified retrieval benchmark"), encoding="utf-8")
        plan = self.run_cli("plan", "--deck", str(deck), "--spec", str(spec), "--json")
        payload = json.loads(plan.stdout)
        slide_id = next(iter(payload["changed"]))
        fragment = self.fragment_for(deck, slide_id, "Verified retrieval benchmark")
        self.run_cli("apply", "--deck", str(deck), "--spec", str(spec), "--fragment", f"{slide_id}={fragment}")
        updated = deck.read_text(encoding="utf-8")
        updated_start = updated.index('<script>\n/* --- theme-visuals-embed --- */')
        updated_end = updated.index("</script>", updated_start) + len("</script>")
        self.assertEqual(updated[updated_start:updated_end], homage)
        doctor = subprocess.run([sys.executable, str(SCRIPTS / "deck_doctor.py"), str(deck), str(spec)], text=True, capture_output=True)
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
```

In `test_skill_layout.py`, assert that `SKILL.md`, `README.md`, and `references/runtime.md` all contain `partial_regen.py init`, `partial_regen.py plan`, `partial_regen.py apply`, `partial_regen.py rollback`, `Claude Code`, and `Codex`. Assert the old phrases `row index, confirmed by title` and `stable data-slide-id` are absent.

- [ ] **Step 2: Run E2E/layout tests and verify the red state**

Run:

```bash
cd skills/premium-presentations/scripts
python3 -m unittest tests.test_partial_regen_e2e tests.test_skill_layout
```

Expected: documentation marker assertions fail and the public round trip fails until guidance and fixture helpers are complete.

- [ ] **Step 3: Replace the manual workflow with exact provider-neutral commands**

Use the repository-root form in `README.md`:

```bash
python3 skills/premium-presentations/scripts/partial_regen.py init --deck DECK --spec SPEC
python3 skills/premium-presentations/scripts/partial_regen.py init --deck DECK --spec SPEC --apply
python3 skills/premium-presentations/scripts/partial_regen.py plan --deck DECK --spec SPEC --json
python3 skills/premium-presentations/scripts/partial_regen.py apply --deck DECK --spec SPEC --fragment slide-3=slide-3.html
python3 skills/premium-presentations/scripts/partial_regen.py rollback --deck DECK --backup BACKUP_DIRECTORY
```

Use the skill-root form in `SKILL.md` and `references/runtime.md`, and state the required working directory immediately above it:

```bash
cd skills/premium-presentations
python3 scripts/partial_regen.py init --deck DECK --spec SPEC
python3 scripts/partial_regen.py init --deck DECK --spec SPEC --apply
python3 scripts/partial_regen.py plan --deck DECK --spec SPEC --json
python3 scripts/partial_regen.py apply --deck DECK --spec SPEC --fragment slide-3=slide-3.html
python3 scripts/partial_regen.py rollback --deck DECK --backup BACKUP_DIRECTORY
```

State explicitly:

- Run initialization preview first and review assigned IDs; initialization never runs automatically.
- Claude Code and Codex read the same JSON plan and generate the same one-section fragment contract; the CLI itself does not call either provider.
- Supply every changed ID in one apply operation.
- Insert/delete/reorder, global CSS/runtime/control changes, new glossary keys, and new conditional capabilities require full regeneration.
- Do not hand-edit a baseline deck after initialization; section drift returns exit code `3`.
- Successful apply preserves untargeted slide bytes and all embedded theme homage images; Deck Doctor remains the publication gate.

- [ ] **Step 4: Complete the end-to-end fixture without committing generated artifacts**

Use `assets/examples/rag-vector-graph/` only as a copied temporary fixture. If its spec/deck count or titles are unsuitable, construct the two-slide fixture entirely inside the test temporary directory. Do not initialize or modify a committed example. The test helper must copy or generate files, run public commands, and remove them with `TemporaryDirectory()`.

Add a Playwright smoke phase after the Python round trip using the repository's installed Python Chromium tooling. Open the resulting local file, iterate every embedded theme, and assert each role and injected visual stays on an embedded WebP URI:

```python
console_errors: list[str] = []
failed_requests: list[str] = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("requestfailed", lambda request: failed_requests.append(request.url))
    page.goto(deck.as_uri(), wait_until="load")
    themes = page.evaluate("Object.keys(window.PremiumThemeVisuals).sort()")
    for theme in themes:
        result = page.evaluate(
            """theme => {
                window.PremiumPresentations.setTheme(theme);
                const payload = window.PremiumThemeVisuals[theme];
                const images = [...document.querySelectorAll('.theme-visual__image')]
                    .map(image => image.getAttribute('src') || '');
                return {payload, images};
            }""",
            theme,
        )
        self.assertTrue(result["payload"]["hero"].startswith("data:image/webp;base64,"))
        self.assertTrue(result["payload"]["map"].startswith("data:image/webp;base64,"))
        self.assertGreaterEqual(len(result["images"]), 2)
        self.assertTrue(all(source.startswith("data:image/webp;base64,") for source in result["images"]))
    page.locator("#premium-controls-tab").click()
    self.assertEqual(page.locator("#premium-controls-tab").get_attribute("aria-expanded"), "true")
    self.assertTrue(page.locator("#premium-controls-panel").count())
    self.assertEqual(page.evaluate("typeof window.PremiumPresenter"), "object")
    browser.close()
self.assertEqual(console_errors, [])
self.assertEqual(failed_requests, [])
```

Capture console errors and failed network requests; both lists must remain empty after navigation, theme switching, and opening presenter controls.

- [ ] **Step 5: Run focused and aggregate verification**

Run from `skills/premium-presentations/scripts`:

```bash
python3 -m unittest tests.test_partial_regen_e2e tests.test_skill_layout
python3 -m unittest discover -s tests
npm run test:all
python3 validate_runtime_contract.py
python3 validate_contrast.py
claude plugin validate ../../.. --strict
validator="$(mktemp)"
curl --fail --silent --show-error --location "https://raw.githubusercontent.com/openai/codex/2e8c3756f95789c215d9ea9a5ade6ec377934b3f/codex-rs/skills/src/assets/samples/plugin-creator/scripts/validate_plugin.py" --output "$validator"
python3 -c 'import hashlib,pathlib,sys; expected="ebda00d55d7518b127f675f062fb5c6e7a1ffdc0a99df1a55ac594400d7d3228"; actual=hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest(); raise SystemExit(0 if actual == expected else 1)' "$validator"
python3 "$validator" ../../..
rm -f "$validator"
npm audit
git diff --check
```

Expected: every command exits `0`; Python discovery includes all three new test modules; the Chromium smoke has zero console/network errors; Claude Code and Codex validators pass; every `window.PremiumThemeVisuals` hero/map value remains an embedded data URI after partial regeneration.

- [ ] **Step 6: Commit Task 5**

```bash
git add skills/premium-presentations/scripts/tests/test_partial_regen_e2e.py
git add -p skills/premium-presentations/SKILL.md \
  README.md \
  skills/premium-presentations/references/runtime.md \
  skills/premium-presentations/scripts/tests/test_skill_layout.py
git diff --cached --check
git commit -m "docs: add provider-neutral partial regeneration workflow"
```

---

### Task 6: Independent review and final integration gate

**Files:**

- Review: all files changed by Tasks 1-5
- Modify only when a reviewer identifies a concrete defect in those files

**Interfaces:**

- Consumes: the approved design, all task commits, and fresh verification output.
- Produces: reviewed implementation with requirement traceability and no uncommitted generated fixtures.

- [ ] **Step 1: Dispatch two-stage review through the execution workflow**

Use `superpowers:subagent-driven-development` to give a fresh spec-compliance reviewer the approved design and task diff. Require findings to cite a file and requirement. After corrections, give a different code-quality reviewer the same diff and current test output. The primary agent integrates fixes and keeps reviewer write scopes read-only.

- [ ] **Step 2: Audit requirement coverage and repository cleanliness**

Run:

```bash
rg -n "premium-regen-state|identity_order_changed|new_runtime_capability|new_glossary_key|section_hash_changed" \
  skills/premium-presentations/scripts/partial_regen.py \
  skills/premium-presentations/scripts/tests/test_partial_regen.py
git status --short
git diff --check
```

Expected: every stable state/reason marker appears in production and tests; only intentional source/docs changes remain; no temporary deck, fragment, backup, journal, browser artifact, or generated fixture is tracked.

- [ ] **Step 3: Run the final clean verification gate**

Run:

```bash
cd skills/premium-presentations/scripts
npm run test:all
python3 validate_runtime_contract.py
python3 validate_contrast.py
claude plugin validate ../../.. --strict
validator="$(mktemp)"
curl --fail --silent --show-error --location "https://raw.githubusercontent.com/openai/codex/2e8c3756f95789c215d9ea9a5ade6ec377934b3f/codex-rs/skills/src/assets/samples/plugin-creator/scripts/validate_plugin.py" --output "$validator"
python3 -c 'import hashlib,pathlib,sys; expected="ebda00d55d7518b127f675f062fb5c6e7a1ffdc0a99df1a55ac594400d7d3228"; actual=hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest(); raise SystemExit(0 if actual == expected else 1)' "$validator"
python3 "$validator" ../../..
rm -f "$validator"
npm audit
git diff --check
```

Expected: every command exits `0`. Record the Python test count, browser-smoke result, and both plugin-validator results in the final handoff.

- [ ] **Step 4: Commit reviewer-approved corrections, if any**

Stage only files changed to address cited findings and use:

```bash
git add -p
git diff --cached --check
git commit -m "fix: harden partial regeneration workflow"
```

If review requires no corrections, do not create an empty commit.
