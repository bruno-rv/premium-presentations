#!/usr/bin/env python3
"""Tests for lan-sync-server.py — AT4: POST-then-GET round-trip < 2s."""
from __future__ import annotations

import http.client
import importlib.util
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SERVER_PATH = ROOT / "scripts" / "lan-sync-server.py"


def load_server_module():
    spec = importlib.util.spec_from_file_location("lan_sync_server", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lan_sync_server = load_server_module()


class LanSyncServerTests(unittest.TestCase):
    ROOM = "test-room-token-with-enough-entropy"

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        (Path(self.tmpdir.name) / "index.html").write_text("<html></html>", encoding="utf-8")

        self.httpd = lan_sync_server.serve(
            self.tmpdir.name, 0, self.ROOM, host="127.0.0.1"
        )
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

        def teardown() -> None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.thread.join(timeout=5)

        self.addCleanup(teardown)

    def _conn(self) -> http.client.HTTPConnection:
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)

    def _slide_path(self, room: str | None = None) -> str:
        return f"/slide?room={room or self.ROOM}"

    def test_at4_post_then_get_round_trip_under_2s(self) -> None:
        start = time.monotonic()
        conn = self._conn()
        body = json.dumps({"id": "s3"}).encode("utf-8")
        conn.request("POST", self._slide_path(), body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        resp.read()
        conn.close()

        conn = self._conn()
        conn.request("GET", self._slide_path())
        resp = conn.getresponse()
        payload = json.loads(resp.read())
        conn.close()
        elapsed = time.monotonic() - start

        self.assertEqual(payload, {"id": "s3"})
        self.assertLess(elapsed, 2.0, f"round trip took {elapsed:.3f}s")

    def test_get_slide_before_any_post_returns_null_id(self) -> None:
        conn = self._conn()
        conn.request("GET", self._slide_path())
        resp = conn.getresponse()
        payload = json.loads(resp.read())
        conn.close()
        self.assertIn("id", payload)

    def test_malformed_post_body_returns_400(self) -> None:
        conn = self._conn()
        conn.request("POST", self._slide_path(), body=b"not json", headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 400)

    def test_unknown_post_path_returns_404(self) -> None:
        conn = self._conn()
        conn.request("POST", "/nope", body=b"{}")
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 404)

    def test_slide_endpoint_rejects_missing_room_token(self) -> None:
        for method in ("GET", "POST"):
            conn = self._conn()
            conn.request(method, "/slide", body=b"{}" if method == "POST" else None)
            resp = conn.getresponse()
            resp.read()
            conn.close()
            self.assertEqual(resp.status, 403)

    def test_slide_endpoint_rejects_incorrect_room_token(self) -> None:
        for method in ("GET", "POST"):
            conn = self._conn()
            conn.request(
                method,
                self._slide_path("wrong-room"),
                body=b"{}" if method == "POST" else None,
            )
            resp = conn.getresponse()
            resp.read()
            conn.close()
            self.assertEqual(resp.status, 403)

    def test_slide_endpoint_rejects_unicode_token_without_crashing(self) -> None:
        conn = self._conn()
        conn.request("GET", "/slide?room=%F0%9F%94%92")
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 403)

    def test_static_file_still_served(self) -> None:
        conn = self._conn()
        conn.request("GET", "/index.html")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertIn(b"<html>", body)

    def _current_id(self) -> str | None:
        conn = self._conn()
        conn.request("GET", self._slide_path())
        resp = conn.getresponse()
        payload = json.loads(resp.read())
        conn.close()
        return payload.get("id")

    def test_missing_content_length_returns_400(self) -> None:
        # http.client always injects "Content-Length: 0" for a bodyless
        # POST, so a raw socket is needed to omit the header entirely (as a
        # non-conforming client might).
        import socket

        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        try:
            request = (
                f"POST {self._slide_path()} HTTP/1.1\r\n"
                "Host: 127.0.0.1\r\n\r\n"
            ).encode()
            sock.sendall(request)
            status_line = sock.makefile("rb").readline()
        finally:
            sock.close()
        self.assertIn(b"400", status_line)

    def test_negative_content_length_returns_400(self) -> None:
        conn = self._conn()
        conn.request("POST", self._slide_path(), body=b"{}", headers={"Content-Length": "-5"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 400)

    def test_non_integer_content_length_returns_400(self) -> None:
        conn = self._conn()
        conn.request("POST", self._slide_path(), body=b"{}", headers={"Content-Length": "abc"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 400)

    def test_oversized_body_returns_413(self) -> None:
        conn = self._conn()
        body = json.dumps({"id": "s" * (lan_sync_server._MAX_BODY + 1)}).encode("utf-8")
        conn.request("POST", self._slide_path(), body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 413)

    def test_non_object_json_returns_400(self) -> None:
        conn = self._conn()
        body = json.dumps(["not", "an", "object"]).encode("utf-8")
        conn.request("POST", self._slide_path(), body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 400)

    def test_non_string_id_returns_400(self) -> None:
        conn = self._conn()
        body = json.dumps({"id": 12345}).encode("utf-8")
        conn.request("POST", self._slide_path(), body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 400)

    def test_oversized_id_string_returns_400(self) -> None:
        conn = self._conn()
        body = json.dumps({"id": "s" * 200}).encode("utf-8")
        conn.request("POST", self._slide_path(), body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 400)

    def test_current_unchanged_after_rejected_posts(self) -> None:
        conn = self._conn()
        body = json.dumps({"id": "good-1"}).encode("utf-8")
        conn.request("POST", self._slide_path(), body=body, headers={"Content-Type": "application/json"})
        conn.getresponse().read()
        conn.close()
        self.assertEqual(self._current_id(), "good-1")

        for bad_body in (b"not json", json.dumps({"id": 999}).encode(), json.dumps(["x"]).encode()):
            conn = self._conn()
            conn.request(
                "POST", self._slide_path(), body=bad_body, headers={"Content-Type": "application/json"}
            )
            resp = conn.getresponse()
            resp.read()
            conn.close()
            self.assertEqual(resp.status, 400)
            self.assertEqual(self._current_id(), "good-1", "_current must not change on rejection")

    def test_valid_post_still_round_trips_after_hardening(self) -> None:
        conn = self._conn()
        body = json.dumps({"id": "s7"}).encode("utf-8")
        conn.request("POST", self._slide_path(), body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        resp.read()
        conn.close()
        self.assertEqual(self._current_id(), "s7")

    def test_share_script_copies_only_index_into_a_temporary_directory(self) -> None:
        share_script = (ROOT / "scripts" / "share-deck.sh").read_text(encoding="utf-8")
        self.assertRegex(share_script, r'LAN_DIR="\$\(mktemp -d\)"')
        self.assertIn('cp "$SRC" "$LAN_DIR/index.html"', share_script)
        self.assertIn("secrets.token_urlsafe(32)", share_script)
        self.assertIn("?present=1&room=$ROOM", share_script)
        self.assertIn("?follow=1&room=$ROOM", share_script)
        self.assertIn('lan-sync-server.py" "$LAN_DIR" "$PORT" "$ROOM"', share_script)
        self.assertNotIn('lan-sync-server.py" "$DIR" "$PORT"', share_script)
        self.assertIn("serve_lan_fallback\n    exit $?", share_script)

    def test_server_compares_room_tokens_in_constant_time(self) -> None:
        source = SERVER_PATH.read_text(encoding="utf-8")
        self.assertIn("secrets.compare_digest(", source)
        self.assertIn('supplied.encode("utf-8")', source)


if __name__ == "__main__":
    unittest.main()
