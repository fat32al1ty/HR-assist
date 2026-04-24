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
from app.models.recommendation_job import RecommendationJob
from app.models.resume import Resume
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

    def test_non_admin_gets_403_on_admin_overview(self) -> None:
        resp = self.client.get("/api/admin/overview", headers=_auth_header(self.user_email))
        self.assertEqual(resp.status_code, 403)

    def test_admin_overview_shape(self) -> None:
        resp = self.client.get("/api/admin/overview", headers=_auth_header(self.admin_email))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for field in (
            "generated_at",
            "users_total",
            "users_active_last_day",
            "resumes_total",
            "vacancies_total",
            "vacancies_indexed",
            "top_searched_roles",
            "active_jobs",
        ):
            self.assertIn(field, body)
        self.assertGreaterEqual(body["users_total"], 2)  # admin + non-admin from setUp
        self.assertIsInstance(body["top_searched_roles"], list)
        self.assertIsInstance(body["active_jobs"], list)

    def test_admin_can_cancel_other_users_job(self) -> None:
        resume = Resume(
            user_id=self.user.id,
            original_filename="resume.pdf",
            content_type="application/pdf",
            status="completed",
            analysis={"target_role": "Python-разработчик"},
        )
        self.db.add(resume)
        self.db.commit()
        self.db.refresh(resume)

        job_id = str(uuid.uuid4())
        job = RecommendationJob(
            id=job_id,
            user_id=self.user.id,
            resume_id=resume.id,
            status="running",
            stage="collecting",
            progress=10,
        )
        self.db.add(job)
        self.db.commit()

        try:
            # Non-admin can't cancel via the admin endpoint.
            resp_deny = self.client.post(
                f"/api/admin/jobs/{job_id}/cancel",
                headers=_auth_header(self.user_email),
            )
            self.assertEqual(resp_deny.status_code, 403)

            # Admin can cancel another user's job.
            resp = self.client.post(
                f"/api/admin/jobs/{job_id}/cancel",
                headers=_auth_header(self.admin_email),
            )
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertEqual(body["id"], job_id)
            self.assertTrue(body["cancel_requested"])

            # Overview lists it as active with cancel_requested flipped.
            overview = self.client.get(
                "/api/admin/overview", headers=_auth_header(self.admin_email)
            ).json()
            match = next((j for j in overview["active_jobs"] if j["id"] == job_id), None)
            self.assertIsNotNone(match)
            assert match is not None  # narrow for type-checker
            self.assertTrue(match["cancel_requested"])
            self.assertEqual(match["user_email"], self.user_email)
            self.assertEqual(match["target_role"], "Python-разработчик")
        finally:
            self.db.execute(delete(RecommendationJob).where(RecommendationJob.id == job_id))
            self.db.execute(delete(Resume).where(Resume.id == resume.id))
            self.db.commit()

    def test_admin_cancel_missing_job_returns_404(self) -> None:
        resp = self.client.post(
            "/api/admin/jobs/nope-does-not-exist/cancel",
            headers=_auth_header(self.admin_email),
        )
        self.assertEqual(resp.status_code, 404)

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
