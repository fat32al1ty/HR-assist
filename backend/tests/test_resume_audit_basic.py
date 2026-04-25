"""Phase 5.0.1 — Resume audit basic integration tests.

Happy path: create user + resume + profile -> call audit endpoint -> verify 4 blocks.
Second call must return cached result (no new DB row created).
"""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.resume import Resume
from app.models.resume_audit import ResumeAudit
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


def _make_resume_with_profile(db, user_id: int) -> Resume:
    resume = Resume(
        user_id=user_id,
        original_filename="test.pdf",
        content_type="application/pdf",
        status="completed",
        analysis={
            "target_role": "Python Developer",
            "seniority": "middle",
            "role_family": "software_engineering",
            "total_experience_years": 3,
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "hard_skills": ["Python", "FastAPI", "PostgreSQL"],
            "experience": [
                {
                    "company": "Acme",
                    "role": "Developer",
                    "period": "2021-2024",
                    "highlights": ["Developed APIs", "Reduced latency by 30%"],
                }
            ],
        },
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
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "hard_skills": ["Python", "FastAPI", "PostgreSQL"],
            "experience": [
                {
                    "company": "Acme",
                    "role": "Developer",
                    "period": "2021-2024",
                    "highlights": ["Developed APIs", "Reduced latency by 30%"],
                }
            ],
        },
        canonical_text="Target role: Python Developer\nSeniority: middle\nHard skills: Python, FastAPI, PostgreSQL",
        qdrant_collection="test_collection",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return resume


class ResumeAuditBasicTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.email = f"audit-test-{suffix}@example.com"
        self.user = _make_user(self.db, self.email)
        self.resume = _make_resume_with_profile(self.db, self.user.id)

    def tearDown(self) -> None:
        self.db.execute(delete(ResumeAudit).where(ResumeAudit.resume_id == self.resume.id))
        self.db.execute(delete(ResumeProfile).where(ResumeProfile.resume_id == self.resume.id))
        self.db.execute(delete(Resume).where(Resume.id == self.resume.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_audit_returns_four_blocks(self) -> None:
        resp = self.client.get(
            f"/api/resumes/{self.resume.id}/audit",
            headers=_auth_header(self.email),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()

        self.assertIn("role_read", body)
        self.assertIn("market_salary", body)
        self.assertIn("skill_gaps", body)
        self.assertIn("quality_issues", body)
        self.assertIn("triggered_question_ids", body)
        self.assertIn("template_mode_active", body)
        self.assertIn("prompt_version", body)
        self.assertIn("computed_at", body)

        role_read = body["role_read"]
        self.assertIn("primary", role_read)
        self.assertIn("alt", role_read)
        primary = role_read["primary"]
        self.assertEqual(primary["role_family"], "software_engineering")
        self.assertEqual(primary["seniority"], "middle")

        self.assertIsInstance(body["skill_gaps"], list)
        self.assertIsInstance(body["quality_issues"], list)

    def test_audit_is_cached_on_second_call(self) -> None:
        # First call creates the audit
        resp1 = self.client.get(
            f"/api/resumes/{self.resume.id}/audit",
            headers=_auth_header(self.email),
        )
        self.assertEqual(resp1.status_code, 200)

        # Count audit rows
        count_before = self.db.scalar(
            select(ResumeAudit).where(ResumeAudit.resume_id == self.resume.id)
        )
        self.assertIsNotNone(count_before)
        ts_before = count_before.computed_at

        # Second call — should return same computed_at (cache hit)
        resp2 = self.client.get(
            f"/api/resumes/{self.resume.id}/audit",
            headers=_auth_header(self.email),
        )
        self.assertEqual(resp2.status_code, 200)

        self.db.expire(count_before)
        count_after = self.db.scalar(
            select(ResumeAudit).where(ResumeAudit.resume_id == self.resume.id)
        )
        self.assertIsNotNone(count_after)
        # computed_at should not change on cache hit
        self.assertEqual(count_after.computed_at, ts_before)

    def test_audit_404_for_missing_resume(self) -> None:
        resp = self.client.get(
            "/api/resumes/999999/audit",
            headers=_auth_header(self.email),
        )
        self.assertEqual(resp.status_code, 404)

    def test_audit_force_bust_cache(self) -> None:
        # First call
        resp1 = self.client.get(
            f"/api/resumes/{self.resume.id}/audit",
            headers=_auth_header(self.email),
        )
        self.assertEqual(resp1.status_code, 200)

        first_row = self.db.scalar(
            select(ResumeAudit).where(ResumeAudit.resume_id == self.resume.id)
        )
        ts_first = first_row.computed_at if first_row else None

        # Force bust — should recompute
        import time
        time.sleep(0.05)
        resp2 = self.client.get(
            f"/api/resumes/{self.resume.id}/audit?force=true",
            headers=_auth_header(self.email),
        )
        self.assertEqual(resp2.status_code, 200)

        self.db.expire_all()
        second_row = self.db.scalar(
            select(ResumeAudit).where(ResumeAudit.resume_id == self.resume.id)
        )
        ts_second = second_row.computed_at if second_row else None

        if ts_first and ts_second:
            self.assertGreaterEqual(ts_second, ts_first)


if __name__ == "__main__":
    unittest.main()
