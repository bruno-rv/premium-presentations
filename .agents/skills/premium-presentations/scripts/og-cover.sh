#!/usr/bin/env bash
# Render slide 1 of a deck as a 1200x630 PNG for OG / Twitter card.
# Usage: ./scripts/og-cover.sh decks/<slug>/<slug>-slides.html
#
# Requires: headless browser. We use a tiny HTML harness + chromium's --screenshot.
# Falls back to a CSS-rendered hint if chromium isn't installed.

set -euo pipefail
SRC="${1:-}"
[[ -z "$SRC" ]] && { echo "usage: $0 <deck.html>" >&2; exit 1; }
[[ ! -f "$SRC" ]] && { echo "not found: $SRC" >&2; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DECK_DIR="$(cd "$(dirname "$SRC")" && pwd)"
OUT="$DECK_DIR/og-cover.png"

CHROME_BIN="$(command -v chromium 2>/dev/null || command -v google-chrome 2>/dev/null || true)"

# macOS: Chrome installed via .dmg (not on $PATH)
if [[ -z "$CHROME_BIN" && -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]; then
  CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
fi

if [[ -z "$CHROME_BIN" ]]; then
  echo "Neither chromium nor google-chrome is installed."
  echo "Manual fallback: open $SRC in a browser at 1200x630, screenshot slide 1, save as $OUT"
  exit 0
fi

HARNESS="$DECK_DIR/.og-harness.html"
cat > "$HARNESS" <<EOF
<!doctype html>
<html><head><meta charset="utf-8"><style>
  html,body{margin:0;background:#000;overflow:hidden}
  iframe{width:1200px;height:630px;border:0;display:block}
  iframe{transform:scale(1);transform-origin:0 0}
</style></head>
<body>
<iframe id="f" src="${SRC##*/}"></iframe>
<script>
  document.getElementById('f').addEventListener('load', () => {
    setTimeout(() => { document.title = 'READY'; }, 1500);
  });
</script>
</body></html>
EOF

"$CHROME_BIN" \
  --headless \
  --no-sandbox \
  --hide-scrollbars \
  --disable-gpu \
  --window-size=1200,630 \
  --screenshot="$OUT" \
  --virtual-time-budget=4000 \
  "file://$HARNESS" 2>/dev/null || true

rm -f "$HARNESS"

if [[ -f "$OUT" ]]; then
  echo "Cover written: $OUT (1200x630)"
else
  echo "Screenshot failed. Manual fallback required."
  exit 1
fi
