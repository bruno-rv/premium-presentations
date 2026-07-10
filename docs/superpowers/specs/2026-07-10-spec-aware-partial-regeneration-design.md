# Spec-aware partial regeneration design

Date: July 10, 2026
Status: Approved in conversation; awaiting written-spec review

## Objective

Add a provider-neutral CLI that lets Claude Code or Codex regenerate one or
more existing slides from edited Slide Map rows without rebuilding the whole
deck. The CLI must preview changes, detect drift, preserve every unchanged
slide byte-for-byte, create backups, and publish only a Deck Doctor-clean
candidate.

The repository has no deterministic spec-to-HTML compiler. Agents continue to
author slide fragments. The CLI provides deterministic identity, planning,
patching, and validation around those fragments.

## Scope

The first release supports replacements of existing slides only.

It defers these changes to full regeneration:

- Slide insertion or deletion.
- Slide reordering.
- New deck-level or global structures.
- A conditional runtime module that the current standalone deck doesn't carry.
- New glossary keys that require a dictionary update.

The CLI never invokes a model and requires no provider API key. Claude Code and
Codex use the same commands and file contracts.

## Approaches considered

### Embedded regeneration manifest

This is the selected approach. A non-executable JSON block inside the deck
stores stable identity, canonical baseline rows, and section hashes. The state
can't be separated from the standalone deck, and the CLI can prove baseline
drift without Git.

### Sidecar state

A sidecar JSON file keeps the deck cleaner, but it can be lost, copied with the
wrong deck, or drift from the distributed HTML. This weakens the standalone
contract.

### Git baseline

A Git comparison needs little new metadata, but generated decks are ignored and
often have no committed predecessor. It isn't a reliable baseline.

## Architecture

Create three focused Python modules under
`skills/premium-presentations/scripts/`.

### `slide_spec.py`

Parse Slide Map tables by normalized header name rather than fixed column
positions. Support legacy 5- and 7-column tables, the current 9-column table,
and the new table with an `ID` column. Preserve unknown future columns in the
canonical field mapping. Parse escaped Markdown pipes without using a plain
`str.split("|")`.

Expose these immutable models and deterministic operations:

```python
@dataclass(frozen=True)
class SlideSpecRow:
    slide_id: str
    ordinal: int
    fields: Mapping[str, str]
    line_no: int
    raw_line: str

parse_slide_map(text: str, *, require_ids: bool = False) -> SlideSpec
canonical_row(row: SlideSpecRow) -> bytes
diff_rows(baseline: SlideSpec, edited: SlideSpec) -> SpecDiff
```

Canonical rows exclude presentation-only Markdown spacing but include every
semantic column except `#` and `ID`. Hash canonical bytes with SHA-256.

### `slide_html.py`

Parse authored `<section class="slide">` elements with `html.parser` raw-text
semantics while retaining exact character offsets. Track nested sections,
templates, scripts, comments, and closing tags. Don't use regular expressions
to determine section boundaries.

Expose these operations:

```python
@dataclass(frozen=True)
class SlideSpan:
    slide_id: str
    title: str
    start: int
    end: int
    raw: str

parse_slide_spans(html: str) -> list[SlideSpan]
validate_fragment(fragment: str, expected: SlideSpecRow) -> list[str]
splice_sections(html: str, replacements: Mapping[str, str]) -> str
```

Apply replacements in descending offset order. This keeps all text outside the
target spans byte-for-byte identical.

### `partial_regen.py`

Provide the public `init`, `plan`, `apply`, and `rollback` commands. Coordinate
the two parsers, embedded state, backup management, candidate validation, and
transactional replacement. Keep model-generated content outside this module.

## Stable identity

Add `ID` immediately after `#` in the Slide Map. Use that exact ID as the
section's real DOM `id`; don't add a second `data-slide-id` identity.

IDs must:

- Match `[A-Za-z0-9_-]{1,128}`.
- Be unique in both the spec and deck.
- Remain unchanged when a title or content field changes.
- Remain unchanged until a full-regeneration workflow deliberately replaces
  the deck.

During explicit initialization, preserve a valid existing section ID at the
same ordinal. Generate a missing ID as `slide-N`, where `N` is the 1-based
initial ordinal. Reject conflicting, duplicate, malformed, or count-mismatched
inputs instead of guessing.

Update newly generated Slide Map rows to include deterministic IDs. A scaffold
isn't initialized until its fully authored deck has the same number and order
of sections as the spec.

## Embedded state

Add one non-executable block outside `#deck`:

```html
<script type="application/json" id="premium-regen-state">
{
  "version": 1,
  "deck": "lesson-slides.html",
  "spec": "lesson-slide-spec.md",
  "order": ["slide-1", "slide-2"],
  "envelopeHash": "sha256:57f5a4f2923f23c962c4b6f8d4577f7f8ef7c0c7a6e93f22c72e1fd6389ec728",
  "slides": {
    "slide-1": {
      "row": {
        "Title": "Opening",
        "Key Content": "Explain the retrieval change"
      },
      "rowHash": "sha256:423f4f89d47d12f4b46c8b18f45af4ad0f2b7a08ce91b68a686b1534054202d7",
      "sectionHash": "sha256:bb14edc7f17585f5f87bc4af046a745a093f168a8a19c1c742e9fcb47a629bce"
    }
  }
}
</script>
```

Store basenames only, never absolute paths. Serialize deterministically and
escape `<` as `\u003c` so row content can't terminate the script block. The
block contains no executable JavaScript. Compute `envelopeHash` over the full
HTML after replacing every authored slide span and the manifest block with
stable sentinels. This detects deck-level changes without treating a planned
slide replacement or manifest refresh as global drift.

## CLI workflow

### Initialize

```bash
python3 scripts/partial_regen.py init --deck DECK --spec SPEC
python3 scripts/partial_regen.py init --deck DECK --spec SPEC --apply
```

The default command is read-only. It prints the proposed ID assignments and
manifest changes. It refuses a deck that already has valid regeneration state
and directs the user to `plan`.

Require the deck and spec to be regular, non-symlink files in the same resolved
directory. This keeps staging, replacement, and backup recovery on one
filesystem.

With `--apply`, the command:

1. Validates the current deck/spec pair.
2. Stages updated deck and spec siblings.
3. Adds the `ID` column, section IDs, and embedded manifest.
4. Creates a backup directory containing the original deck, spec, and backup
   metadata.
5. Validates the staged pair.
6. Replaces both targets with rollback if any replacement or final validation
   fails.

### Plan

```bash
python3 scripts/partial_regen.py plan --deck DECK --spec SPEC
python3 scripts/partial_regen.py plan --deck DECK --spec SPEC --json
```

`plan` is always read-only. It compares the edited spec with the embedded
baseline and reports each changed ID and field. It separately verifies current
section hashes, identity sets, and order.

The human output guides an agent. The JSON output uses stable status strings,
changed IDs, changed fields, and refusal reasons. `plan` doesn't create fragment
files or mutate state.

### Apply

```bash
python3 scripts/partial_regen.py apply \
  --deck DECK \
  --spec SPEC \
  --fragment slide-3=fragments/slide-3.html \
  --fragment slide-7=fragments/slide-7.html
```

Claude Code or Codex writes one fragment for every ID reported by `plan`.
`apply` requires the fragment ID set to equal the planned change set. It doesn't
permit partial application of an edited spec because that would leave the spec
and deck semantically inconsistent.

Each fragment must:

- Contain exactly one slide `<section>` and no surrounding document markup.
- Use the expected stable DOM `id`.
- Set `data-nav-title` to the exact decoded `Title` field.
- Contain no `<script>`, `<style>`, `<link>`, or deck-level controls.
- Contain exactly one direct `aside.notes` as its final element.
- Use only conditional runtime capabilities already present in the deck.
- Use only glossary keys already present in the deck dictionary.

`apply` verifies the baseline again immediately before staging. It splices
fragments into a sibling candidate, updates baseline rows and hashes in the
manifest, proves unchanged section hashes are identical, and runs Deck Doctor
against the edited spec. Only then does it create a timestamped backup and use
`os.replace` to publish the candidate.

### Roll back

```bash
python3 scripts/partial_regen.py rollback --deck DECK --backup BACKUP_DIRECTORY
```

Write backups beneath
`DECK.parent/.partial-regen/backups/<UTC-timestamp>/`. Each directory contains
a metadata file that lists its exact targets and SHA-256 hashes. An
initialization backup lists the deck and spec; an apply backup lists only the
deck. Rollback restores exactly the listed files, stages and verifies their
hashes, and rolls back its own replacements if an error occurs. Rolling back an
apply intentionally leaves the edited spec in place, so the next `plan` reports
the same required regeneration.

Backup metadata stores target basenames only. Rollback accepts only backup
directories beneath the deck's resolved `.partial-regen/backups/` root and
refuses symlinks, path traversal, unexpected targets, or hash mismatches.

## Refusal and error handling

Return an actionable human message for every refusal. `--json` output uses a
stable status and reason code.

Use these process exit codes:

- `0`: Successful preview, no changes, successful mutation, or successful
  rollback.
- `1`: Invalid input, malformed fragment/state, validation error, or I/O error.
- `2`: Full regeneration required because of structural or runtime changes.
- `3`: Baseline drift; restore the expected deck backup or use full
  regeneration before applying.

Require full regeneration for:

- Added, removed, duplicated, or reordered IDs.
- Changed slide count or spec/deck identity order.
- A changed global envelope hash.
- A new conditional runtime module that the deck doesn't already contain.
- A new glossary key that requires global dictionary changes.
- Deck-level CSS, scripts, controls, or global markup.

Treat a current section hash mismatch as baseline drift, not as a changed spec
row. Never overwrite manual deck edits silently.

Every mutation is fail-closed. Backup creation, candidate creation, fragment
validation, Deck Doctor, replacement, and final committed-view validation can
all fail without leaving a partial target update.

`apply` publishes one deck file with an atomic `os.replace`. Initialization and
initialization rollback update two files, so they also maintain a durable
transaction journal in the backup directory. Mark the journal `prepared`
before the first replacement and `committed` after final validation. Every CLI
command checks for a prepared transaction and refuses further work until
`rollback` restores the recorded backup. This makes interruption recovery
explicit even though two filesystem paths can't be crash-atomic together.

## Integration

- Reuse `slide_spec.py` from `validate_deck.py` for Slide Map parsing and count
  validation so the CLI and canonical validator can't disagree.
- Update `spec_generator.py` and the Slide Map template to emit the `ID` column.
- Replace the manual index-and-title partial-regeneration section in `SKILL.md`
  with the CLI workflow.
- Document the same provider-neutral commands in `README.md` and runtime
  references for Claude Code and Codex.
- Register new tests through existing Python unittest discovery and the
  aggregate `npm run test:all` command.
- Use temporary fixtures for parser and rollback tests. Initialize a committed
  example only if the resulting diff remains reviewable and validates cleanly.

## Testing strategy

Follow test-driven development. Every production behavior starts with a failing
test.

### Spec parser

- Parse legacy 5- and 7-column tables, the current 9-column table, and the new
  ID format.
- Parse escaped pipes and preserve unknown columns.
- Reject missing, duplicate, malformed, or reordered IDs when required.
- Produce deterministic canonical bytes and hashes.

### HTML parser and fragments

- Extract exact slide spans with nested sections, scripts, templates, comments,
  and slide-adjacent whitespace.
- Preserve every non-target slice byte-for-byte.
- Reject wrong IDs or titles, multiple sections, missing or misplaced notes,
  and forbidden global tags.

### Initialization and planning

- Prove default initialization is read-only.
- Preserve existing valid IDs and generate deterministic missing IDs.
- Create an exact deck/spec backup before mutation.
- Detect one-row and multi-row changes.
- Refuse inserts, deletes, reorders, count mismatches, and baseline drift.

### Apply and rollback

- Apply one and multiple replacements.
- Require the exact planned fragment set.
- Reject new runtime dependencies and glossary keys.
- Prove unchanged sections remain byte-identical.
- Inject backup, Deck Doctor, replacement, and final-validation failures and
  prove original files remain byte-identical.
- Restore init and apply backups according to their metadata.

### Compatibility and regression

- Run the full aggregate suite.
- Run runtime, contrast, Claude Code, and Codex plugin validators.
- Create and initialize a temporary deck, edit one spec row, plan, generate a
  fixture fragment, apply it, and open the result in Chromium.
- Verify theme switching, embedded homage images, presenter controls, and zero
  console or network portability errors after partial regeneration.

## Success criteria

The feature is complete when:

- An existing valid deck can be explicitly initialized without losing bytes
  outside the added IDs and manifest.
- An edited replacement-only spec produces a deterministic read-only plan.
- Claude Code and Codex can supply the same fragment contract.
- Apply changes only targeted sections and embedded state.
- Structural, global, runtime, and drift hazards fail closed.
- Every successful mutation has a verifiable rollback path.
- Deck Doctor and the full repository suite pass on the final candidate.
