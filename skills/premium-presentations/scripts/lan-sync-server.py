#!/usr/bin/env python3
"""LAN follow-along sync server for Premium Presentations decks.

Stdlib-only (http.server, json) ThreadingHTTPServer: serves an isolated
directory containing the deck, plus a tiny in-memory current-slide-id endpoint:

  POST /slide?room=<token> {"id": "<slide-id>"}  presenter write
  GET  /slide?room=<token>                        audience read

Security: binds 0.0.0.0 so audience devices on the LAN can reach it, but
requires a cryptographically random room token on every sync read/write.
The share script serves a temporary directory containing only index.html.
Do not expose this ephemeral server to the public internet.

Usage:
  ./scripts/lan-sync-server.py <serve-dir> <port> <room-token>
"""

from __future__ import annotations

import json
import re
import secrets
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

# Small body cap: presenter slide ids are short strings, never large payloads.
_MAX_BODY = 4096
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def make_handler(directory: str, room_token: str) -> type[SimpleHTTPRequestHandler]:
    current: dict[str, str | None] = {"id": None}

    class SyncHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        def do_POST(self) -> None:
            request = urlsplit(self.path)
            if request.path != "/slide":
                self.send_error(404)
                return
            if not self._authorized(request.query):
                self.send_error(403, "Invalid room token")
                return

            try:
                length = int(self.headers.get("Content-Length", ""))
                if length < 0:
                    raise ValueError("negative Content-Length")
            except ValueError:
                self.send_error(400, "Missing or invalid Content-Length")
                return

            if length > _MAX_BODY:
                self.send_error(413, "Request body too large")
                return

            try:
                raw = self.rfile.read(length) if length else b"{}"
                payload = json.loads(raw or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("payload must be a JSON object")
                slide_id = payload.get("id")
                if slide_id is not None and not (
                    isinstance(slide_id, str) and _ID_RE.match(slide_id)
                ):
                    raise ValueError("id must be null or a bounded id string")
            except (ValueError, TypeError):
                self.send_error(400, "Malformed JSON body")
                return

            current["id"] = slide_id
            self._json({"ok": True})

        def do_GET(self) -> None:
            request = urlsplit(self.path)
            if request.path == "/slide":
                if not self._authorized(request.query):
                    self.send_error(403, "Invalid room token")
                    return
                self._json(current)
                return
            super().do_GET()

        def _authorized(self, query: str) -> bool:
            supplied = parse_qs(query, keep_blank_values=True).get("room", [""])[0]
            return secrets.compare_digest(
                supplied.encode("utf-8"), room_token.encode("utf-8")
            )

        def _json(self, obj: dict) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args) -> None:  # quieter default logging
            pass

    return SyncHandler


def serve(
    directory: str,
    port: int,
    room_token: str,
    *,
    host: str = "0.0.0.0",
) -> ThreadingHTTPServer:
    if not room_token:
        raise ValueError("room_token must not be empty")
    handler = make_handler(directory, room_token)
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: lan-sync-server.py <serve-dir> <port> <room-token>", file=sys.stderr)
        return 1
    directory, port_str, room_token = argv
    if not Path(directory).is_dir():
        print(f"Not a directory: {directory}", file=sys.stderr)
        return 1
    try:
        port = int(port_str)
    except ValueError:
        print(f"Invalid port: {port_str}", file=sys.stderr)
        return 1

    if not room_token:
        print("Room token must not be empty", file=sys.stderr)
        return 1

    httpd = serve(directory, port, room_token)
    print(f"Serving {directory} on 0.0.0.0:{port} (tokenized /slide + static files)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
