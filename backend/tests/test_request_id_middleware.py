"""v0.23.0: request_id middleware contract.

Inbound X-Request-ID is trusted (so an upstream Caddy or frontend trace
can be carried through), otherwise a UUID is generated. Either way the
response carries it back.
"""

from __future__ import annotations

import re
import unittest

from fastapi.testclient import TestClient

from app.main import app

_HEADER = "X-Request-ID"


class RequestIdMiddlewareTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_response_carries_request_id_when_absent(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        rid = resp.headers.get(_HEADER)
        self.assertIsNotNone(rid)
        # uuid4().hex is 32 chars; we accept any 1..64 non-empty string.
        self.assertTrue(1 <= len(rid) <= 64)
        self.assertTrue(re.fullmatch(r"[A-Za-z0-9._-]+", rid))

    def test_inbound_request_id_is_trusted(self) -> None:
        resp = self.client.get("/health", headers={_HEADER: "trace-abc-123"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get(_HEADER), "trace-abc-123")

    def test_overlong_inbound_request_id_replaced_with_uuid(self) -> None:
        too_long = "x" * 200
        resp = self.client.get("/health", headers={_HEADER: too_long})
        rid = resp.headers.get(_HEADER)
        self.assertIsNotNone(rid)
        self.assertNotEqual(rid, too_long)
        self.assertLessEqual(len(rid), 64)

    def test_blank_inbound_request_id_replaced_with_uuid(self) -> None:
        resp = self.client.get("/health", headers={_HEADER: "   "})
        rid = resp.headers.get(_HEADER)
        self.assertIsNotNone(rid)
        self.assertNotEqual(rid.strip(), "")


if __name__ == "__main__":
    unittest.main()
