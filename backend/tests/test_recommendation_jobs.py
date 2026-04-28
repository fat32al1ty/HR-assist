"""Integration tests for recommendation-jobs service behaviours.

T5  partial flag — recommend_vacancies_for_resume sets metrics.partial=True
    when max_runtime_seconds is exhausted mid-deep-scan.

T6  sweep_stale_running_jobs — flips aged running rows to failed, leaves
    fresh running rows untouched.
"""

from __future__ import annotations

import unittest
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.recommendation_job import RecommendationJob
from app.models.resume import Resume
from app.models.user import User
from app.repositories.recommendation_jobs import create_recommendation_job
from app.services.recommendation_jobs import (
    JOB_TIMEOUT_MESSAGE,
    sweep_stale_running_jobs,
)
from app.services.vacancy_pipeline import VacancyDiscoveryMetrics
from app.services.vacancy_recommendation import recommend_vacancies_for_resume


# ---------------------------------------------------------------------------
# T5 — metrics.partial is set when the runtime budget runs out mid-deep-scan
# ---------------------------------------------------------------------------


class PartialMetricsFlagTest(unittest.TestCase):
    """recommend_vacancies_for_resume sets metrics.partial=True on timeout."""

    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"partial-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Partial Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="partial-test.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/partial-{suffix}.pdf",
            status="completed",
            analysis={
                "target_role": "Backend Engineer",
                "specialization": "Python",
                "hard_skills": ["Python", "FastAPI"],
                "matching_keywords": ["backend", "python"],
            },
            error_message=None,
        )
        self.db.add(self.resume)
        self.db.commit()
        self.db.refresh(self.resume)

    def tearDown(self) -> None:
        self.db.execute(delete(Resume).where(Resume.user_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_partial_flag_set_when_runtime_budget_exhausted(
        self, mock_discover, mock_match
    ) -> None:
        """max_runtime_seconds=0 forces _cut_short on the very first deep-scan
        iteration, so aggregate_metrics.partial must be True in the return value."""
        mock_match.return_value = []
        # Make discover return a non-empty metrics so the loop sees real work
        # and doesn't bail for the "all already indexed" shortcut.
        mock_discover.return_value = SimpleNamespace(
            metrics=VacancyDiscoveryMetrics(fetched=5, analyzed=2, indexed=2)
        )

        _, metrics, _ = recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            discover_count=10,
            match_limit=10,
            deep_scan=True,
            rf_only=True,
            use_prefetched_index=False,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
            max_runtime_seconds=0,  # budget already exhausted before any work
        )

        self.assertTrue(
            metrics.partial,
            "metrics.partial must be True when the runtime budget was exhausted",
        )

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_partial_flag_serialises_in_asdict(
        self, mock_discover, mock_match
    ) -> None:
        """asdict(metrics) must include 'partial': True so the job snapshot
        that ends up in the DB is correct."""
        mock_match.return_value = []
        mock_discover.return_value = SimpleNamespace(
            metrics=VacancyDiscoveryMetrics(fetched=5, analyzed=2, indexed=2)
        )

        _, metrics, _ = recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            discover_count=10,
            match_limit=10,
            deep_scan=True,
            rf_only=True,
            use_prefetched_index=False,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
            max_runtime_seconds=0,
        )

        serialised = asdict(metrics)
        self.assertIn("partial", serialised)
        self.assertTrue(serialised["partial"])

    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_partial_flag_false_when_budget_not_exhausted(
        self, mock_discover, mock_match
    ) -> None:
        """Regression guard: when the full scan completes, partial must stay False."""
        mock_match.return_value = []
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        _, metrics, _ = recommend_vacancies_for_resume(
            self.db,
            resume_id=self.resume.id,
            user_id=self.user.id,
            discover_count=10,
            match_limit=10,
            deep_scan=False,
            rf_only=True,
            use_prefetched_index=False,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
            max_runtime_seconds=None,  # no budget limit
        )

        self.assertFalse(
            metrics.partial,
            "metrics.partial must be False when no runtime budget was set",
        )


# ---------------------------------------------------------------------------
# T6 — sweep_stale_running_jobs flips aged running rows, leaves fresh alone
# ---------------------------------------------------------------------------


class SweepStaleRunningJobsTest(unittest.TestCase):
    """sweep_stale_running_jobs: stale rows → failed; fresh rows untouched."""

    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"sweep-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Sweep Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="sweep-test.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/sweep-{suffix}.pdf",
            status="completed",
            analysis={"target_role": "backend engineer"},
            error_message=None,
        )
        self.db.add(self.resume)
        self.db.commit()
        self.db.refresh(self.resume)

    def tearDown(self) -> None:
        self.db.execute(
            delete(RecommendationJob).where(RecommendationJob.user_id == self.user.id)
        )
        self.db.execute(delete(Resume).where(Resume.user_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def _create_running_job(self, *, started_at: datetime) -> RecommendationJob:
        job_id = str(uuid.uuid4())
        job = create_recommendation_job(
            self.db,
            job_id=job_id,
            user_id=self.user.id,
            resume_id=self.resume.id,
            request_payload={},
        )
        job.status = "running"
        job.stage = "collecting"
        job.progress = 42
        job.started_at = started_at
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def test_stale_running_job_is_flipped_to_failed(self) -> None:
        stale_job = self._create_running_job(
            started_at=datetime.now(UTC) - timedelta(hours=2)
        )
        stale_job_id = stale_job.id

        swept = sweep_stale_running_jobs()

        self.assertGreaterEqual(swept, 1)
        # sweep_stale_running_jobs opens its own SessionLocal, so we must
        # expire the current session's identity map before re-reading the row.
        self.db.expire_all()
        refreshed = self.db.scalar(
            select(RecommendationJob).where(RecommendationJob.id == stale_job_id)
        )
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "failed")
        self.assertEqual(refreshed.stage, "failed")
        self.assertEqual(refreshed.progress, 100)
        self.assertEqual(refreshed.error_message, JOB_TIMEOUT_MESSAGE)
        self.assertIsNotNone(refreshed.finished_at)

    def test_fresh_running_job_is_left_untouched(self) -> None:
        fresh_job = self._create_running_job(
            started_at=datetime.now(UTC) - timedelta(seconds=5)
        )
        fresh_job_id = fresh_job.id

        sweep_stale_running_jobs()

        self.db.expire_all()
        refreshed = self.db.scalar(
            select(RecommendationJob).where(RecommendationJob.id == fresh_job_id)
        )
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(
            refreshed.status,
            "running",
            "A freshly-started job must not be swept",
        )

    def test_sweep_returns_count_of_swept_rows(self) -> None:
        # Insert two stale jobs and one fresh; sweep must return exactly 2.
        self._create_running_job(started_at=datetime.now(UTC) - timedelta(hours=3))
        self._create_running_job(started_at=datetime.now(UTC) - timedelta(hours=4))
        self._create_running_job(started_at=datetime.now(UTC) - timedelta(seconds=10))

        swept = sweep_stale_running_jobs()

        # At least the 2 stale ones we inserted must have been swept.
        # (There may be leftover stale jobs from other test runs; we don't own
        # the full table, so we assert ≥ not ==.)
        self.assertGreaterEqual(swept, 2)


if __name__ == "__main__":
    unittest.main()
