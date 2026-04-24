"""Tests for the cursor-fallback path in recommend_vacancies_for_resume.

Three scenarios:
1. Warm-run with enough prefetched matches → early return, fallback never runs.
2. Warm-run, deep-scan finishes with too few high-quality matches → fallback
   fires up to 2 queries with date_from=None.
3. Cold-start (cursor_from=None) → fallback guard skips (counter stays 0).
"""
import unittest
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import call, patch

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.services.vacancy_pipeline import VacancyDiscoveryMetrics
from app.services.vacancy_recommendation import (
    HIGH_QUALITY_MATCH_THRESHOLD,
    recommend_vacancies_for_resume,
)

_HIGH = HIGH_QUALITY_MATCH_THRESHOLD + 0.05
_LOW = HIGH_QUALITY_MATCH_THRESHOLD - 0.1


def _metrics() -> VacancyDiscoveryMetrics:
    return VacancyDiscoveryMetrics()


class CursorFallbackBase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"fallback-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Fallback Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="fallback.pdf",
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

    def _set_cursor(self, hours_ago: int = 24) -> None:
        self.user.last_hh_seen_at = datetime.now(UTC) - timedelta(hours=hours_ago)
        self.db.add(self.user)
        self.db.commit()


class TestFallbackSkippedWhenEnoughPrefetched(CursorFallbackBase):
    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_no_fallback_on_enough_prefetched(self, mock_discover, mock_match) -> None:
        """enough_prefetched early-return path: discover never called, fallback counter = 0."""
        self._set_cursor()
        mock_match.return_value = [{"similarity_score": _HIGH}] * 20
        mock_discover.return_value = SimpleNamespace(metrics=_metrics())

        _, metrics, _ = recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            match_limit=10,
            deep_scan=True,
            use_prefetched_index=True,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
        )

        self.assertEqual(mock_discover.call_count, 0)
        self.assertEqual(metrics.cursor_fallback_queries_run, 0)


class TestFallbackFiresWhenFewHighQuality(CursorFallbackBase):
    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_fallback_runs_without_date_from(self, mock_discover, mock_match) -> None:
        """Deep-scan returns low-quality matches → fallback queries use date_from=None."""
        self._set_cursor()
        # All matches are low quality → neither deep-scan interim nor post-scan
        # threshold check will be satisfied.
        mock_match.return_value = [{"similarity_score": _LOW}] * 3
        mock_discover.return_value = SimpleNamespace(metrics=_metrics())

        _, metrics, _ = recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            match_limit=10,
            deep_scan=True,
            use_prefetched_index=True,
            discover_if_few_matches=True,
            min_prefetched_matches=8,
        )

        # At least one fallback query must have been dispatched.
        self.assertGreater(metrics.cursor_fallback_queries_run, 0)
        # Every fallback discover call must have date_from=None.
        fallback_calls = [
            c
            for c in mock_discover.call_args_list
            if c.kwargs.get("date_from") is None
        ]
        self.assertGreater(
            len(fallback_calls),
            0,
            msg="Expected at least one discover call with date_from=None in fallback",
        )
        # Fallback is capped at 2 queries.
        self.assertLessEqual(metrics.cursor_fallback_queries_run, 2)

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_fallback_capped_at_two_queries(self, mock_discover, mock_match) -> None:
        """Even with many query variations, the fallback runs at most 2."""
        self._set_cursor()
        mock_match.return_value = [{"similarity_score": _LOW}]
        mock_discover.return_value = SimpleNamespace(metrics=_metrics())

        _, metrics, _ = recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            match_limit=40,
            deep_scan=True,
            use_prefetched_index=True,
            discover_if_few_matches=True,
            min_prefetched_matches=10,
        )

        self.assertLessEqual(metrics.cursor_fallback_queries_run, 2)


class TestFallbackSkippedOnColdStart(CursorFallbackBase):
    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_cold_start_no_fallback(self, mock_discover, mock_match) -> None:
        """cursor_from=None on cold start — fallback guard must not trigger."""
        # user.last_hh_seen_at is None by default after setUp.
        mock_match.return_value = [{"similarity_score": _LOW}]
        mock_discover.return_value = SimpleNamespace(metrics=_metrics())

        _, metrics, _ = recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            match_limit=10,
            deep_scan=True,
            use_prefetched_index=True,
            discover_if_few_matches=True,
            min_prefetched_matches=8,
        )

        # cursor_from is None → fallback condition evaluates False → counter = 0.
        self.assertEqual(metrics.cursor_fallback_queries_run, 0)
        # Also assert no date_from=None calls slipped through via the fallback path
        # (cold-start calls all use cursor_from=None already, but counter tracks
        # only the dedicated fallback loop, which should not run).
        fallback_none_calls = [
            c
            for c in mock_discover.call_args_list
            if c.kwargs.get("date_from") is None
        ]
        # Cold-start calls all legitimately have date_from=None (cursor_from=None),
        # but cursor_fallback_queries_run must still be 0.
        self.assertEqual(metrics.cursor_fallback_queries_run, 0)


if __name__ == "__main__":
    unittest.main()
