from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recommendation_job import RecommendationJob


def create_recommendation_job(
    db: Session,
    *,
    job_id: str,
    user_id: int,
    resume_id: int,
    request_payload: dict | None,
) -> RecommendationJob:
    job = RecommendationJob(
        id=job_id,
        user_id=user_id,
        resume_id=resume_id,
        status="queued",
        stage="queued",
        progress=0,
        request_payload=request_payload,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_recommendation_job_for_user(
    db: Session, *, job_id: str, user_id: int
) -> RecommendationJob | None:
    return db.scalar(
        select(RecommendationJob).where(
            RecommendationJob.id == job_id, RecommendationJob.user_id == user_id
        )
    )


def mark_job_running(db: Session, job: RecommendationJob) -> RecommendationJob:
    if job.status in {"completed", "failed"}:
        return job
    job.status = "running"
    job.stage = "collecting"
    job.progress = max(1, min(99, int(job.progress or 0)))
    job.started_at = datetime.now(UTC)
    job.error_message = None
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job_progress(
    db: Session,
    job: RecommendationJob,
    *,
    stage: str,
    progress: int,
    metrics: dict | None = None,
    query: str | None = None,
) -> RecommendationJob:
    if job.status in {"completed", "failed"}:
        return job
    job.status = "running"
    job.stage = stage
    job.progress = max(0, min(99, int(progress)))
    if metrics is not None:
        job.metrics = metrics
    if query is not None and query.strip():
        job.query = query.strip()
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def complete_job(
    db: Session,
    job: RecommendationJob,
    *,
    query: str,
    metrics: dict,
    matches: list[dict],
    openai_usage: dict,
) -> RecommendationJob:
    if job.status in {"completed", "failed"}:
        return job
    job.status = "completed"
    job.stage = "done"
    job.progress = 100
    job.query = query
    job.metrics = metrics
    job.matches = matches
    job.openai_usage = openai_usage
    job.finished_at = datetime.now(UTC)
    job.error_message = None
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def fail_job(
    db: Session, job: RecommendationJob, *, error_message: str, openai_usage: dict | None = None
) -> RecommendationJob:
    if job.status == "completed":
        return job
    job.status = "failed"
    job.stage = "failed"
    job.progress = 100
    job.error_message = error_message
    job.openai_usage = openai_usage
    job.finished_at = datetime.now(UTC)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def request_job_cancel(db: Session, job: RecommendationJob) -> RecommendationJob:
    """Flip the cancel flag on a running/queued job.

    No-op on terminal jobs (completed/failed). The worker checks this flag
    between stages and bails out at the next safe boundary.
    """
    if job.status in {"completed", "failed"} or job.cancel_requested:
        return job
    job.cancel_requested = True
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
