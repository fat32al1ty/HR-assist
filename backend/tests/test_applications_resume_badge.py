"""Phase 1.7 PR #6 — application creation stamps resume_id and exposes label.

The Kanban stays common but each card needs a resume badge, so the create
endpoint must pin the user's currently-active resume and ApplicationRead
must surface the label (or None if the resume was later deleted).
"""

from __future__ import annotations

import unittest
import uuid

from sqlalchemy import delete

from app.api.routes.applications import create_application_endpoint
from app.db.session import SessionLocal
from app.models.application import Application
from app.models.resume import Resume
from app.models.user import User
from app.models.vacancy import Vacancy
from app.repositories.resumes import activate_resume, create_resume_record, update_resume_label
from app.schemas.application import ApplicationCreateRequest


class ApplicationResumeBadgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"kanban-{self.suffix}@example.com",
            hashed_password="test-hash",
            full_name="Kanban Tester",
            is_active=True,
            email_verified=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume_a = create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="ic.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/ic-{self.suffix}.pdf",
        )
        update_resume_label(self.db, self.resume_a, label="IC Staff")

        self.vacancy = Vacancy(
            source="test",
            source_url=f"https://example.test/vacancy/{self.suffix}",
            title="Staff Backend",
            company="Co",
            location="Москва",
            status="indexed",
        )
        self.db.add(self.vacancy)
        self.db.commit()
        self.db.refresh(self.vacancy)

    def tearDown(self) -> None:
        self.db.execute(delete(Application).where(Application.user_id == self.user.id))
        self.db.execute(delete(Vacancy).where(Vacancy.id == self.vacancy.id))
        self.db.execute(delete(Resume).where(Resume.user_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_application_is_stamped_with_active_resume_label(self) -> None:
        result = create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id, status="draft"),
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(result.resume_id, self.resume_a.id)
        self.assertEqual(result.resume_label, "IC Staff")

    def test_application_tracks_whichever_resume_is_active(self) -> None:
        resume_b = create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="mgmt.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/mgmt-{self.suffix}.pdf",
        )
        update_resume_label(self.db, resume_b, label="Mgmt")
        activate_resume(self.db, resume=resume_b)

        result = create_application_endpoint(
            payload=ApplicationCreateRequest(vacancy_id=self.vacancy.id, status="draft"),
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(result.resume_id, resume_b.id)
        self.assertEqual(result.resume_label, "Mgmt")


if __name__ == "__main__":
    unittest.main()
