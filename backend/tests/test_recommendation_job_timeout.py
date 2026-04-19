import unittest
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.recommendation_job import RecommendationJob
from app.models.resume import Resume
from app.models.user import User
from app.repositories.recommendation_jobs import create_recommendation_job, fail_job
from app.services.recommendation_jobs import get_job_snapshot_for_user


class RecommendationJobTimeoutTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"timeout-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Timeout Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="timeout-test.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/{suffix}.pdf",
            status="completed",
            extracted_text="timeout test",
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

    def test_running_job_is_persisted_as_failed_after_timeout(self) -> None:
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
        job.progress = 50
        job.started_at = datetime.now(timezone.utc) - timedelta(hours=2)
        self.db.add(job)
        self.db.commit()

        snapshot = get_job_snapshot_for_user(job_id=job_id, user_id=self.user.id)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot["status"], "failed")
        self.assertEqual(snapshot["stage"], "failed")
        self.assertEqual(snapshot["progress"], 100)
        self.assertFalse(snapshot["active"])

        refreshed = self.db.scalar(select(RecommendationJob).where(RecommendationJob.id == job_id))
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "failed")
        self.assertEqual(refreshed.stage, "failed")
        self.assertEqual(refreshed.progress, 100)
        self.assertIsNotNone(refreshed.finished_at)

    def test_completed_job_cannot_be_overwritten_by_fail_job(self) -> None:
        job_id = str(uuid.uuid4())
        job = create_recommendation_job(
            self.db,
            job_id=job_id,
            user_id=self.user.id,
            resume_id=self.resume.id,
            request_payload={},
        )
        job.status = "completed"
        job.stage = "done"
        job.progress = 100
        self.db.add(job)
        self.db.commit()

        fail_job(self.db, job, error_message="forced failure")
        refreshed = self.db.scalar(select(RecommendationJob).where(RecommendationJob.id == job_id))
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "completed")
        self.assertEqual(refreshed.stage, "done")


if __name__ == "__main__":
    unittest.main()
