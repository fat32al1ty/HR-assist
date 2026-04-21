"""HTTP-level rate limiting for auth endpoints.

These tests spin up FastAPI's TestClient to exercise the slowapi middleware,
which is skipped by the function-level tests in test_auth_hardening_flow.py.
"""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import settings
from app.core.rate_limit import AUTH_REGISTER_LIMIT, limiter
from app.db.session import SessionLocal
from app.main import app
from app.models.auth_otp_code import AuthOtpCode
from app.models.user import User


def _limit_count(limit_spec: str) -> int:
    return int(limit_spec.split("/")[0])


class AuthRateLimitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_beta_keys = settings.beta_tester_keys
        settings.beta_tester_keys = "BETA-TEST-KEY"
        self.emails: list[str] = []
        self._limiter_was_enabled = limiter.enabled
        limiter.enabled = True
        limiter.reset()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        settings.beta_tester_keys = self.original_beta_keys
        limiter.enabled = self._limiter_was_enabled
        limiter.reset()
        if self.emails:
            db = SessionLocal()
            try:
                users = db.query(User).filter(User.email.in_(self.emails)).all()
                for user in users:
                    db.execute(delete(AuthOtpCode).where(AuthOtpCode.user_id == user.id))
                    db.execute(delete(User).where(User.id == user.id))
                db.commit()
            finally:
                db.close()

    def test_register_returns_429_past_limit(self) -> None:
        cap = _limit_count(AUTH_REGISTER_LIMIT)
        payloads = []
        for _ in range(cap + 1):
            email = f"rl-{uuid.uuid4().hex[:10]}@example.com"
            self.emails.append(email)
            payloads.append(
                {
                    "email": email,
                    "password": "SuperStrong123",
                    "full_name": "Rate Limit Test",
                    "beta_key": "WRONG-KEY",
                }
            )

        statuses = [self.client.post("/api/auth/register", json=p).status_code for p in payloads]
        # Any rejection code is fine for the first `cap` calls (403 here because
        # beta_key is wrong). The (cap + 1)-th must be 429. Critically: nothing
        # before the cap should be 500 — that would mean slowapi's header
        # injection blew up (see https://github.com/laurentS/slowapi issue #177).
        self.assertTrue(all(status < 500 for status in statuses[:cap]), statuses[:cap])
        self.assertTrue(all(status != 429 for status in statuses[:cap]))
        self.assertEqual(statuses[-1], 429)

    def test_rate_limited_endpoint_does_not_500_on_success_path(self) -> None:
        """Regression: slowapi requires a `response: Response` parameter in the
        handler signature, otherwise its header-injection path raises at 500.
        This test exercises the happy path (valid beta_key + unique email) and
        asserts we get 201, not 500.
        """
        email = f"rl-ok-{uuid.uuid4().hex[:10]}@example.com"
        self.emails.append(email)
        resp = self.client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "SuperStrong123",
                "full_name": "Rate Limit Success",
                "beta_key": "BETA-TEST-KEY",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        # slowapi should have attached rate-limit metadata — this confirms the
        # header-injection path actually ran without exploding.
        self.assertIn("x-ratelimit-limit", {k.lower() for k in resp.headers.keys()})


if __name__ == "__main__":
    unittest.main()
