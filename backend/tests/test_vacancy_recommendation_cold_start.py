import unittest
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.services.vacancy_pipeline import VacancyDiscoveryMetrics
from app.services.vacancy_recommendation import (
    ADMIN_MAX_OPENAI_ANALYZED,
    ADMIN_MAX_SOURCES_SCANNED,
    ADMIN_PER_QUERY_CAP,
    COLD_START_MAX_OPENAI_ANALYZED,
    MAX_DEEP_SCAN_QUERIES,
    WARM_MAX_OPENAI_ANALYZED,
    recommend_vacancies_for_resume,
)


class ColdStartLLMBudgetTest(unittest.TestCase):
    """Phase 2.0 PR A1 — first-run users get a bigger LLM budget.

    The old cap of 18 capped the fresh index at ~14 vacancies. For users whose
    `last_hh_seen_at` is still NULL (meaning we've never hit HH for them yet)
    we spend 40 analyses instead, so the very first `Обновить подбор` returns
    a meaningful number of matches rather than 2-5.
    """

    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"cold-start-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Cold Start Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="cold-start.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/{suffix}.pdf",
            status="completed",
            analysis={
                "target_role": "Backend Engineer",
                "specialization": "Python",
                "hard_skills": ["Python", "FastAPI"],
                "matching_keywords": ["backend"],
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
    def test_cold_start_user_gets_larger_llm_budget(self, mock_discover, mock_match) -> None:
        mock_match.return_value = []
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        self.assertIsNone(self.user.last_hh_seen_at)

        recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            discover_count=40,
            match_limit=20,
            deep_scan=True,
            rf_only=True,
            use_prefetched_index=False,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
        )

        self.assertGreaterEqual(mock_discover.call_count, 1)
        max_analyzed_values = [
            call.kwargs.get("max_analyzed") for call in mock_discover.call_args_list
        ]
        # First call should receive the full cold-start budget (no prior analyses).
        self.assertEqual(max_analyzed_values[0], COLD_START_MAX_OPENAI_ANALYZED)

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_warm_user_keeps_tight_llm_budget(self, mock_discover, mock_match) -> None:
        mock_match.return_value = []
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        # Simulate a user who already had an HH fetch — cursor is populated.
        self.user.last_hh_seen_at = datetime.now(UTC) - timedelta(hours=2)
        self.db.add(self.user)
        self.db.commit()

        recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            discover_count=40,
            match_limit=20,
            deep_scan=True,
            rf_only=True,
            use_prefetched_index=False,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
        )

        self.assertGreaterEqual(mock_discover.call_count, 1)
        max_analyzed_values = [
            call.kwargs.get("max_analyzed") for call in mock_discover.call_args_list
        ]
        self.assertEqual(max_analyzed_values[0], WARM_MAX_OPENAI_ANALYZED)

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_shallow_scan_cold_start_also_uses_cold_budget(self, mock_discover, mock_match) -> None:
        # deep_scan=False path uses analyzed_budget directly via max_analyzed kwarg
        # on the single discover call. Regression guard for the `else` branch.
        mock_match.return_value = []
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        self.assertIsNone(self.user.last_hh_seen_at)

        recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            discover_count=40,
            match_limit=20,
            deep_scan=False,
            rf_only=True,
            use_prefetched_index=False,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
        )

        self.assertEqual(mock_discover.call_count, 1)
        self.assertEqual(
            mock_discover.call_args.kwargs.get("max_analyzed"),
            COLD_START_MAX_OPENAI_ANALYZED,
        )

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_admin_user_gets_wider_scan_and_llm_budget(self, mock_discover, mock_match) -> None:
        mock_match.return_value = []
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        # Promote the test user to admin — expect the larger caps to flow
        # through to discover_and_index_vacancies kwargs.
        self.user.is_admin = True
        self.db.add(self.user)
        self.db.commit()

        recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            discover_count=40,
            match_limit=20,
            deep_scan=True,
            rf_only=True,
            use_prefetched_index=False,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
        )

        self.assertGreaterEqual(mock_discover.call_count, 1)
        first_call = mock_discover.call_args_list[0]
        # Admin LLM cap is the wide one, not the cold-start 40.
        self.assertEqual(first_call.kwargs.get("max_analyzed"), ADMIN_MAX_OPENAI_ANALYZED)
        # Per-query fetch count should be far above the non-admin 150 cap.
        self.assertGreater(first_call.kwargs.get("count"), 150)
        self.assertLessEqual(first_call.kwargs.get("count"), ADMIN_PER_QUERY_CAP)
        # Admin should get the full 6 query variations (interactive cap of 3 lifted).
        self.assertLessEqual(mock_discover.call_count, MAX_DEEP_SCAN_QUERIES)
        # Total scan budget across all calls fits under the admin ceiling.
        total_count = sum(int(call.kwargs.get("count", 0)) for call in mock_discover.call_args_list)
        self.assertLessEqual(total_count, ADMIN_MAX_SOURCES_SCANNED)

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_admin_interactive_flow_skips_three_query_cap(self, mock_discover, mock_match) -> None:
        """When an admin triggers the normal UI flow (use_prefetched_index=True)
        they still get the full 6-query deep scan. Non-admins are capped at 3.
        """
        mock_match.return_value = []
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        self.user.is_admin = True
        self.db.add(self.user)
        self.db.commit()

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

        # Up to 6 (MAX_DEEP_SCAN_QUERIES), not the interactive 3-cap.
        self.assertGreater(mock_discover.call_count, 3)


if __name__ == "__main__":
    unittest.main()
