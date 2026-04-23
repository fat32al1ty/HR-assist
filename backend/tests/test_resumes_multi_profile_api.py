"""Phase 1.7 PR #5 — multi-profile API tests.

Covers the three new endpoints that make the resume switcher work:
  - GET  /resumes/active
  - POST /resumes/{id}/activate
  - PATCH /resumes/{id}   (label editor)

Plus label validation on the schema.
"""

from __future__ import annotations

import unittest
import uuid

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.api.routes.resumes import (
    activate_resume_endpoint,
    get_active_resume,
    patch_resume,
)
from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user import User
from app.repositories.resumes import create_resume_record
from app.schemas.resume import RESUME_LABEL_MAX, ResumeLabelUpdate


class ResumeLabelUpdateSchemaTest(unittest.TestCase):
    def test_label_is_trimmed(self) -> None:
        payload = ResumeLabelUpdate(label="  Management  ")
        self.assertEqual(payload.label, "Management")

    def test_blank_label_becomes_none(self) -> None:
        payload = ResumeLabelUpdate(label="   ")
        self.assertIsNone(payload.label)

    def test_rejects_overlong_label(self) -> None:
        with self.assertRaises(ValidationError):
            ResumeLabelUpdate(label="x" * (RESUME_LABEL_MAX + 1))


class MultiProfileApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"mp-api-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="MP API Tester",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume_a = create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="ic.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/ic-{suffix}.pdf",
        )
        self.resume_b = create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="mgmt.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/mgmt-{suffix}.pdf",
        )

    def tearDown(self) -> None:
        self.db.execute(delete(Resume).where(Resume.user_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_get_active_returns_the_active_resume(self) -> None:
        result = get_active_resume(current_user=self.user, db=self.db)
        self.assertEqual(result.id, self.resume_a.id)
        self.assertTrue(result.is_active)

    def test_get_active_returns_404_when_no_resume(self) -> None:
        # Remove all resumes for this user
        self.db.execute(delete(Resume).where(Resume.user_id == self.user.id))
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            get_active_resume(current_user=self.user, db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "no_active_resume")

    def test_activate_flips_active_resume(self) -> None:
        result = activate_resume_endpoint(
            resume_id=self.resume_b.id, current_user=self.user, db=self.db
        )
        self.assertEqual(result.id, self.resume_b.id)
        self.assertTrue(result.is_active)

        # Only one active remains
        active_ids = list(
            self.db.scalars(
                select(Resume.id).where(Resume.user_id == self.user.id, Resume.is_active.is_(True))
            )
        )
        self.assertEqual(active_ids, [self.resume_b.id])

    def test_activate_rejects_other_users_resume(self) -> None:
        other_suffix = uuid.uuid4().hex[:10]
        other = User(
            email=f"mp-api-other-{other_suffix}@example.com",
            hashed_password="test-hash",
            full_name="Other",
            is_active=True,
        )
        self.db.add(other)
        self.db.commit()
        self.db.refresh(other)
        try:
            with self.assertRaises(HTTPException) as ctx:
                activate_resume_endpoint(resume_id=self.resume_a.id, current_user=other, db=self.db)
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            self.db.execute(delete(User).where(User.id == other.id))
            self.db.commit()

    def test_patch_resume_sets_label(self) -> None:
        result = patch_resume(
            resume_id=self.resume_a.id,
            payload=ResumeLabelUpdate(label="  IC Staff "),
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(result.id, self.resume_a.id)
        self.assertEqual(result.label, "IC Staff")

    def test_patch_resume_clears_label_when_blank(self) -> None:
        patch_resume(
            resume_id=self.resume_a.id,
            payload=ResumeLabelUpdate(label="temp"),
            current_user=self.user,
            db=self.db,
        )
        result = patch_resume(
            resume_id=self.resume_a.id,
            payload=ResumeLabelUpdate(label=""),
            current_user=self.user,
            db=self.db,
        )
        self.assertIsNone(result.label)

    def test_patch_resume_rejects_other_user(self) -> None:
        other_suffix = uuid.uuid4().hex[:10]
        other = User(
            email=f"mp-api-other2-{other_suffix}@example.com",
            hashed_password="test-hash",
            full_name="Other",
            is_active=True,
        )
        self.db.add(other)
        self.db.commit()
        self.db.refresh(other)
        try:
            with self.assertRaises(HTTPException) as ctx:
                patch_resume(
                    resume_id=self.resume_a.id,
                    payload=ResumeLabelUpdate(label="hijack"),
                    current_user=other,
                    db=self.db,
                )
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            self.db.execute(delete(User).where(User.id == other.id))
            self.db.commit()


if __name__ == "__main__":
    unittest.main()
