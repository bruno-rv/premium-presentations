# Premium Presentations

Project-local Claude skill for generating, editing, validating, and bundling
premium HTML slide decks.

Repository: [bruno-rv/premium-presentations.git](https://github.com/bruno-rv/premium-presentations.git)

## Current Shape

This repository is intentionally small at the root. The actual skill lives in
one project-skill directory:

```text
.claude/skills/premium-presentations/
```

Root files are only repository-level material:

| Path | Purpose |
|------|---------|
| `.claude/skills/premium-presentations/` | Canonical Claude project skill |
| `README.md` | Repository orientation |
| `LICENSE` | License |
| `.gitignore` | Local cache and vendor-mirror ignores |

There are no root-level `scripts/`, `references/`, `assets/`, `templates/`,
`shared/`, or `decks/` folders. Those are all bundled inside the skill.

## Skill Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Skill metadata and compact operating instructions |
| `references/` | Progressive-disclosure guidance for design, runtime, themes, examples, and components |
| `scripts/` | Deterministic scaffold, bundle, validation, OG cover, and smoke-test tooling |
| `assets/shared/` | Runtime CSS, JavaScript, theme visuals, red mark, and slide engine |
| `assets/templates/` | Base templates, theme previews, diagram snippet, and component snippets |
| `assets/decks/` | Existing complete deck examples and generated deck outputs |
| `assets/studio/` | Local gallery for previews and example decks |

## Generation Fidelity

Yes: the skill is capable of generating new presentations with the same
features, design language, themes, and runtime behavior as the existing decks in
this repo.

It does this by using the same source of truth as the existing presentations:

- `assets/shared/premium-themes.css` for discovered themes
- `assets/shared/*.css` and `assets/shared/*.js` for runtime behavior
- `assets/templates/*.html` for base deck structure
- `assets/templates/components/*.snippet.html` for reusable visual patterns
- `assets/decks/*` as examples and regression corpus
- `references/*.md` for progressive guidance when more detail is needed

What "same" means here:

| Capability | Status |
|------------|--------|
| Same themes | Yes. Themes are discovered dynamically from `premium-themes.css`; current themes are `editorial`, `warm`, and `red`. |
| Same visual system | Yes. New decks use the bundled templates, component snippets, typography, spacing, controls, and theme visuals. |
| Same runtime features | Yes. New decks use the shared SlideEngine, presenter mode, timer, search, clicker, TTS, annotations, Mermaid handling, and export controls. |
| Same validation | Yes. Decks are checked by the bundled validators and runtime-contract tests. |
| Same exact content | Only when the user provides the source deck, slide spec, or exact content brief. The skill preserves the framework; it does not infer missing subject matter perfectly from nothing. |
| Byte-identical HTML | Not guaranteed for new decks. The expected guarantee is feature and design parity, not byte-for-byte cloning. |

## Existing Decks

The bundled examples live under:

```text
.claude/skills/premium-presentations/assets/decks/
```

Current examples:

- `graph-databases`
- `rag-vector-graph`
- `red-smoke`
- `vector-databases`
- `vector-vs-graph`

These decks are useful as examples, design references, and validation fixtures.

## Runtime Features

Generated decks keep the Premium Presentations runtime stack:

- Theme switching
- 3D/parallax background toggle
- Marker, laser, clear, and hidden controls panel
- Scroll-snap SlideEngine navigation
- Presenter popup with notes
- Speaker timer
- Search and slide jump
- Clicker/WebHID support with keyboard fallback
- TTS read-aloud
- Export/PDF and OG cover support
- Mermaid diagrams with theme-aware rendering and diagram-fit validation
- Red theme chrome and red brand assets when using the red theme

## Quick Start

Run commands from the skill directory:

```bash
cd .claude/skills/premium-presentations

./scripts/list-themes.py
./scripts/new-deck.sh warm my-talk "My Title" 12
./scripts/validate-deck.sh assets/decks/my-talk/my-talk-slides.html

open assets/studio/index.html
open assets/decks/my-talk/my-talk-slides.html
```

Serve locally if Mermaid or browser security restrictions affect `file://`:

```bash
python3 -m http.server 8765
# http://localhost:8765/assets/decks/my-talk/my-talk-slides.html
```

## Create Or Edit A Deck

Use the skill as the source of truth:

1. Start from `scripts/new-deck.sh`.
2. Pick a theme returned by `scripts/list-themes.py`.
3. Edit the generated HTML under `assets/decks/<slug>/`.
4. Use `references/design.md`, `references/runtime.md`, and
   `references/components.md` only when the task needs that detail.
5. Reuse snippets from `assets/templates/components/`.
6. Validate before treating the deck as ready.

For decks with 8 or more requested slides, `new-deck.sh` also creates a slide
spec. The initial scaffold validates structurally, but the spec validation is
expected to pass only after the deck has been authored to the planned slide
count.

## Validation

Run from `.claude/skills/premium-presentations/`:

```bash
./scripts/validate-runtime-contract.py
npm --prefix scripts test
npm --prefix scripts run test:presenter
```

Validate a specific deck:

```bash
./scripts/validate-deck.sh assets/decks/<slug>/<slug>-slides.html
```

After shared runtime or template changes, re-bundle affected decks and rerun the
runtime contract:

```bash
python3 scripts/bundle_deck.py assets/decks/<slug>/<slug>-slides.html --in-place --force
./scripts/validate-runtime-contract.py
```

## Packaging

For Claude Code, this repo already contains the project skill at:

```text
.claude/skills/premium-presentations/SKILL.md
```

For Claude.ai upload, zip the skill directory itself, not the repository root:

```text
premium-presentations.zip
└── premium-presentations/
    ├── SKILL.md
    ├── scripts/
    ├── references/
    └── assets/
```

The folder name must stay `premium-presentations`, matching the `name` field in
`SKILL.md`.
