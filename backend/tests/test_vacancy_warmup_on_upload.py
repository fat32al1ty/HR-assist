import unittest
import uuid
from threading import Event
from unittest.mock import patch

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.services import vacancy_warmup
from app.services.vacancy_warmup import trigger_warmup_for_resume


class WarmupOnUploadTest(unittest.TestCase):
    """Phase 2.0 PR A4 — trigger_warmup_for_resume fires discover_and_index_vacancies
    for the uploader's resume in a background thread, so the index is already
    primed when the user clicks "Обновить подбор" for the first time.
    """

    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"warmup-upload-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Warmup Upload Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="warmup.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/{suffix}.pdf",
            status="completed",
            analysis={
                "target_role": "Backend Engineer",
                "specialization": "Python",
                "hard_skills": ["Python", "FastAPI"],
                "matching_keywords": ["backend", "observability"],
            },
            error_message=None,
        )
        self.db.add(self.resume)
        self.db.commit()
        self.db.refresh(self.resume)

    def tearDown(self) -> None:
        self.db.execute(
            delete(UserVacancyFeedback).where(UserVacancyFeedback.user_id == self.user.id)
        )
        self.db.execute(delete(Resume).where(Resume.user_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_trigger_fires_discover_with_resume_derived_query(self) -> None:
        call_captured: dict = {}
        done = Event()

        def _fake_discover(_db, *, query, count, **kwargs):
            call_captured["query"] = query
            call_captured["count"] = count
            call_captured["kwargs"] = kwargs
            done.set()

            class _Result:
                class metrics:
                    pass

            return _Result()

        with patch.object(
            vacancy_warmup, "discover_and_index_vacancies", side_effect=_fake_discover
        ):
            thread = trigger_warmup_for_resume(user_id=self.user.id, resume_id=self.resume.id)
            self.assertIsNotNone(thread)
            thread.join(timeout=5.0)
            self.assertFalse(thread.is_alive())

        self.assertTrue(done.is_set())
        # Query must reflect resume analysis (role, skills, keywords).
        query = call_captured["query"]
        self.assertIn("Backend Engineer", query)
        # Budget must be the "on upload" count, not the small per-cycle one.
        self.assertGreaterEqual(call_captured["count"], 25)
        self.assertGreaterEqual(call_captured["kwargs"].get("max_analyzed", 0), 25)

    def test_trigger_skips_when_resume_missing(self) -> None:
        with patch.object(vacancy_warmup, "discover_and_index_vacancies") as mock_discover:
            thread = trigger_warmup_for_resume(user_id=self.user.id, resume_id=999_999_999)
            self.assertIsNotNone(thread)
            thread.join(timeout=5.0)

        mock_discover.assert_not_called()

    def test_trigger_skips_when_resume_belongs_to_other_user(self) -> None:
        with patch.object(vacancy_warmup, "discover_and_index_vacancies") as mock_discover:
            thread = trigger_warmup_for_resume(user_id=self.user.id + 999, resume_id=self.resume.id)
            self.assertIsNotNone(thread)
            thread.join(timeout=5.0)

        mock_discover.assert_not_called()

    def test_trigger_disabled_via_settings_returns_none(self) -> None:
        with patch.object(vacancy_warmup.settings, "vacancy_warmup_on_resume_upload", False):
            with patch.object(vacancy_warmup, "discover_and_index_vacancies") as mock_discover:
                thread = trigger_warmup_for_resume(user_id=self.user.id, resume_id=self.resume.id)
                self.assertIsNone(thread)
                mock_discover.assert_not_called()

    def test_trigger_swallows_discover_exceptions(self) -> None:
        def _boom(*_args, **_kwargs):
            raise RuntimeError("network down")

        with patch.object(vacancy_warmup, "discover_and_index_vacancies", side_effect=_boom):
            with self.assertLogs(vacancy_warmup.logger, level="WARNING") as cm:
                thread = trigger_warmup_for_resume(user_id=self.user.id, resume_id=self.resume.id)
                thread.join(timeout=5.0)

        # Exception is logged but never leaks back to the HTTP request.
        self.assertTrue(any("resume_upload_warmup_failed" in line for line in cm.output))
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
