#!/usr/bin/env bash
# Scaffold a Premium Presentations HTML deck.
# Usage: ./scripts/new-deck.sh [--output-dir DIR] [--themes-css FILE] <theme> <slug> "<title>" [slide_count]
#
# Examples:
#   ./scripts/list-themes.py
#   ./scripts/new-deck.sh warm my-talk "My Talk" 15

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR=""
THEMES_CSS_FILE=""

usage() {
  sed -n '2,7p' "$0" | tail -n +2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      [[ $# -ge 2 ]] || usage
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --themes-css)
      [[ $# -ge 2 ]] || usage
      THEMES_CSS_FILE="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -*)
      usage
      ;;
    *)
      break
      ;;
  esac
done

FRAMEWORK="${1:-}"
SLUG="${2:-}"
TITLE="${3:-}"
COUNT="${4:-10}"

[[ -z "$FRAMEWORK" || -z "$SLUG" || -z "$TITLE" ]] && usage

THEMES=()
if [[ -n "$THEMES_CSS_FILE" ]]; then
  while IFS= read -r theme; do
    [[ -n "$theme" ]] && THEMES+=("$theme")
  done < <(python3 "$ROOT/scripts/list-themes.py" --css "$THEMES_CSS_FILE")
else
  while IFS= read -r theme; do
    [[ -n "$theme" ]] && THEMES+=("$theme")
  done < <(python3 "$ROOT/scripts/list-themes.py")
fi
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

if [[ -n "$OUTPUT_DIR" ]]; then
  mkdir -p "$OUTPUT_DIR"
  DECK_DIR="$(cd "$OUTPUT_DIR" && pwd)"
else
  DECK_DIR="$ROOT/assets/decks/$SLUG"
fi
SLIDES_FILE="$DECK_DIR/${SLUG}-slides.html"
SPEC_FILE="$DECK_DIR/${SLUG}-slide-spec.md"
THEME_TEMPLATE="$ROOT/assets/templates/${FRAMEWORK}-base.html"
if [[ -f "$THEME_TEMPLATE" ]]; then
  TEMPLATE="$THEME_TEMPLATE"
else
  TEMPLATE="$ROOT/assets/templates/premium-base.html"
fi

if [[ -z "$OUTPUT_DIR" && -e "$DECK_DIR" ]]; then
  echo "Deck already exists: $DECK_DIR" >&2
  exit 1
fi
if [[ -n "$OUTPUT_DIR" && ( -e "$SLIDES_FILE" || -e "$SPEC_FILE" ) ]]; then
  echo "Deck already exists: $DECK_DIR" >&2
  exit 1
fi

mkdir -p "$DECK_DIR"

sed \
  -e "s|{{THEME}}|${FRAMEWORK}|g" \
  -e "s|{{TITLE}}|${TITLE}|g" \
  -e "s|{{SHARED}}|../../shared/|g" \
  -e "s|{{BAR_RIGHT}}||g" \
  "$TEMPLATE" > "$SLIDES_FILE"

BUNDLE_ARGS=("$SLIDES_FILE" --in-place --shared-root "$ROOT/assets/shared")
if [[ -n "$THEMES_CSS_FILE" ]]; then
  BUNDLE_ARGS+=(--themes-css "$THEMES_CSS_FILE")
fi
python3 "$ROOT/scripts/bundle_deck.py" "${BUNDLE_ARGS[@]}"
python3 "$ROOT/scripts/validate_deck.py" "$SLIDES_FILE" || exit 1

if [[ "$COUNT" -ge 8 ]]; then
  SPEC_TEMPLATE="$ROOT/references/slide-spec-template.md"
  if [[ ! -f "$SPEC_TEMPLATE" ]]; then
    echo "Missing slide spec template: references/slide-spec-template.md" >&2
    exit 1
  fi
  cp "$SPEC_TEMPLATE" "$SPEC_FILE"
  python3 "$ROOT/scripts/spec_generator.py" "$SPEC_FILE" "$SLUG" "$TITLE" "$COUNT"

  echo "Created spec ($COUNT slides): $SPEC_FILE"
else
  echo "Skipped spec (< 8 slides)"
fi

echo ""
echo "Deck scaffolded (Premium Presentations):"
echo "  Directory: $DECK_DIR"
echo "  Slides:    $SLIDES_FILE (standalone single file)"
echo "  Theme:     $FRAMEWORK (switch live in deck controls)"
echo "  Re-bundle: python3 scripts/bundle_deck.py \"$SLIDES_FILE\" --in-place --shared-root \"$ROOT/assets/shared\"  (after editing shared assets)"
echo "  Target:    $COUNT slides"
echo ""
if [[ -f "$SPEC_FILE" ]]; then
  echo "Validate: python3 scripts/validate_deck.py \"$SLIDES_FILE\" \"$SPEC_FILE\""
else
  echo "Validate: python3 scripts/validate_deck.py \"$SLIDES_FILE\""
fi
echo "Open:     open \"$SLIDES_FILE\""
