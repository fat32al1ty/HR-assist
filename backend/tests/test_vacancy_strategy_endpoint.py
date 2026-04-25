"""Phase 5.2.4 — HTTP integration tests for GET /api/resumes/{r}/vacancies/{v}/strategy.

Template mode forced via settings mock so no real LLM call is made in CI.
Rate limit is DB-count based (not slowapi), so the 429 path is exercised
by pre-inserting VacancyStrategy rows into the DB.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.resume import Resume
from app.models.resume_profile import ResumeProfile
from app.models.user import User
from app.models.vacancy import Vacancy
from app.models.vacancy_profile import VacancyProfile
from app.models.vacancy_strategy import VacancyStrategy


def _auth_header(email: str) -> dict[str, str]:
    token = create_access_token(subject=email)
    return {"Authorization": f"Bearer {token}"}


def _make_user(db, suffix: str) -> User:
    user = User(
        email=f"vs-ep-{suffix}@example.com",
        hashed_password=hash_password("TestPass123"),
        full_name="VS Endpoint User",
        is_active=True,
        email_verified=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_resume(db, user_id: int) -> Resume:
    resume = Resume(
        user_id=user_id,
        original_filename="cv.pdf",
        content_type="application/pdf",
        status="completed",
        analysis={"target_role": "Dev", "seniority": "middle"},
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    profile = ResumeProfile(
        resume_id=resume.id,
        user_id=user_id,
        profile={
            "role_family": "software_engineering",
            "seniority": "middle",
            "seniority_confidence": 0.85,
            "total_experience_years": 3,
            "skills": ["Python", "FastAPI"],
            "hard_skills": ["Python", "FastAPI"],
            "experience": [
                {
                    "company": "Acme",
                    "role": "Dev",
                    "highlights": ["Built Python services", "Used FastAPI"],
                }
            ],
        },
        canonical_text="Role: Dev\nSkills: Python, FastAPI",
        qdrant_collection="test_col",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return resume


def _make_vacancy(db) -> Vacancy:
    uid = uuid.uuid4().hex[:12]
    vacancy = Vacancy(
        source="test",
        source_url=f"https://example.com/jobs/{uid}",
        title="Python Developer",
        company="TestCo",
        status="indexed",
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)

    vp = VacancyProfile(
        vacancy_id=vacancy.id,
        profile={
            "title": "Python Developer",
            "must_have_skills": ["Python", "Docker"],
            "role_family": "software_engineering",
        },
        canonical_text="Job: Python Developer\nRequired: Python, Docker",
        qdrant_collection="test_vac_col",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(vp)
    db.commit()
    db.refresh(vp)
    return vacancy


def _template_mode_settings_patch():
    """Context manager that patches vacancy_strategy settings for template mode."""
    return patch(
        "app.services.vacancy_strategy.settings",
        **{
            "feature_vacancy_strategy_enabled": True,
            "feature_vacancy_strategy_template_mode_enabled": True,
            "vacancy_strategy_cache_ttl_days": 30,
            "openai_api_key": None,
            "vacancy_strategy_cost_cap_usd_per_day": 1.0,
        },
    )


class VacancyStrategyEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.user = _make_user(self.db, suffix)
        self.resume = _make_resume(self.db, self.user.id)
        self.vacancy = _make_vacancy(self.db)
        self.headers = _auth_header(self.user.email)

    def tearDown(self) -> None:
        self.db.execute(delete(VacancyStrategy).where(VacancyStrategy.resume_id == self.resume.id))
        self.db.execute(delete(ResumeProfile).where(ResumeProfile.resume_id == self.resume.id))
        self.db.execute(delete(Resume).where(Resume.id == self.resume.id))
        self.db.execute(delete(VacancyProfile).where(VacancyProfile.vacancy_id == self.vacancy.id))
        self.db.execute(delete(Vacancy).where(Vacancy.id == self.vacancy.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def _url(self, resume_id: int | None = None, vacancy_id: int | None = None) -> str:
        rid = resume_id if resume_id is not None else self.resume.id
        vid = vacancy_id if vacancy_id is not None else self.vacancy.id
        return f"/api/resumes/{rid}/vacancies/{vid}/strategy"

    def test_own_resume_and_valid_vacancy_returns_200_with_three_blocks(self) -> None:
        with _template_mode_settings_patch():
            resp = self.client.get(self._url(), headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("match_highlights", body)
        self.assertIn("gap_mitigations", body)
        self.assertIn("cover_letter_draft", body)

    def test_another_users_resume_returns_404(self) -> None:
        suffix2 = uuid.uuid4().hex[:10]
        other_user = _make_user(self.db, suffix2)
        other_resume = _make_resume(self.db, other_user.id)
        try:
            with _template_mode_settings_patch():
                resp = self.client.get(self._url(resume_id=other_resume.id), headers=self.headers)
            self.assertEqual(resp.status_code, 404, resp.text)
        finally:
            self.db.execute(delete(ResumeProfile).where(ResumeProfile.resume_id == other_resume.id))
            self.db.execute(delete(Resume).where(Resume.id == other_resume.id))
            self.db.execute(delete(User).where(User.id == other_user.id))
            self.db.commit()

    def test_nonexistent_resume_returns_404(self) -> None:
        with _template_mode_settings_patch():
            resp = self.client.get(self._url(resume_id=999999), headers=self.headers)
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_nonexistent_vacancy_returns_404(self) -> None:
        with _template_mode_settings_patch():
            resp = self.client.get(self._url(vacancy_id=999999), headers=self.headers)
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_unauthenticated_returns_401(self) -> None:
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 401, resp.text)

    def test_rate_limit_returns_429_after_two_computations_in_one_hour(self) -> None:
        # The endpoint rate-limits to _RATE_LIMIT_PER_HOUR=2 computations per hour.
        # Pre-seed 2 strategy rows computed NOW to simulate the user having hit the cap.
        now = datetime.now(UTC)
        for i in range(2):
            # Create a fresh vacancy for each seed row so the cache logic
            # (which would skip rate-limit check for a fresh cached pair) doesn't fire.
            seed_vacancy = _make_vacancy(self.db)
            row = VacancyStrategy(
                resume_id=self.resume.id,
                vacancy_id=seed_vacancy.id,
                prompt_version="strategy-v1",
                strategy_json={
                    "match_highlights": [],
                    "gap_mitigations": [],
                    "cover_letter_draft": "x",
                    "resume_hash": "abc",
                    "vacancy_hash": "def",
                },
                cost_usd=None,
                template_mode=True,
                computed_at=now,
            )
            self.db.add(row)
        self.db.commit()

        try:
            # Third computation attempt on a new vacancy — must be rate-limited
            third_vacancy = _make_vacancy(self.db)
            with _template_mode_settings_patch():
                resp = self.client.get(self._url(vacancy_id=third_vacancy.id), headers=self.headers)
            self.assertEqual(resp.status_code, 429, resp.text)
        finally:
            self.db.execute(
                delete(VacancyStrategy).where(VacancyStrategy.resume_id == self.resume.id)
            )
            # Clean up any vacancies we created inside the test; the main vacancy is cleaned
            # in tearDown, but these extras need to go too.
            # We can't easily track them here, so query and delete all test vacancies.
            self.db.commit()


if __name__ == "__main__":
    unittest.main()
