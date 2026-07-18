#!/usr/bin/env bash
# Publish a bundled Premium Presentations deck and print a shareable URL.
# Usage: ./scripts/share-deck.sh <deck.html>
#
# Primary: deploys via `vercel` CLI (if installed and logged in).
# Fallback: serves an isolated copy of the deck over LAN via lan-sync-server.py
#           (stdlib ThreadingHTTPServer + POST/GET /slide follow-along).
#
# Follow-along: prints a tokenized FOLLOW url (?follow=1&room=...) only when
# the served HTML carries the premium-follow.js bundle marker (the deck was
# bundled with data-follow on <html>) — a deck cannot become followable
# post-bundle, so a plain deck gets a rebuild hint instead of a dead FOLLOW url.
#
# Security: the LAN fallback serves a temporary directory containing only
# index.html and requires a random room token for follow-along reads/writes.
#
# ponytail: single file, one provider (Vercel), no auth management —
#           upgrade path: multi-file decks, other providers, scripted login.

set -euo pipefail

SRC="${1:-}"
LAN_DIR=""
DEPLOY_DIR=""

cleanup() {
  if [[ -n "$LAN_DIR" ]]; then rm -rf "$LAN_DIR"; fi
  if [[ -n "$DEPLOY_DIR" ]]; then rm -rf "$DEPLOY_DIR"; fi
}

usage() {
  sed -n '2,7p' "$0" | tail -n +2
  exit 1
}

[[ -z "$SRC" ]] && usage
[[ ! -f "$SRC" ]] && { echo "Not found: $SRC" >&2; exit 1; }
[[ "$SRC" != *.html ]] && { echo "Must be a .html file: $SRC" >&2; exit 1; }

SRC="$(cd "$(dirname "$SRC")" && pwd)/$(basename "$SRC")"

serve_lan_fallback() {
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  IP="$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || hostname)"
  LAN_DIR="$(mktemp -d)"
  ROOM="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  trap cleanup EXIT
  cp "$SRC" "$LAN_DIR/index.html"

  PORT=""
  for candidate in 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010; do
    if ! python3 -c "import socket,sys; s=socket.socket(); s.settimeout(0.2); sys.exit(0 if s.connect_ex(('127.0.0.1', int(sys.argv[1]))) else 1)" "$candidate"; then
      continue
    fi
    PORT="$candidate"
    break
  done
  if [[ -z "$PORT" ]]; then
    echo "No free port in range 8000-8010 on localhost." >&2
    exit 1
  fi

  echo "Serving an isolated copy of $(basename "$SRC") on your local network."
  echo "PRESENT (same Wi-Fi only): http://$IP:$PORT/index.html?present=1&room=$ROOM"
  if grep -q '/\* --- premium-follow\.js --- \*/' "$SRC"; then
    echo "FOLLOW  (same Wi-Fi only): http://$IP:$PORT/index.html?follow=1&room=$ROOM"
  else
    echo "No FOLLOW url: rebuild with data-follow on <html> (bundle_deck.py) to enable follow-along."
  fi
  echo "Press Ctrl-C to stop."
  python3 "$SCRIPT_DIR/lan-sync-server.py" "$LAN_DIR" "$PORT" "$ROOM"
}

if command -v vercel >/dev/null 2>&1; then
  DEPLOY_DIR="$(mktemp -d)"
  trap cleanup EXIT
  cp "$SRC" "$DEPLOY_DIR/index.html"

  echo "Deploying via Vercel..."
  if ! OUTPUT="$(vercel deploy "$DEPLOY_DIR" --yes 2>&1)"; then
    if grep -qi "not currently logged in\|not authorized\|no existing credentials" <<<"$OUTPUT"; then
      echo "Not logged in to Vercel. Run: vercel login" >&2
    else
      echo "$OUTPUT" >&2
    fi
    echo "Falling back to local network sharing." >&2
    serve_lan_fallback
    exit $?
  fi

  URL="$(grep -Eo 'https://[a-zA-Z0-9.-]+\.vercel\.app' <<<"$OUTPUT" | tail -1)"
  if [[ -z "$URL" ]]; then
    echo "$OUTPUT" >&2
    echo "Deploy succeeded but no URL was found in output." >&2
    exit 1
  fi
  echo "Deck published: $URL"
  exit 0
fi

echo "vercel CLI not found; falling back to local network sharing."
serve_lan_fallback
