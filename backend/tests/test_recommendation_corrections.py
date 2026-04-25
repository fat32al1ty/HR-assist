"""Phase 5.2.4 — HTTP integration tests for POST /api/recommendation-corrections."""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.recommendation_correction import RecommendationCorrection
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
        email=f"rc-{suffix}@example.com",
        hashed_password=hash_password("TestPass123"),
        full_name="RC Test User",
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
    return resume


def _make_vacancy(db) -> Vacancy:
    uid = uuid.uuid4().hex[:12]
    vacancy = Vacancy(
        source="test",
        source_url=f"https://example.com/jobs/{uid}",
        title="Test Job",
        company="TestCo",
        status="indexed",
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)

    vp = VacancyProfile(
        vacancy_id=vacancy.id,
        profile={"title": "Test Job", "must_have_skills": ["Python"]},
        canonical_text="Job: Test Job",
        qdrant_collection="test_col",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(vp)
    db.commit()
    db.refresh(vp)
    return vacancy


class RecommendationCorrectionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.user = _make_user(self.db, suffix)
        self.resume = _make_resume(self.db, self.user.id)
        self.vacancy = _make_vacancy(self.db)
        # Corrections require an existing strategy row for the (resume, vacancy) pair.
        strategy = VacancyStrategy(
            resume_id=self.resume.id,
            vacancy_id=self.vacancy.id,
            prompt_version="strategy-v1",
            strategy_json={"match_highlights": [], "gap_mitigations": [], "cover_letter_draft": ""},
            cost_usd=None,
            template_mode=True,
        )
        self.db.add(strategy)
        self.db.commit()
        self.headers = _auth_header(self.user.email)

    def tearDown(self) -> None:
        self.db.execute(
            delete(RecommendationCorrection).where(
                RecommendationCorrection.resume_id == self.resume.id
            )
        )
        self.db.execute(
            delete(VacancyStrategy).where(VacancyStrategy.resume_id == self.resume.id)
        )
        self.db.execute(delete(Resume).where(Resume.id == self.resume.id))
        self.db.execute(delete(VacancyProfile).where(VacancyProfile.vacancy_id == self.vacancy.id))
        self.db.execute(delete(Vacancy).where(Vacancy.id == self.vacancy.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def _payload(self, **overrides) -> dict:
        base = {
            "resume_id": self.resume.id,
            "vacancy_id": self.vacancy.id,
            "correction_type": "match_highlight_invalid",
            "subject_index": 0,
            "subject_text": "This highlight was wrong",
        }
        base.update(overrides)
        return base

    def test_post_own_resume_correction_returns_201_with_fields_echoed(self) -> None:
        resp = self.client.post(
            "/api/recommendation-corrections",
            json=self._payload(),
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        body = resp.json()
        self.assertEqual(body["correction_type"], "match_highlight_invalid")
        self.assertEqual(body["subject_index"], 0)
        self.assertEqual(body["resume_id"], self.resume.id)
        self.assertEqual(body["vacancy_id"], self.vacancy.id)
        self.assertIn("id", body)
        self.assertIn("created_at", body)

    def test_post_another_users_resume_returns_404(self) -> None:
        suffix2 = uuid.uuid4().hex[:10]
        other_user = _make_user(self.db, suffix2)
        other_resume = _make_resume(self.db, other_user.id)
        try:
            resp = self.client.post(
                "/api/recommendation-corrections",
                json=self._payload(resume_id=other_resume.id),
                headers=self.headers,
            )
            self.assertEqual(resp.status_code, 404, resp.text)
        finally:
            self.db.execute(delete(Resume).where(Resume.id == other_resume.id))
            self.db.execute(delete(User).where(User.id == other_user.id))
            self.db.commit()

    def test_post_nonexistent_vacancy_returns_404(self) -> None:
        resp = self.client.post(
            "/api/recommendation-corrections",
            json=self._payload(vacancy_id=999999),
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_post_invalid_correction_type_returns_422(self) -> None:
        resp = self.client.post(
            "/api/recommendation-corrections",
            json=self._payload(correction_type="foo"),
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 422, resp.text)

    def test_post_subject_index_negative_returns_422(self) -> None:
        resp = self.client.post(
            "/api/recommendation-corrections",
            json=self._payload(subject_index=-1),
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 422, resp.text)

    def test_post_subject_index_above_10_returns_422(self) -> None:
        resp = self.client.post(
            "/api/recommendation-corrections",
            json=self._payload(subject_index=11),
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 422, resp.text)

    def test_unauthenticated_returns_401(self) -> None:
        resp = self.client.post(
            "/api/recommendation-corrections",
            json=self._payload(),
        )
        self.assertEqual(resp.status_code, 401, resp.text)

    def test_post_without_existing_strategy_returns_409(self) -> None:
        # Drop the strategy row to simulate a stray correction with no rendered
        # strategy in front of the user.
        self.db.execute(
            delete(VacancyStrategy).where(VacancyStrategy.resume_id == self.resume.id)
        )
        self.db.commit()
        resp = self.client.post(
            "/api/recommendation-corrections",
            json=self._payload(),
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 409, resp.text)


if __name__ == "__main__":
    unittest.main()
