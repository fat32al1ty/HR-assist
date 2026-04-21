"""Phase 1.7 PR #4 — multi-profile DB tests."""

from __future__ import annotations

import unittest
import uuid

from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.models.vacancy import Vacancy
from app.repositories.resumes import (
    RESUME_LIMIT_PER_USER,
    ResumeLimitExceeded,
    activate_resume,
    create_resume_record,
    delete_resume,
    get_active_resume_for_user,
)
from app.services.vector_store import QdrantVectorStore


class ResumeLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"multi-profile-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Multi Profile Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self) -> None:
        self.db.execute(
            delete(UserVacancyFeedback).where(UserVacancyFeedback.user_id == self.user.id)
        )
        self.db.execute(delete(Resume).where(Resume.user_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_first_resume_becomes_active(self) -> None:
        resume = create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="r1.pdf",
            content_type="application/pdf",
            storage_path="/tmp/r1.pdf",
        )
        self.assertTrue(resume.is_active)
        active = get_active_resume_for_user(self.db, user_id=self.user.id)
        self.assertIsNotNone(active)
        self.assertEqual(active.id, resume.id)

    def test_second_resume_starts_inactive(self) -> None:
        first = create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="r1.pdf",
            content_type="application/pdf",
            storage_path="/tmp/r1.pdf",
        )
        second = create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="r2.pdf",
            content_type="application/pdf",
            storage_path="/tmp/r2.pdf",
        )
        self.assertTrue(first.is_active)
        self.assertFalse(second.is_active)

    def test_third_resume_is_rejected(self) -> None:
        create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="r1.pdf",
            content_type="application/pdf",
            storage_path="/tmp/r1.pdf",
        )
        create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="r2.pdf",
            content_type="application/pdf",
            storage_path="/tmp/r2.pdf",
        )
        with self.assertRaises(ResumeLimitExceeded) as ctx:
            create_resume_record(
                self.db,
                user_id=self.user.id,
                original_filename="r3.pdf",
                content_type="application/pdf",
                storage_path="/tmp/r3.pdf",
            )
        self.assertEqual(ctx.exception.limit, RESUME_LIMIT_PER_USER)

    def test_activate_flips_active_flag_atomically(self) -> None:
        first = create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="r1.pdf",
            content_type="application/pdf",
            storage_path="/tmp/r1.pdf",
        )
        second = create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="r2.pdf",
            content_type="application/pdf",
            storage_path="/tmp/r2.pdf",
        )
        activate_resume(self.db, resume=second)

        active_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(Resume)
                .where(Resume.user_id == self.user.id, Resume.is_active.is_(True))
            )
        )
        self.assertEqual(active_count, 1)

        self.db.refresh(first)
        self.db.refresh(second)
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)

    def test_deleting_active_promotes_next_most_recent(self) -> None:
        first = create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="r1.pdf",
            content_type="application/pdf",
            storage_path="/tmp/r1.pdf",
        )
        second = create_resume_record(
            self.db,
            user_id=self.user.id,
            original_filename="r2.pdf",
            content_type="application/pdf",
            storage_path="/tmp/r2.pdf",
        )
        # first is active (created first -> was the only one)
        self.assertTrue(first.is_active)
        delete_resume(self.db, first)

        self.db.refresh(second)
        self.assertTrue(second.is_active)


class FeedbackScopedToResumeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"feedback-scope-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Feedback Scope Test",
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
        self.vacancy = Vacancy(
            source="hh_api",
            source_url=f"https://hh.ru/vacancy/{uuid.uuid4().int % 1000000}",
            title="Senior Backend",
            company="Co",
            location="Москва",
            status="indexed",
            raw_payload={},
            raw_text="Senior backend",
            error_message=None,
        )
        self.db.add(self.vacancy)
        self.db.commit()
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

    def test_same_vacancy_can_have_different_feedback_per_resume(self) -> None:
        # Like under resume A, dislike the same vacancy under resume B.
        self.db.add(
            UserVacancyFeedback(
                user_id=self.user.id,
                resume_id=self.resume_a.id,
                vacancy_id=self.vacancy.id,
                liked=True,
                disliked=False,
            )
        )
        self.db.add(
            UserVacancyFeedback(
                user_id=self.user.id,
                resume_id=self.resume_b.id,
                vacancy_id=self.vacancy.id,
                liked=False,
                disliked=True,
            )
        )
        self.db.commit()

        rows = list(
            self.db.scalars(
                select(UserVacancyFeedback).where(
                    UserVacancyFeedback.user_id == self.user.id,
                    UserVacancyFeedback.vacancy_id == self.vacancy.id,
                )
            )
        )
        self.assertEqual(len(rows), 2)
        by_resume = {row.resume_id: row for row in rows}
        self.assertTrue(by_resume[self.resume_a.id].liked)
        self.assertTrue(by_resume[self.resume_b.id].disliked)


class PreferencePointIdTest(unittest.TestCase):
    def test_point_id_is_stable_and_scoped(self) -> None:
        store = QdrantVectorStore.__new__(QdrantVectorStore)
        a1_pos = store._user_preference_point_id(user_id=1, resume_id=10, kind="positive")
        a1_neg = store._user_preference_point_id(user_id=1, resume_id=10, kind="negative")
        a2_pos = store._user_preference_point_id(user_id=1, resume_id=20, kind="positive")
        b1_pos = store._user_preference_point_id(user_id=2, resume_id=10, kind="positive")

        self.assertNotEqual(a1_pos, a1_neg)
        self.assertNotEqual(a1_pos, a2_pos)  # different resume
        self.assertNotEqual(a1_pos, b1_pos)  # different user

        # Stability across calls
        self.assertEqual(
            a1_pos,
            store._user_preference_point_id(user_id=1, resume_id=10, kind="positive"),
        )


if __name__ == "__main__":
    unittest.main()
