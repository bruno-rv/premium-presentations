#!/usr/bin/env bash
# Scaffold a Premium Presentations HTML deck.
# Usage: ./scripts/new-deck.sh <theme> <slug> "<title>" [slide_count]
#
# Examples:
#   ./scripts/list-themes.py
#   ./scripts/new-deck.sh warm rag-vector-graph "RAG, Vector and Graph Databases" 15

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ASSETS="$ROOT/assets"
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

DECK_DIR="$ASSETS/decks/$SLUG"
SLIDES_FILE="$DECK_DIR/${SLUG}-slides.html"
SPEC_FILE="$DECK_DIR/${SLUG}-slide-spec.md"
THEME_TEMPLATE="$ASSETS/templates/${FRAMEWORK}-base.html"
if [[ -f "$THEME_TEMPLATE" ]]; then
  TEMPLATE="$THEME_TEMPLATE"
else
  TEMPLATE="$ASSETS/templates/premium-base.html"
fi

if [[ -e "$DECK_DIR" ]]; then
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

python3 "$ROOT/scripts/bundle_deck.py" "$SLIDES_FILE" --in-place
export VALIDATE_HTML="$SLIDES_FILE"
export VALIDATE_SPEC=""
python3 "$ROOT/scripts/validate_deck.py" || exit 1

if [[ "$COUNT" -ge 8 ]]; then
  SPEC_TEMPLATE="$ROOT/references/slide-spec-template.md"
  if [[ ! -f "$SPEC_TEMPLATE" ]]; then
    echo "Missing slide spec template: references/slide-spec-template.md" >&2
    exit 1
  fi
  cp "$SPEC_TEMPLATE" "$SPEC_FILE"

  python3 - "$SPEC_FILE" "$SLUG" "$TITLE" "$COUNT" <<'PY'
import sys, re
path, slug, title, count = sys.argv[1:5]
count = int(count)
text = open(path, encoding="utf-8").read()
text = text.replace("{CODE}", slug.upper().replace("-", " "))
text = text.replace("{code}", slug)
text = text.replace("{Full title}", title)
text = text.replace("{N}", str(max(15, count // 2)))

rows = []
for i in range(1, count + 1):
    if i == 1:
        t, typ, pat = "Title", "Title", "slide--title"
    elif i == 2:
        t, typ, pat = "Hook", "Hook Quote", "slide--quote"
    elif i == count:
        t, typ, pat = "Closing", "Closing Quote", "slide--quote"
    elif i in (4, 8, 12) and count >= 12:
        t, typ, pat = f"Act break {i}", "Divider", "DIV+ divider-act"
    else:
        t, typ, pat = f"Slide {i}", "Content", "slide / diagram / table"
    rows.append(f"| {i} | {typ} | {t} | TBD | {pat} | TBD |")

table = "| # | Type | Title | Key Content | Visual Pattern | Why Panel |\n|---|------|-------|-------------|----------------|----------|\n" + "\n".join(rows)
text = re.sub(
    r"(## Slide Map\n\n)\| # \| Type \| Title \| Key Content \| Visual Pattern \| Why Panel \|\n"
    r"\|[-|]+\|\n(?:\|.*\|\n)+",
    lambda _: "## Slide Map\n\n" + table + "\n",
    text,
    count=1,
)
open(path, "w", encoding="utf-8").write(text)
PY

  echo "Created spec ($COUNT slides): $SPEC_FILE"
else
  echo "Skipped spec (< 8 slides)"
fi

echo ""
echo "Deck scaffolded (Premium Presentations):"
echo "  Directory: $DECK_DIR"
echo "  Slides:    $SLIDES_FILE (standalone single file)"
echo "  Theme:     $FRAMEWORK (switch live in deck controls)"
echo "  Re-bundle: ./scripts/bundle-deck.sh \"$SLIDES_FILE\" --in-place  (after editing assets/shared/)"
echo "  Target:    $COUNT slides"
echo ""
echo "Validate: ./scripts/validate-deck.sh \"$SLIDES_FILE\" ${SPEC_FILE:+"\"$SPEC_FILE\""}"
echo "Open:     open \"$SLIDES_FILE\""
