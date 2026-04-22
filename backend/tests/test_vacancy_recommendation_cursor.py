import unittest
import uuid
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.services.vacancy_pipeline import VacancyDiscoveryMetrics
from app.services.vacancy_recommendation import (
    HH_CURSOR_OVERLAP,
    recommend_vacancies_for_resume,
)


class VacancyRecommendationCursorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"cursor-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Cursor Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="cursor-test.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/{suffix}.pdf",
            status="completed",
            extracted_text="Python backend",
            analysis={
                "target_role": "DevOps Engineer",
                "specialization": "Observability",
                "hard_skills": ["Prometheus", "Grafana"],
                "matching_keywords": ["observability"],
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

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_cursor_advances_after_successful_fetch(self, mock_discover, mock_match) -> None:
        mock_match.return_value = []
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        self.assertIsNone(self.user.last_hh_seen_at)

        recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            discover_count=40,
            match_limit=10,
            deep_scan=False,
            rf_only=True,
            use_prefetched_index=False,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
        )

        self.db.refresh(self.user)
        self.assertIsNotNone(self.user.last_hh_seen_at)
        self.assertLessEqual(
            (datetime.now(UTC) - self.user.last_hh_seen_at).total_seconds(),
            60,
        )

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_cursor_passed_with_overlap_to_discovery(self, mock_discover, mock_match) -> None:
        mock_match.return_value = []
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        cursor_value = datetime.now(UTC) - timedelta(hours=24)
        self.user.last_hh_seen_at = cursor_value
        self.db.add(self.user)
        self.db.commit()

        recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            discover_count=40,
            match_limit=10,
            deep_scan=False,
            rf_only=True,
            use_prefetched_index=False,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
        )

        self.assertGreaterEqual(mock_discover.call_count, 1)
        passed_date_from = mock_discover.call_args.kwargs.get("date_from")
        self.assertIsNotNone(passed_date_from)
        # Cursor passed with HH_CURSOR_OVERLAP subtracted for safety.
        expected = cursor_value - HH_CURSOR_OVERLAP
        self.assertAlmostEqual(passed_date_from.timestamp(), expected.timestamp(), delta=1.0)

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_cursor_not_advanced_when_only_prefetched_returned(
        self, mock_discover, mock_match
    ) -> None:
        # Many matches already in the index — enough_prefetched short-circuit
        # returns without touching HH; cursor should stay put.
        mock_match.return_value = [{"similarity_score": 0.9}] * 20
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            discover_count=40,
            match_limit=20,
            deep_scan=True,
            rf_only=True,
            use_prefetched_index=True,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
        )

        self.db.refresh(self.user)
        self.assertIsNone(self.user.last_hh_seen_at)
        self.assertEqual(mock_discover.call_count, 0)


if __name__ == "__main__":
    unittest.main()
