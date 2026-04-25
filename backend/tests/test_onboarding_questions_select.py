"""Phase 5.0.2 — Onboarding question selection tests.

Fixture resume with ambiguous seniority (4-6 years) -> seniority_ambiguous
must appear in the returned 5. Answer it -> second call drops it.
"""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.resume import Resume
from app.models.resume_clarification import ResumeClarification
from app.models.resume_profile import ResumeProfile
from app.models.user import User


def _make_user(db, email: str) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("TestPass123"),
        full_name="Test User",
        is_active=True,
        email_verified=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(email: str) -> dict[str, str]:
    token = create_access_token(subject=email)
    return {"Authorization": f"Bearer {token}"}


def _make_resume_ambiguous_seniority(db, user_id: int) -> Resume:
    """5 years experience = right in the seniority_ambiguous zone (4-6 years, not explicit)."""
    resume = Resume(
        user_id=user_id,
        original_filename="test.pdf",
        content_type="application/pdf",
        status="completed",
        analysis={"target_role": "Backend Dev", "seniority": "middle"},
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
            "seniority_confidence": 0.5,
            "total_experience_years": 5.0,
            "role_is_technical": True,
            "skills": ["Python", "Django"],
            "hard_skills": ["Python", "Django"],
        },
        canonical_text="Target role: Backend Dev\nSeniority: middle\nExperience: 5 years",
        qdrant_collection="test_collection",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return resume


class OnboardingQuestionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.email = f"onboarding-test-{suffix}@example.com"
        self.user = _make_user(self.db, self.email)
        self.resume = _make_resume_ambiguous_seniority(self.db, self.user.id)

    def tearDown(self) -> None:
        self.db.execute(
            delete(ResumeClarification).where(ResumeClarification.resume_id == self.resume.id)
        )
        self.db.execute(delete(ResumeProfile).where(ResumeProfile.resume_id == self.resume.id))
        self.db.execute(delete(Resume).where(Resume.id == self.resume.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_seniority_ambiguous_in_questions(self) -> None:
        resp = self.client.get(
            f"/api/resumes/{self.resume.id}/onboarding/questions",
            headers=_auth_header(self.email),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        questions = resp.json()
        self.assertIsInstance(questions, list)
        self.assertLessEqual(len(questions), 5)

        ids = [q["id"] for q in questions]
        self.assertIn("seniority_ambiguous", ids)

    def test_answered_question_dropped_from_list(self) -> None:
        # Verify seniority_ambiguous is present
        resp = self.client.get(
            f"/api/resumes/{self.resume.id}/onboarding/questions",
            headers=_auth_header(self.email),
        )
        self.assertEqual(resp.status_code, 200)
        ids_before = [q["id"] for q in resp.json()]
        self.assertIn("seniority_ambiguous", ids_before)

        # Answer it
        answer_resp = self.client.post(
            f"/api/resumes/{self.resume.id}/onboarding/answer",
            headers=_auth_header(self.email),
            json={"question_id": "seniority_ambiguous", "answer_value": "senior"},
        )
        self.assertEqual(answer_resp.status_code, 204)

        # Second call — seniority_ambiguous should be gone
        resp2 = self.client.get(
            f"/api/resumes/{self.resume.id}/onboarding/questions",
            headers=_auth_header(self.email),
        )
        self.assertEqual(resp2.status_code, 200)
        ids_after = [q["id"] for q in resp2.json()]
        self.assertNotIn("seniority_ambiguous", ids_after)

    def test_answers_endpoint_returns_existing(self) -> None:
        # Post an answer first
        self.client.post(
            f"/api/resumes/{self.resume.id}/onboarding/answer",
            headers=_auth_header(self.email),
            json={"question_id": "salary_missing", "answer_value": "150000"},
        )

        resp = self.client.get(
            f"/api/resumes/{self.resume.id}/onboarding/answers",
            headers=_auth_header(self.email),
        )
        self.assertEqual(resp.status_code, 200)
        answers = resp.json()
        self.assertIsInstance(answers, list)
        q_ids = [a["question_id"] for a in answers]
        self.assertIn("salary_missing", q_ids)

    def test_questions_404_for_missing_resume(self) -> None:
        resp = self.client.get(
            "/api/resumes/999999/onboarding/questions",
            headers=_auth_header(self.email),
        )
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
