# Premium Presentations

Claude skill for generating polished, browser-rendered HTML presentation decks.

This repository is the skill package. `SKILL.md` is the agent entry point;
`README.md` is only human-facing orientation.

## Install

Clone or copy this folder into your Claude skills directory:

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/bruno-rv/premium-presentations.git ~/.claude/skills/premium-presentations
```

For local validation scripts that use Node dependencies:

```bash
npm --prefix scripts ci
```

## Use

List available themes:

```bash
./scripts/list-themes.py
```

Create a deck:

```bash
./scripts/new-deck.sh warm my-talk "My Title" 12
```

The generated deck is written to:

```text
assets/decks/my-talk/my-talk-slides.html
```

Validate it:

```bash
./scripts/validate-deck.sh assets/decks/my-talk/my-talk-slides.html assets/decks/my-talk/my-talk-slide-spec.md
```

Open the studio:

```bash
open assets/studio/index.html
```

## Layout

```text
premium-presentations/
├── SKILL.md
├── README.md
├── assets/
│   ├── shared/
│   ├── studio/
│   └── templates/
├── references/
└── scripts/
```

`assets/` contains bundled resources used by generated output: runtime CSS/JS,
theme visuals, templates, snippets, and the studio page. The key committed
paths are `assets/shared/`, `assets/studio/`, and `assets/templates/`.

`assets/decks/` is generated output from `scripts/new-deck.sh`. It is ignored
by git and should stay out of the package unless a user explicitly asks to
commit a finished deck.

`references/` contains one-level agent guidance loaded only when needed:
runtime details, design rules, component patterns, examples, theme notes, and
the slide-spec template.

`scripts/` contains deterministic tooling for scaffolding, bundling, testing,
and validation.

## Validate The Skill

```bash
python3 scripts/test_skill_layout.py
python3 scripts/test_runtime_contract.py
python3 scripts/validate-runtime-contract.py
node --test scripts/theme-quality.test.mjs
npm --prefix scripts run test:presenter
git diff --check
```

Create and validate a smoke deck:

```bash
./scripts/new-deck.sh editorial smoke-deck "Smoke Deck" 2
./scripts/validate-deck.sh assets/decks/smoke-deck/smoke-deck-slides.html
rm -rf assets/decks/smoke-deck
```
