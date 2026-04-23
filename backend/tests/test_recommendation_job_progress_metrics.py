import unittest
import uuid

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.recommendation_job import RecommendationJob
from app.models.resume import Resume
from app.models.user import User
from app.repositories.recommendation_jobs import create_recommendation_job, update_job_progress


class RecommendationJobProgressMetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"metrics-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Metrics Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="metrics-test.pdf",
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

    def test_update_job_progress_persists_metrics_and_query(self) -> None:
        job_id = str(uuid.uuid4())
        job = create_recommendation_job(
            self.db,
            job_id=job_id,
            user_id=self.user.id,
            resume_id=self.resume.id,
            request_payload={"discover_count": 40},
        )

        metrics = {
            "fetched": 120,
            "analyzed": 8,
            "filtered": 111,
            "indexed": 1,
            "already_indexed_skipped": 42,
        }
        update_job_progress(
            self.db,
            job,
            stage="collecting",
            progress=63,
            metrics=metrics,
            query="devops observability",
        )

        refreshed = self.db.scalar(select(RecommendationJob).where(RecommendationJob.id == job_id))
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "running")
        self.assertEqual(refreshed.stage, "collecting")
        self.assertEqual(refreshed.progress, 63)
        self.assertEqual(refreshed.query, "devops observability")
        self.assertEqual(refreshed.metrics, metrics)


if __name__ == "__main__":
    unittest.main()
