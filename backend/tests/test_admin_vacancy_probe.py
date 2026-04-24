"""Tests for the admin /vacancy-sources/probe endpoint."""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes import admin as admin_routes
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.auth_otp_code import AuthOtpCode
from app.models.user import User
from sqlalchemy import delete


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


class AdminVacancyProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.user_email = f"nonadmin-probe-{suffix}@example.com"
        self.admin_email = f"admin-probe-{suffix}@example.com"
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

    def _all_empty_patches(self):
        return [
            patch.object(admin_routes, "_search_hh_public_api_vacancies", return_value=[]),
            patch.object(admin_routes, "_search_superjob_api_vacancies", return_value=[]),
            patch.object(admin_routes, "_search_habr_api_vacancies", return_value=[]),
            patch.object(admin_routes, "_collect_public_hh_vacancies", return_value=[]),
            patch.object(admin_routes, "_collect_public_habr_vacancies", return_value=[]),
            patch.object(admin_routes, "_collect_public_superjob_vacancies", return_value=[]),
            patch.object(admin_routes.settings, "superjob_api_key", "key"),
            patch.object(admin_routes.settings, "habr_career_api_token", "tok"),
        ]

    def test_probe_requires_admin(self) -> None:
        resp = self.client.post(
            "/api/admin/vacancy-sources/probe",
            json={"query": "python"},
            headers=_auth_header(self.user_email),
        )
        self.assertEqual(resp.status_code, 403)

    def test_probe_returns_counts_per_source(self) -> None:
        patches = self._all_empty_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
            resp = self.client.post(
                "/api/admin/vacancy-sources/probe",
                json={"query": "python developer"},
                headers=_auth_header(self.admin_email),
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["query"], "python developer")
        expected_keys = {
            "hh_api",
            "superjob_api",
            "habr_api",
            "hh_public",
            "habr_public",
            "superjob_public",
        }
        self.assertEqual(set(body["sources"].keys()), expected_keys)
        for key in expected_keys:
            self.assertIn("count", body["sources"][key])
            self.assertIn("error", body["sources"][key])

    def test_probe_reports_errors(self) -> None:
        with (
            patch.object(
                admin_routes,
                "_search_hh_public_api_vacancies",
                side_effect=RuntimeError("timeout"),
            ),
            patch.object(admin_routes, "_search_superjob_api_vacancies", return_value=[]),
            patch.object(admin_routes, "_search_habr_api_vacancies", return_value=[]),
            patch.object(admin_routes, "_collect_public_hh_vacancies", return_value=[]),
            patch.object(admin_routes, "_collect_public_habr_vacancies", return_value=[]),
            patch.object(admin_routes, "_collect_public_superjob_vacancies", return_value=[]),
            patch.object(admin_routes.settings, "superjob_api_key", "key"),
            patch.object(admin_routes.settings, "habr_career_api_token", "tok"),
        ):
            resp = self.client.post(
                "/api/admin/vacancy-sources/probe",
                json={"query": "python"},
                headers=_auth_header(self.admin_email),
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["sources"]["hh_api"]["count"], 0)
        self.assertIsNotNone(body["sources"]["hh_api"]["error"])
        self.assertIn("timeout", body["sources"]["hh_api"]["error"])

    def test_probe_handles_missing_credentials(self) -> None:
        with (
            patch.object(admin_routes, "_search_hh_public_api_vacancies", return_value=[]),
            patch.object(admin_routes, "_search_superjob_api_vacancies", return_value=[]),
            patch.object(admin_routes, "_search_habr_api_vacancies", return_value=[]),
            patch.object(admin_routes, "_collect_public_hh_vacancies", return_value=[]),
            patch.object(admin_routes, "_collect_public_habr_vacancies", return_value=[]),
            patch.object(admin_routes, "_collect_public_superjob_vacancies", return_value=[]),
            patch.object(admin_routes.settings, "superjob_api_key", None),
            patch.object(admin_routes.settings, "habr_career_api_token", None),
        ):
            resp = self.client.post(
                "/api/admin/vacancy-sources/probe",
                json={"query": "python"},
                headers=_auth_header(self.admin_email),
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["sources"]["superjob_api"]["error"], "no SUPERJOB_API_KEY")
        self.assertEqual(body["sources"]["habr_api"]["error"], "no HABR_CAREER_API_TOKEN")


if __name__ == "__main__":
    unittest.main()
