# Premium Presentations

Claude project skill for generating, editing, validating, and bundling premium
HTML slide decks with shared themes, presenter mode, Mermaid diagrams, runtime
controls, and example decks.

Repository: [bruno-rv/premium-presentations.git](https://github.com/bruno-rv/premium-presentations.git)

## Skill Location

The canonical skill is checked in at:

```text
.claude/skills/premium-presentations/
```

This follows Claude Code's project skill convention:
`.claude/skills/<skill-name>/SKILL.md`.

For Claude.ai upload, zip the `premium-presentations/` skill directory itself,
not the repository root:

```text
premium-presentations.zip
└── premium-presentations/
    ├── SKILL.md
    ├── scripts/
    ├── references/
    └── assets/
```

## Quick Start

Run commands from `.claude/skills/premium-presentations/`:

```bash
cd .claude/skills/premium-presentations

./scripts/list-themes.py
./scripts/new-deck.sh warm my-talk "My Title" 12
./scripts/validate-deck.sh assets/decks/my-talk/my-talk-slides.html

open assets/studio/index.html
open assets/decks/my-talk/my-talk-slides.html
```

Serve locally if Mermaid fails on `file://`:

```bash
python3 -m http.server 8765
# http://localhost:8765/assets/decks/my-talk/my-talk-slides.html
```

## Skill Structure

| Path | Necessary? | Decision |
|------|------------|----------|
| `.claude/skills/premium-presentations/SKILL.md` | Yes | Skill entrypoint and trigger metadata. |
| `.claude/skills/premium-presentations/references/` | Yes | Progressive-disclosure design/runtime/component guidance. |
| `.claude/skills/premium-presentations/scripts/` | Yes | Deterministic scaffold, bundle, validation, cover, and smoke-test tooling. |
| `.claude/skills/premium-presentations/assets/shared/` | Yes | Runtime CSS, JavaScript, theme visuals, and brand assets used by generated decks. |
| `.claude/skills/premium-presentations/assets/templates/` | Yes | Base decks, theme previews, and reusable component snippets. |
| `.claude/skills/premium-presentations/assets/decks/` | Yes | Complete example decks and generated deck output. |
| `.claude/skills/premium-presentations/assets/studio/` | Yes | Local gallery for previews and examples. |
| `README.md` | Yes | Repository-level orientation only; not part of the skill payload. |
| `LICENSE` | Yes | Repository license. |
| `.gitignore` | Yes | Keeps local/vendor caches out while allowing this Claude skill to be tracked. |
| Root `agents/` | No | Removed; OpenAI/Codex metadata is not needed for a single Claude project skill. |
| Root `scripts/`, `references/`, `assets/`, `templates/`, `shared/`, `decks/` | No | Moved under the single Claude skill to avoid root clutter. |

## Validation

Run from `.claude/skills/premium-presentations/`:

```bash
./scripts/validate-runtime-contract.py
npm --prefix scripts test
npm --prefix scripts run test:presenter
```

Use `./scripts/validate-deck.sh assets/decks/<slug>/<slug>-slides.html` for a
specific deck.
