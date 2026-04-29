"""v0.23.0: smoke tests for /admin/metrics/* endpoints.

Each endpoint must return 200 with the documented JSON shape on a
freshly-empty DB (no synthetic fixtures here — admin_metrics service
must tolerate zero data and return zeros, not NULLs).
"""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User


class _AdminEndpointBase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"admin-metrics-{suffix}@example.com",
            hashed_password=hash_password("TestPass123"),
            full_name="Admin",
            is_active=True,
            email_verified=True,
            is_admin=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        self.token = create_access_token(subject=self.user.email)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.db.execute(User.__table__.delete().where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}


class AdminMetricsEndpointsSmokeTest(_AdminEndpointBase):
    def test_latency_endpoint_returns_shape(self) -> None:
        resp = self.client.get("/api/admin/metrics/latency?range=24h", headers=self._headers())
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("by_job_type", body)
        self.assertEqual(body["range"], "24h")

    def test_cost_endpoint_returns_shape(self) -> None:
        resp = self.client.get("/api/admin/metrics/cost?range=7d", headers=self._headers())
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        for key in ("total_usd", "today_usd", "yesterday_usd", "by_day", "by_model"):
            self.assertIn(key, body)
        self.assertIsInstance(body["by_day"], list)
        self.assertIsInstance(body["by_model"], list)

    def test_activation_funnel_returns_5_steps(self) -> None:
        resp = self.client.get(
            "/api/admin/metrics/activation-funnel?range=30d",
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(len(body["steps"]), 5)
        keys = [s["key"] for s in body["steps"]]
        self.assertEqual(
            keys,
            ["uploaded", "first_search", "first_match", "first_like", "first_apply"],
        )

    def test_retention_returns_three_buckets(self) -> None:
        resp = self.client.get("/api/admin/metrics/retention", headers=self._headers())
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        for key in ("d1", "d7", "d30"):
            self.assertIn(key, body)
            for k in ("retained", "eligible", "share"):
                self.assertIn(k, body[key])

    def test_quality_endpoint_returns_shape(self) -> None:
        resp = self.client.get("/api/admin/metrics/quality?range=7d", headers=self._headers())
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("ctr_by_tier", body)
        self.assertIn("score_distribution_by_tier", body)

    def test_segment_warmup_returns_shape(self) -> None:
        resp = self.client.get(
            "/api/admin/metrics/segment-warmup?range=7d", headers=self._headers()
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        for key in ("by_status", "mean_duration_seconds", "daily_count", "daily_cap"):
            self.assertIn(key, body)

    def test_freshness_endpoint_returns_runs_list(self) -> None:
        resp = self.client.get("/api/admin/metrics/freshness?range=30d", headers=self._headers())
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIsInstance(resp.json()["runs"], list)

    def test_match_events_endpoint_returns_events_list(self) -> None:
        resp = self.client.get("/api/admin/metrics/match-events?range=7d", headers=self._headers())
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIsInstance(resp.json()["events"], list)

    def test_invalid_range_rejected_400(self) -> None:
        resp = self.client.get("/api/admin/metrics/latency?range=99x", headers=self._headers())
        self.assertEqual(resp.status_code, 400)

    def test_non_admin_blocked(self) -> None:
        # Strip is_admin and confirm endpoint refuses.
        suffix = uuid.uuid4().hex[:10]
        regular = User(
            email=f"reg-{suffix}@example.com",
            hashed_password=hash_password("TestPass123"),
            full_name="Reg",
            is_active=True,
            email_verified=True,
            is_admin=False,
        )
        db = SessionLocal()
        try:
            db.add(regular)
            db.commit()
            db.refresh(regular)
            token = create_access_token(subject=regular.email)
            resp = self.client.get(
                "/api/admin/metrics/latency?range=24h",
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(resp.status_code, 403)
            db.execute(User.__table__.delete().where(User.id == regular.id))
            db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
