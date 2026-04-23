import unittest
import uuid
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.services.vacancy_recommendation import recommend_vacancies_for_resume


class RecommendationRuntimeGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"runtime-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Runtime Guard Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="runtime-test.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/{suffix}.pdf",
            status="completed",
            analysis={
                "target_role": "Backend Engineer",
                "specialization": "Platform Services",
                "hard_skills": ["Python", "FastAPI", "PostgreSQL"],
                "matching_keywords": ["backend", "platform", "api"],
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

    def test_runtime_guard_returns_without_failure(self) -> None:
        query, metrics, matches = recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            discover_count=40,
            match_limit=10,
            deep_scan=True,
            rf_only=True,
            use_brave_fallback=False,
            use_prefetched_index=False,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
            max_runtime_seconds=0,
        )
        self.assertIsInstance(query, str)
        self.assertIsNotNone(metrics)
        self.assertIsInstance(matches, list)
        self.assertEqual(metrics.analyzed, 0)


if __name__ == "__main__":
    unittest.main()
