"""Integration tests for vacancy 'seen' feedback.

Covers:
- POST /feedback/seen marks vacancy as seen (idempotent)
- POST /feedback/unseen un-marks vacancy as seen
- GET /feedback/seen returns VacancyMatchRead list
- seen vacancies are excluded from _excluded_ids_for_active_resume
"""

import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import delete

from app.api.routes.vacancies import (
    mark_vacancy_seen,
    seen_vacancies,
    unmark_vacancy_seen,
    _excluded_ids_for_active_resume,
)
from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.models.vacancy import Vacancy
from app.schemas.vacancy import VacancyFeedbackRequest


class VacancyFeedbackSeenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"seen-fb-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Seen Feedback Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="seen-test.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/{suffix}.pdf",
            status="completed",
            analysis={"target_role": "backend engineer"},
            error_message=None,
            is_active=True,
        )
        self.db.add(self.resume)

        self.vacancy = Vacancy(
            source="hh_api",
            source_url=f"https://hh.ru/vacancy/{uuid.uuid4().int % 1000000}",
            title="DevOps Engineer Seen Test",
            company="Seen Corp",
            location="Москва",
            status="indexed",
            raw_payload={},
            raw_text="DevOps, monitoring",
            error_message=None,
        )
        self.db.add(self.vacancy)
        self.db.commit()
        self.db.refresh(self.resume)
        self.db.refresh(self.vacancy)

    def tearDown(self) -> None:
        self.db.execute(
            delete(UserVacancyFeedback).where(UserVacancyFeedback.user_id == self.user.id)
        )
        self.db.execute(delete(Vacancy).where(Vacancy.id == self.vacancy.id))
        self.db.execute(delete(Resume).where(Resume.user_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_mark_seen_returns_correct_shape(self) -> None:
        payload = VacancyFeedbackRequest(vacancy_id=self.vacancy.id)
        resp = mark_vacancy_seen(payload=payload, current_user=self.user, db=self.db)
        self.assertEqual(resp.vacancy_id, self.vacancy.id)
        self.assertTrue(resp.seen)
        self.assertFalse(resp.liked)
        self.assertFalse(resp.disliked)

    def test_mark_seen_is_idempotent(self) -> None:
        payload = VacancyFeedbackRequest(vacancy_id=self.vacancy.id)
        mark_vacancy_seen(payload=payload, current_user=self.user, db=self.db)
        resp = mark_vacancy_seen(payload=payload, current_user=self.user, db=self.db)
        self.assertTrue(resp.seen)

    def test_unseen_clears_seen_flag(self) -> None:
        payload = VacancyFeedbackRequest(vacancy_id=self.vacancy.id)
        mark_vacancy_seen(payload=payload, current_user=self.user, db=self.db)
        resp = unmark_vacancy_seen(payload=payload, current_user=self.user, db=self.db)
        self.assertFalse(resp.seen)

    def test_get_seen_vacancies_lists_marked_vacancy(self) -> None:
        payload = VacancyFeedbackRequest(vacancy_id=self.vacancy.id)
        mark_vacancy_seen(payload=payload, current_user=self.user, db=self.db)
        result = seen_vacancies(limit=100, current_user=self.user, db=self.db)
        self.assertTrue(any(item.vacancy_id == self.vacancy.id for item in result))

    def test_seen_vacancy_excluded_from_active_resume_ids(self) -> None:
        payload = VacancyFeedbackRequest(vacancy_id=self.vacancy.id)
        mark_vacancy_seen(payload=payload, current_user=self.user, db=self.db)
        excluded = _excluded_ids_for_active_resume(self.db, self.user)
        self.assertIn(self.vacancy.id, excluded)


if __name__ == "__main__":
    unittest.main()
