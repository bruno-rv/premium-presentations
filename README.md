# Premium Presentations

Claude skill for generating polished, browser-rendered HTML presentation decks.

This repo is the Claude Code plugin package and the skill source. `SKILL.md` is the agent entry point; `README.md` is human-facing orientation only.

## Preview

**Title slide** — Editorial dark theme with ambient 3D visual, slide rail, and tool panel:

![Title slide](docs/screenshot-title.png)

**Content slide** — Cupertino light theme with pipeline step layout:

![Content slide](docs/screenshot-slide.png)

**Presenter view** — Dual-pane popup with current/next slide preview, expanded speaker notes, and a configurable countdown timer (set any duration from the tool panel, or define a default in deck settings):

![Presenter view](docs/screenshot-presenter.png)

## Install

### Claude Code plugin (recommended)

Add to `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "premium-presentations": {
      "source": { "source": "github", "repo": "bruno-rv/premium-presentations" }
    }
  },
  "enabledPlugins": {
    "premium-presentations@premium-presentations": true
  }
}
```

### Manual

Clone the repo and link the skill subdirectory:

```bash
git clone https://github.com/bruno-rv/premium-presentations.git
mkdir -p ~/.claude/skills
ln -s "$(pwd)/premium-presentations/skills/premium-presentations" ~/.claude/skills/premium-presentations
```

For local validation scripts that use Node dependencies:

```bash
npm --prefix skills/premium-presentations/scripts ci
```

For browser-rendering checks, install the Python validation dependency and its
managed Chromium once:

```bash
python3 -m pip install -r skills/premium-presentations/scripts/requirements.txt
python3 -m playwright install chromium
```

`scripts/og-cover.sh` uses a system Chrome/Chromium binary (`chromium`,
`google-chrome`, or macOS Google Chrome). Install one of those if you need the
sidecar `og-cover.png` helper.

## Use

List available themes:

```bash
./skills/premium-presentations/scripts/list-themes.py
```

Create a deck:

```bash
./skills/premium-presentations/scripts/new-deck.sh warm my-talk "My Title" 12
```

The generated deck is written to:

```text
skills/premium-presentations/assets/decks/my-talk/my-talk-slides.html
```

Validate it:

```bash
python3 skills/premium-presentations/scripts/validate_deck.py \
  skills/premium-presentations/assets/decks/my-talk/my-talk-slides.html \
  skills/premium-presentations/assets/decks/my-talk/my-talk-slide-spec.md
```

Generate an optional social/cover image next to the deck:

```bash
./skills/premium-presentations/scripts/og-cover.sh \
  skills/premium-presentations/assets/decks/my-talk/my-talk-slides.html
```

The cover is a sidecar file. The standalone deck HTML does not reference it
automatically.

Open the studio:

```bash
open skills/premium-presentations/assets/studio/index.html
```

## Layout

```text
premium-presentations/          ← repo root
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── docs/                       ← screenshots for this README
├── skills/
│   └── premium-presentations/  ← skill root (SKILL.md entry point)
│       ├── SKILL.md
│       ├── assets/
│       │   ├── shared/         ← runtime CSS/JS, theme visuals
│       │   ├── studio/
│       │   └── templates/
│       ├── references/
│       └── scripts/
├── LICENSE
└── README.md
```

`assets/` contains bundled resources used by generated output: runtime CSS/JS,
theme visuals, templates, snippets, and the studio page. Generated decks are
portable standalone HTML bundles: runtime search, diagrams, PNG export,
presenter mode, controls, and theme assets do not require CDNs or remote fonts.
The key committed paths are `assets/shared/`, `assets/studio/`, and
`assets/templates/`.

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
python3 skills/premium-presentations/scripts/tests/test_skill_layout.py
python3 skills/premium-presentations/scripts/tests/test_runtime_contract.py
python3 skills/premium-presentations/scripts/validate_runtime_contract.py
npm --prefix skills/premium-presentations/scripts test
npm --prefix skills/premium-presentations/scripts run test:presenter
npm --prefix skills/premium-presentations/scripts run test:popup
git diff --check
```

Create and validate a smoke deck:

```bash
./skills/premium-presentations/scripts/new-deck.sh editorial smoke-deck "Smoke Deck" 2
python3 skills/premium-presentations/scripts/validate_deck.py \
  skills/premium-presentations/assets/decks/smoke-deck/smoke-deck-slides.html
rm -rf skills/premium-presentations/assets/decks/smoke-deck
```
