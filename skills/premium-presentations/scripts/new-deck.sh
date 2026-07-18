#!/usr/bin/env bash
# Scaffold a Premium Presentations HTML deck.
# Usage: ./scripts/new-deck.sh <theme> <slug> "<title>" [slide_count]
#
# Examples:
#   ./scripts/list-themes.py
#   ./scripts/new-deck.sh warm my-talk "My Talk" 15

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRAMEWORK="${1:-}"
SLUG="${2:-}"
TITLE="${3:-}"
COUNT="${4:-10}"

usage() {
  sed -n '2,7p' "$0" | tail -n +2
  exit 1
}

[[ -z "$FRAMEWORK" || -z "$SLUG" || -z "$TITLE" ]] && usage

THEMES=()
while IFS= read -r theme; do
  [[ -n "$theme" ]] && THEMES+=("$theme")
done < <(python3 "$ROOT/scripts/list-themes.py")
if [[ "${#THEMES[@]}" -eq 0 ]]; then
  echo "No themes found in assets/shared/premium-themes.css" >&2
  exit 1
fi
if ! printf '%s\n' "${THEMES[@]}" | grep -Fxq "$FRAMEWORK"; then
  echo "Theme must be one of: ${THEMES[*]}" >&2
  exit 1
fi

if [[ ! "$SLUG" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  echo "Slug must be lowercase alphanumeric with hyphens" >&2
  exit 1
fi

if ! [[ "$COUNT" =~ ^[0-9]+$ ]] || [[ "$COUNT" -lt 1 ]]; then
  echo "slide_count must be a positive integer" >&2
  exit 1
fi

DECKS_DIR="$ROOT/assets/decks"
DECK_DIR="$DECKS_DIR/$SLUG"
THEME_TEMPLATE="$ROOT/assets/templates/${FRAMEWORK}-base.html"
if [[ -f "$THEME_TEMPLATE" ]]; then
  TEMPLATE="$THEME_TEMPLATE"
else
  TEMPLATE="$ROOT/assets/templates/premium-base.html"
fi

if [[ -e "$DECK_DIR" ]]; then
  echo "Deck already exists: $DECK_DIR" >&2
  exit 1
fi

mkdir -p "$DECKS_DIR"
STAGING_DIR="$(mktemp -d "$DECKS_DIR/.${SLUG}.staging.XXXXXX")"
cleanup() {
  if [[ -n "${STAGING_DIR:-}" && -d "$STAGING_DIR" ]]; then
    rm -rf -- "$STAGING_DIR"
  fi
}
trap cleanup EXIT HUP INT TERM

SLIDES_FILE="$STAGING_DIR/${SLUG}-slides.html"
SPEC_FILE="$STAGING_DIR/${SLUG}-slide-spec.md"

python3 "$ROOT/scripts/render_template.py" "$TEMPLATE" "$SLIDES_FILE" \
  --var THEME "$FRAMEWORK" \
  --var TITLE "$TITLE" \
  --var SHARED "../../shared/" \
  --var BAR_RIGHT ""

python3 "$ROOT/scripts/bundle_deck.py" "$SLIDES_FILE" --in-place
python3 "$ROOT/scripts/validate_deck.py" "$SLIDES_FILE"

if [[ "$COUNT" -ge 8 ]]; then
  SPEC_TEMPLATE="$ROOT/references/slide-spec-template.md"
  if [[ ! -f "$SPEC_TEMPLATE" ]]; then
    echo "Missing slide spec template: references/slide-spec-template.md" >&2
    exit 1
  fi
  cp "$SPEC_TEMPLATE" "$SPEC_FILE"
  python3 "$ROOT/scripts/spec_generator.py" "$SPEC_FILE" "$SLUG" "$TITLE" "$COUNT"
  SPEC_CREATED=1
else
  SPEC_CREATED=0
fi

if [[ -e "$DECK_DIR" ]]; then
  echo "Deck already exists: $DECK_DIR" >&2
  exit 1
fi
mv -- "$STAGING_DIR" "$DECK_DIR"
STAGING_DIR=""
trap - EXIT HUP INT TERM

SLIDES_FILE="$DECK_DIR/${SLUG}-slides.html"
SPEC_FILE="$DECK_DIR/${SLUG}-slide-spec.md"

if [[ "$SPEC_CREATED" -eq 1 ]]; then
  echo "Created spec ($COUNT slides): $SPEC_FILE"
else
  echo "Skipped spec (< 8 slides)"
fi

echo ""
echo "Deck scaffolded (Premium Presentations):"
echo "  Directory: $DECK_DIR"
echo "  Slides:    $SLIDES_FILE (standalone single file)"
echo "  Theme:     $FRAMEWORK (switch live in deck controls)"
echo "  Re-bundle: python3 scripts/bundle_deck.py \"$SLIDES_FILE\" --in-place  (after editing assets/shared/)"
echo "  Target:    $COUNT slides"
echo ""
if [[ -f "$SPEC_FILE" ]]; then
  echo "Validate: python3 scripts/validate_deck.py \"$SLIDES_FILE\" \"$SPEC_FILE\""
else
  echo "Validate: python3 scripts/validate_deck.py \"$SLIDES_FILE\""
fi
echo "Open:     open \"$SLIDES_FILE\""
