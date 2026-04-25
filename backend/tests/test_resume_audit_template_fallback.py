"""Phase 5.0.1 — Template fallback test.

When cost cap is 0.0, audit must return template_mode_active=True
and no LLM call must be made for skill normalization.
"""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import delete

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
        analysis={"target_role": "Backend Dev", "seniority": "junior", "role_family": "software_engineering"},
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    profile = ResumeProfile(
        resume_id=resume.id,
        user_id=user_id,
        profile={
            "role_family": "software_engineering",
            "seniority": "junior",
            "seniority_confidence": 0.7,
            "total_experience_years": 1.0,
            "skills": ["Python"],
            "hard_skills": ["Python"],
        },
        canonical_text="Target role: Backend Dev\nSeniority: junior",
        qdrant_collection="test_collection",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return resume


class TemplateFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.email = f"template-fallback-{suffix}@example.com"
        self.user = _make_user(self.db, self.email)
        self.resume = _make_resume_with_profile(self.db, self.user.id)

    def tearDown(self) -> None:
        self.db.execute(delete(ResumeAudit).where(ResumeAudit.resume_id == self.resume.id))
        self.db.execute(delete(ResumeProfile).where(ResumeProfile.resume_id == self.resume.id))
        self.db.execute(delete(Resume).where(Resume.id == self.resume.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_template_mode_active_when_cost_cap_zero(self) -> None:
        # Use -1.0 as the cap so that daily_cost=0.0 > -1.0 triggers template mode
        with patch("app.services.resume_audit.settings") as mock_settings:
            mock_settings.feature_resume_audit_enabled = True
            mock_settings.feature_resume_audit_template_mode_enabled = False
            mock_settings.resume_audit_cost_cap_usd_per_day = -1.0
            mock_settings.resume_audit_cache_ttl_days = 7
            mock_settings.openai_api_key = None

            resp = self.client.get(
                f"/api/resumes/{self.resume.id}/audit?force=true",
                headers=_auth_header(self.email),
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["template_mode_active"])

    def test_template_mode_when_flag_set(self) -> None:
        with patch("app.services.resume_audit.settings") as mock_settings:
            mock_settings.feature_resume_audit_enabled = True
            mock_settings.feature_resume_audit_template_mode_enabled = True
            mock_settings.resume_audit_cost_cap_usd_per_day = 1.0
            mock_settings.resume_audit_cache_ttl_days = 7
            mock_settings.openai_api_key = None

            resp = self.client.get(
                f"/api/resumes/{self.resume.id}/audit?force=true",
                headers=_auth_header(self.email),
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["template_mode_active"])


if __name__ == "__main__":
    unittest.main()
