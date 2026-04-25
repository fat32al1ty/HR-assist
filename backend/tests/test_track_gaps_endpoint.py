"""Smoke tests for GET /api/resumes/{resume_id}/track-gaps.

Verifies auth gating, ownership checks, 404 on missing resume,
and correct response shape for the happy path.
"""

from __future__ import annotations

import uuid
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.resume import Resume
from app.models.resume_profile import ResumeProfile
from app.models.track_gap_analysis import TrackGapAnalysis
from app.models.user import User


def _make_user(db, email: str) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("TestPass123"),
        full_name="Endpoint Test User",
        is_active=True,
        email_verified=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=email)}"}


def _make_resume(db, user_id: int) -> Resume:
    resume = Resume(
        user_id=user_id,
        original_filename="cv.pdf",
        content_type="application/pdf",
        status="completed",
        analysis={},
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


class TrackGapsEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        s = uuid.uuid4().hex[:8]

        # Primary user + resume
        self.email = f"tge-{s}@example.com"
        self.user = _make_user(self.db, self.email)
        self.resume = _make_resume(self.db, self.user.id)

        # Second user (for ownership test)
        self.email2 = f"tge2-{s}@example.com"
        self.user2 = _make_user(self.db, self.email2)

    def tearDown(self) -> None:
        db = self.db
        db.execute(delete(TrackGapAnalysis).where(TrackGapAnalysis.resume_id == self.resume.id))
        db.execute(delete(ResumeProfile).where(ResumeProfile.resume_id == self.resume.id))
        db.execute(delete(Resume).where(Resume.id == self.resume.id))
        db.execute(delete(User).where(User.id == self.user.id))
        db.execute(delete(User).where(User.id == self.user2.id))
        db.commit()
        db.close()

    def test_own_resume_returns_200_with_valid_shape(self) -> None:
        resp = self.client.get(
            f"/api/resumes/{self.resume.id}/track-gaps",
            headers=_auth(self.email),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        # Top-level keys
        for track in ("match", "grow", "stretch"):
            self.assertIn(track, body, f"Missing top-level key: {track}")
            block = body[track]
            self.assertIn("track", block)
            self.assertIn("vacancies_count", block)
            self.assertIn("top_gaps", block)
            self.assertIn("softer_subset_count", block)
            self.assertIsInstance(block["top_gaps"], list)
            self.assertIsInstance(block["vacancies_count"], int)
            self.assertIsInstance(block["softer_subset_count"], int)

    def test_another_users_resume_returns_404(self) -> None:
        """user2 tries to access user1's resume → 404 (not a leak)."""
        resp = self.client.get(
            f"/api/resumes/{self.resume.id}/track-gaps",
            headers=_auth(self.email2),
        )
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_nonexistent_resume_returns_404(self) -> None:
        resp = self.client.get(
            "/api/resumes/999999999/track-gaps",
            headers=_auth(self.email),
        )
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_unauthenticated_request_returns_401(self) -> None:
        resp = self.client.get(f"/api/resumes/{self.resume.id}/track-gaps")
        self.assertEqual(resp.status_code, 401, resp.text)


if __name__ == "__main__":
    unittest.main()
