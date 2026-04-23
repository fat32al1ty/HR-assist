"""Cancel-path tests for the recommendation job (Phase 1.3).

Network-free: we exercise the cancel helpers directly and a thin simulation
of the worker progress callback. The DELETE endpoint is not end-to-end —
the route layer is a thin wrapper around cancel_job_for_user and is
covered here via the service entry point.
"""

import unittest
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.recommendation_job import RecommendationJob
from app.models.resume import Resume
from app.models.user import User
from app.repositories.recommendation_jobs import (
    create_recommendation_job,
    request_job_cancel,
)
from app.services.recommendation_jobs import (
    JOB_CANCELLED_MESSAGE,
    RecommendationJobCancelled,
    cancel_job_for_user,
    check_job_alive,
)


class RecommendationJobCancelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"cancel-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Cancel Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="cancel-test.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/{suffix}.pdf",
            status="completed",
            analysis={"target_role": "backend engineer"},
            error_message=None,
        )
        self.db.add(self.resume)
        self.db.commit()
        self.db.refresh(self.resume)

    def tearDown(self) -> None:
        self.db.execute(delete(RecommendationJob).where(RecommendationJob.user_id == self.user.id))
        self.db.execute(delete(Resume).where(Resume.user_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def _make_job(self, *, status: str = "running", stage: str = "collecting") -> RecommendationJob:
        job_id = str(uuid.uuid4())
        job = create_recommendation_job(
            self.db,
            job_id=job_id,
            user_id=self.user.id,
            resume_id=self.resume.id,
            request_payload={},
        )
        job.status = status
        job.stage = stage
        job.progress = 30
        if status == "running":
            job.started_at = datetime.now(UTC)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def test_request_job_cancel_flips_flag(self) -> None:
        job = self._make_job()
        self.assertFalse(job.cancel_requested)

        updated = request_job_cancel(self.db, job)
        self.assertTrue(updated.cancel_requested)
        # Status stays running until the worker observes the flag.
        self.assertEqual(updated.status, "running")

    def test_cancel_job_for_user_returns_snapshot(self) -> None:
        job = self._make_job()
        snapshot = cancel_job_for_user(job_id=job.id, user_id=self.user.id)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertTrue(snapshot["cancel_requested"])
        self.assertEqual(snapshot["id"], job.id)

    def test_cancel_unknown_job_returns_none(self) -> None:
        snapshot = cancel_job_for_user(job_id="does-not-exist", user_id=self.user.id)
        self.assertIsNone(snapshot)

    def test_cancel_is_rejected_for_other_users(self) -> None:
        job = self._make_job()
        snapshot = cancel_job_for_user(job_id=job.id, user_id=self.user.id + 99999)
        self.assertIsNone(snapshot)

        # And the flag stays clear.
        self.db.expire_all()
        fresh = self.db.scalar(select(RecommendationJob).where(RecommendationJob.id == job.id))
        assert fresh is not None
        self.assertFalse(fresh.cancel_requested)

    def test_cancel_on_completed_job_is_noop(self) -> None:
        job = self._make_job(status="completed", stage="done")
        snapshot = cancel_job_for_user(job_id=job.id, user_id=self.user.id)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        # Completed jobs keep their terminal state, no flag flip.
        self.assertFalse(snapshot["cancel_requested"])
        self.assertEqual(snapshot["status"], "completed")

    def test_cancel_twice_is_idempotent(self) -> None:
        job = self._make_job()
        cancel_job_for_user(job_id=job.id, user_id=self.user.id)
        snapshot = cancel_job_for_user(job_id=job.id, user_id=self.user.id)
        assert snapshot is not None
        self.assertTrue(snapshot["cancel_requested"])

    def test_check_job_alive_raises_when_flag_set(self) -> None:
        """The worker's between-stages poll raises a cancellation exception."""
        job = self._make_job()
        # Another process (the API handler) requests cancel mid-flight.
        request_job_cancel(self.db, job)

        with self.assertRaises(RecommendationJobCancelled) as ctx:
            check_job_alive(self.db, job)
        self.assertEqual(str(ctx.exception), JOB_CANCELLED_MESSAGE)

    def test_check_job_alive_passes_when_flag_clear(self) -> None:
        job = self._make_job()
        # No flag, not timed out → should not raise.
        check_job_alive(self.db, job)


if __name__ == "__main__":
    unittest.main()
