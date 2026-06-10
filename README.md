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
python3 scripts/validate_deck.py assets/decks/my-talk/my-talk-slides.html assets/decks/my-talk/my-talk-slide-spec.md
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

`scripts/` contains deterministic tooling for scaffolding, bundling, and
validation. Its test suite lives in `scripts/tests/`.

## Validate The Skill

These commands test the skill package itself (deck-output validation lives in
`SKILL.md`):

```bash
python3 scripts/tests/test_skill_layout.py
python3 scripts/tests/test_runtime_contract.py
python3 scripts/validate_runtime_contract.py
npm --prefix scripts test
npm --prefix scripts run test:presenter
npm --prefix scripts run test:popup
git diff --check
```

Create and validate a smoke deck:

```bash
./scripts/new-deck.sh editorial smoke-deck "Smoke Deck" 2
python3 scripts/validate_deck.py assets/decks/smoke-deck/smoke-deck-slides.html
rm -rf assets/decks/smoke-deck
```
