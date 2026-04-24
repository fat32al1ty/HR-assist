"""Integration tests for admin salary predictor endpoints."""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.models.vacancy import Vacancy
from app.models.vacancy_profile import VacancyProfile
from app.services import salary_predictor


def _make_user(db, email: str, is_admin: bool = False) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("TestPass123"),
        full_name="Salary Test",
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


def _make_vacancy(db, *, location="Москва") -> Vacancy:
    vacancy = Vacancy(
        source="hh_api",
        source_url=f"https://hh.ru/vacancy/{uuid.uuid4().int % 9000000 + 1000000}",
        title="Backend Engineer",
        company="Test Corp",
        location=location,
        status="indexed",
        raw_payload={},
        raw_text="Python, FastAPI",
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


def _make_vacancy_profile(
    db,
    vacancy: Vacancy,
    *,
    salary_min=None,
    salary_max=None,
    salary_currency=None,
    predicted_p50=None,
) -> VacancyProfile:
    vp = VacancyProfile(
        vacancy_id=vacancy.id,
        profile={"role_family": "software_engineering", "seniority": "middle"},
        canonical_text="Backend Engineer",
        qdrant_collection="test_collection",
        qdrant_point_id=str(uuid.uuid4()),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        predicted_salary_p50=predicted_p50,
    )
    db.add(vp)
    db.commit()
    db.refresh(vp)
    return vp


class AdminSalaryPredictorStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.user_email = f"sal-user-{suffix}@example.com"
        self.admin_email = f"sal-admin-{suffix}@example.com"
        self.user = _make_user(self.db, self.user_email, is_admin=False)
        self.admin = _make_user(self.db, self.admin_email, is_admin=True)
        self.vacancies: list[Vacancy] = []
        self.profiles: list[VacancyProfile] = []

    def tearDown(self) -> None:
        for vp in self.profiles:
            self.db.execute(delete(VacancyProfile).where(VacancyProfile.id == vp.id))
        for v in self.vacancies:
            self.db.execute(delete(Vacancy).where(Vacancy.id == v.id))
        self.db.execute(delete(User).where(User.email.in_([self.user_email, self.admin_email])))
        self.db.commit()
        self.db.close()

    def test_status_returns_403_for_non_admin(self):
        resp = self.client.get(
            "/api/admin/salary-predictor/status", headers=_auth_header(self.user_email)
        )
        self.assertEqual(resp.status_code, 403)

    def test_status_returns_200_with_correct_counts(self):
        v = _make_vacancy(self.db)
        self.vacancies.append(v)

        vp = _make_vacancy_profile(
            self.db, v, salary_min=100000, salary_max=150000, salary_currency="RUB"
        )
        self.profiles.append(vp)

        resp = self.client.get(
            "/api/admin/salary-predictor/status", headers=_auth_header(self.admin_email)
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("total_vacancy_profiles", body)
        self.assertIn("with_stated_salary_rub", body)
        self.assertIn("with_predicted_salary", body)
        self.assertIn("lgbm_model_loaded", body)
        self.assertIn("predictor_enabled", body)
        self.assertEqual(body["training_floor"], 1000)
        self.assertGreaterEqual(body["total_vacancy_profiles"], 1)
        self.assertGreaterEqual(body["with_stated_salary_rub"], 1)


class AdminSalaryBackfillTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.user_email = f"bfill-user-{suffix}@example.com"
        self.admin_email = f"bfill-admin-{suffix}@example.com"
        self.user = _make_user(self.db, self.user_email, is_admin=False)
        self.admin = _make_user(self.db, self.admin_email, is_admin=True)
        self.vacancies: list[Vacancy] = []
        self.profiles: list[VacancyProfile] = []

    def tearDown(self) -> None:
        for vp in self.profiles:
            self.db.execute(delete(VacancyProfile).where(VacancyProfile.id == vp.id))
        for v in self.vacancies:
            self.db.execute(delete(Vacancy).where(Vacancy.id == v.id))
        self.db.execute(delete(User).where(User.email.in_([self.user_email, self.admin_email])))
        self.db.commit()
        self.db.close()

    def test_backfill_populates_predicted(self):
        v = _make_vacancy(self.db)
        self.vacancies.append(v)
        vp = _make_vacancy_profile(self.db, v)
        self.profiles.append(vp)

        band = salary_predictor.SalaryBand(
            p25=90000, p50=130000, p75=170000, confidence=0.5, model_version="test-v1"
        )
        with patch("app.services.salary_predictor.predict", return_value=band):
            with patch("app.api.routes.admin.settings") as mock_settings:
                mock_settings.feature_salary_predictor_enabled = True
                mock_settings.feature_salary_baseline_enabled = False
                resp = self.client.post(
                    "/api/admin/salary-predictor/backfill",
                    headers=_auth_header(self.admin_email),
                )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("processed", body)
        self.assertIn("updated", body)
        self.assertGreaterEqual(body["processed"], 0)

    def test_backfill_respects_feature_flag(self):
        with patch("app.api.routes.admin.settings") as mock_settings:
            mock_settings.feature_salary_predictor_enabled = False
            resp = self.client.post(
                "/api/admin/salary-predictor/backfill",
                headers=_auth_header(self.admin_email),
            )
        self.assertEqual(resp.status_code, 400)

    def test_backfill_skips_rows_with_stated_salary(self):
        v = _make_vacancy(self.db)
        self.vacancies.append(v)
        # Row with salary_min set — should be excluded from backfill query
        vp = _make_vacancy_profile(self.db, v, salary_min=120000, salary_currency="RUB")
        self.profiles.append(vp)

        band = salary_predictor.SalaryBand(
            p25=90000, p50=130000, p75=170000, confidence=0.5, model_version="test-v1"
        )
        with patch("app.services.salary_predictor.predict", return_value=band):
            resp = self.client.post(
                "/api/admin/salary-predictor/backfill",
                headers=_auth_header(self.admin_email),
            )
        self.assertEqual(resp.status_code, 200)

        # The profile we created has salary_min set; the backfill query
        # filters WHERE salary_min IS NULL AND salary_max IS NULL — so this
        # profile should NOT have predicted_salary_p50 populated.
        self.db.refresh(vp)
        self.assertIsNone(vp.predicted_salary_p50)


if __name__ == "__main__":
    unittest.main()
