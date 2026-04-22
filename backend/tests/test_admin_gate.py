"""Admin gate integration tests.

Verifies that /api/admin/* returns 403 for non-admin users and 200 for admins,
that /api/dashboard/stats returns the trimmed funnel shape (no qdrant/vector fields),
and that /api/system/vacancy-warmup returns only the four user-facing fields.
"""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.auth_otp_code import AuthOtpCode
from app.models.user import User


def _make_user(db, email: str, is_admin: bool = False) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("TestPass123"),
        full_name="Test User",
        is_active=True,
        email_verified=True,
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(email: str) -> dict[str, str]:
    token = create_access_token(subject=email)
    return {"Authorization": f"Bearer {token}"}


class AdminGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.user_email = f"nonadmin-{suffix}@example.com"
        self.admin_email = f"admin-{suffix}@example.com"
        self.user = _make_user(self.db, self.user_email, is_admin=False)
        self.admin = _make_user(self.db, self.admin_email, is_admin=True)

    def tearDown(self) -> None:
        for email in (self.user_email, self.admin_email):
            u = self.db.query(User).filter(User.email == email).one_or_none()
            if u:
                self.db.execute(delete(AuthOtpCode).where(AuthOtpCode.user_id == u.id))
                self.db.execute(delete(User).where(User.id == u.id))
        self.db.commit()
        self.db.close()

    def test_non_admin_gets_403_on_admin_stats(self) -> None:
        resp = self.client.get("/api/admin/stats", headers=_auth_header(self.user_email))
        self.assertEqual(resp.status_code, 403)

    def test_non_admin_gets_403_on_admin_warmup(self) -> None:
        resp = self.client.get("/api/admin/warmup", headers=_auth_header(self.user_email))
        self.assertEqual(resp.status_code, 403)

    def test_non_admin_gets_403_on_admin_config_check(self) -> None:
        resp = self.client.get("/api/admin/config-check", headers=_auth_header(self.user_email))
        self.assertEqual(resp.status_code, 403)

    def test_admin_gets_200_on_admin_stats(self) -> None:
        resp = self.client.get("/api/admin/stats", headers=_auth_header(self.admin_email))
        self.assertEqual(resp.status_code, 200)

    def test_admin_gets_200_on_admin_warmup(self) -> None:
        resp = self.client.get("/api/admin/warmup", headers=_auth_header(self.admin_email))
        self.assertEqual(resp.status_code, 200)

    def test_admin_gets_200_on_admin_config_check(self) -> None:
        resp = self.client.get("/api/admin/config-check", headers=_auth_header(self.admin_email))
        self.assertEqual(resp.status_code, 200)

    def test_non_admin_dashboard_stats_is_funnel_shape(self) -> None:
        resp = self.client.get("/api/dashboard/stats", headers=_auth_header(self.user_email))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("generated_at", body)
        self.assertIn("funnel", body)
        self.assertNotIn("qdrant", body)
        self.assertNotIn("vector_candidates_top300", body)
        funnel = body["funnel"]
        self.assertIn("analyzed_count", funnel)
        self.assertIn("matched_count", funnel)
        self.assertIn("selected_count", funnel)

    def test_system_vacancy_warmup_trimmed_fields(self) -> None:
        resp = self.client.get("/api/system/vacancy-warmup")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("enabled", body)
        self.assertIn("running", body)
        self.assertIn("last_finished_at", body)
        self.assertIn("interval_seconds", body)
        self.assertNotIn("cycle", body)
        self.assertNotIn("last_metrics", body)


if __name__ == "__main__":
    unittest.main()
