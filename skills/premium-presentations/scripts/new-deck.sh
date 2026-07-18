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

DECK_DIR_PREEXISTED=0
if [[ -n "$OUTPUT_DIR" ]]; then
  [[ -e "$OUTPUT_DIR" ]] && DECK_DIR_PREEXISTED=1
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

STAGING_PARENT="$(dirname "$DECK_DIR")"
mkdir -p "$STAGING_PARENT"
STAGING_DIR="$(mktemp -d "$STAGING_PARENT/.${SLUG}.staging.XXXXXX")"
cleanup_partial_output() {
  status=$?
  trap - EXIT HUP INT TERM
  if [[ -n "${STAGING_DIR:-}" && -d "$STAGING_DIR" ]]; then
    rm -rf -- "$STAGING_DIR"
  fi
  if [[ "$status" -ne 0 ]]; then
    rm -f "$SLIDES_FILE" "$SPEC_FILE" || true
    if [[ -z "$OUTPUT_DIR" || "$DECK_DIR_PREEXISTED" -eq 0 ]]; then
      rmdir "$DECK_DIR" 2>/dev/null || true
    fi
  fi
  exit "$status"
}
trap cleanup_partial_output EXIT HUP INT TERM

STAGED_SLIDES="$STAGING_DIR/${SLUG}-slides.html"
STAGED_SPEC="$STAGING_DIR/${SLUG}-slide-spec.md"

python3 "$ROOT/scripts/render_template.py" "$TEMPLATE" "$STAGED_SLIDES" \
  --var THEME "$FRAMEWORK" \
  --var TITLE "$TITLE" \
  --var SHARED "../../shared/" \
  --var BAR_RIGHT ""

BUNDLE_ARGS=("$STAGED_SLIDES" --in-place --shared-root "$ROOT/assets/shared")
if [[ -n "$THEMES_CSS_FILE" ]]; then
  BUNDLE_ARGS+=(--themes-css "$THEMES_CSS_FILE")
fi
python3 "$ROOT/scripts/bundle_deck.py" "${BUNDLE_ARGS[@]}"
python3 "$ROOT/scripts/validate_deck.py" "$STAGED_SLIDES"

if [[ "$COUNT" -ge 8 ]]; then
  SPEC_TEMPLATE="$ROOT/references/slide-spec-template.md"
  if [[ ! -f "$SPEC_TEMPLATE" ]]; then
    echo "Missing slide spec template: references/slide-spec-template.md" >&2
    exit 1
  fi
  cp "$SPEC_TEMPLATE" "$STAGED_SPEC"
  python3 "$ROOT/scripts/spec_generator.py" "$STAGED_SPEC" "$SLUG" "$TITLE" "$COUNT"
  SPEC_CREATED=1
else
  SPEC_CREATED=0
fi

# Both files are fully built and validated in staging; move them into the
# final location as the last step so a crash or failure above never leaves
# a partial deck behind (rename is atomic per-file on the same filesystem,
# guaranteed here since STAGING_DIR is a sibling of DECK_DIR).
mkdir -p "$DECK_DIR"
mv -- "$STAGED_SLIDES" "$SLIDES_FILE"
if [[ "$SPEC_CREATED" -eq 1 ]]; then
  mv -- "$STAGED_SPEC" "$SPEC_FILE"
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
