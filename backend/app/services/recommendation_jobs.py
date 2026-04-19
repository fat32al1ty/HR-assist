from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.recommendation_job import RecommendationJob
from app.repositories.recommendation_jobs import (
    complete_job,
    create_recommendation_job,
    fail_job,
    get_recommendation_job_for_user,
    mark_job_running,
    update_job_progress,
)
from app.services.openai_usage import OpenAIBudgetExceeded, openai_budget_scope
from app.services.vacancy_recommendation import recommend_vacancies_for_resume

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="recommendation-job")
_active_jobs: set[str] = set()
_active_lock = Lock()
JOB_TIMEOUT_MESSAGE = (
    "Recommendation job timed out. Current search configuration is too heavy. "
    "Retry with narrower query or lower scan depth."
)


def start_recommendation_job(
    *,
    user_id: int,
    resume_id: int,
    request_payload: dict,
) -> str:
    job_id = str(uuid4())
    db = SessionLocal()
    try:
        create_recommendation_job(
            db,
            job_id=job_id,
            user_id=user_id,
            resume_id=resume_id,
            request_payload=request_payload,
        )
    finally:
        db.close()

    with _active_lock:
        _active_jobs.add(job_id)
    _executor.submit(_run_recommendation_job, job_id)
    return job_id


def _timed_out(job: RecommendationJob) -> bool:
    if job.status != "running" or job.started_at is None:
        return False
    elapsed_seconds = (datetime.now(timezone.utc) - job.started_at).total_seconds()
    return elapsed_seconds > settings.recommendation_job_timeout_seconds


def _force_fail_if_timed_out(db, job: RecommendationJob) -> RecommendationJob:
    if _timed_out(job):
        fail_job(db, job, error_message=JOB_TIMEOUT_MESSAGE)
        with _active_lock:
            _active_jobs.discard(job.id)
    return job


def _snapshot_from_job(job: RecommendationJob) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "stage": job.stage,
        "progress": int(job.progress or 0),
        "query": job.query,
        "metrics": job.metrics or {},
        "matches": job.matches or [],
        "openai_usage": job.openai_usage or {},
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "active": _is_job_active(job.id),
    }


def get_job_snapshot_for_user(*, job_id: str, user_id: int) -> dict | None:
    db = SessionLocal()
    try:
        job = get_recommendation_job_for_user(db, job_id=job_id, user_id=user_id)
        if job is None:
            return None
        job = _force_fail_if_timed_out(db, job)
        return _snapshot_from_job(job)
    finally:
        db.close()


def get_latest_job_snapshot_for_user(*, user_id: int, resume_id: int | None = None) -> dict | None:
    db = SessionLocal()
    try:
        query = select(RecommendationJob).where(RecommendationJob.user_id == user_id)
        if resume_id is not None:
            query = query.where(RecommendationJob.resume_id == resume_id)
        query = query.order_by(RecommendationJob.created_at.desc()).limit(1)
        job = db.scalar(query)
        if job is None:
            return None
        job = _force_fail_if_timed_out(db, job)
        return _snapshot_from_job(job)
    finally:
        db.close()


def _is_job_active(job_id: str) -> bool:
    with _active_lock:
        return job_id in _active_jobs


def _run_recommendation_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.scalar(select(RecommendationJob).where(RecommendationJob.id == job_id))
        if job is None:
            return

        mark_job_running(db, job)
        payload = job.request_payload or {}
        resume_id = int(job.resume_id)
        user_id = int(job.user_id)

        def assert_not_timed_out() -> None:
            db.refresh(job)
            if _timed_out(job):
                raise TimeoutError(JOB_TIMEOUT_MESSAGE)

        def on_progress(stage: str, progress: int, metrics: dict | None = None) -> None:
            assert_not_timed_out()
            update_job_progress(db, job, stage=stage, progress=progress, metrics=metrics)

        with openai_budget_scope(
            budget_usd=settings.openai_request_budget_usd,
            budget_enforced=settings.openai_enforce_request_budget,
        ) as usage_tracker:
            try:
                query, metrics, matches = recommend_vacancies_for_resume(
                    db,
                    resume_id=resume_id,
                    user_id=user_id,
                    discover_count=int(payload.get("discover_count", 40)),
                    match_limit=int(payload.get("match_limit", 20)),
                    deep_scan=bool(payload.get("deep_scan", True)),
                    rf_only=bool(payload.get("rf_only", True)),
                    use_brave_fallback=bool(payload.get("use_brave_fallback", False)),
                    use_prefetched_index=bool(payload.get("use_prefetched_index", True)),
                    discover_if_few_matches=bool(payload.get("discover_if_few_matches", True)),
                    min_prefetched_matches=int(payload.get("min_prefetched_matches", 8)),
                    progress_callback=on_progress,
                    max_runtime_seconds=max(30, int(settings.recommendation_job_timeout_seconds) - 30),
                )
                assert_not_timed_out()
            except OpenAIBudgetExceeded as error:
                fail_job(
                    db,
                    job,
                    error_message=(
                        "OpenAI budget exceeded for this request. "
                        f"Spent ${error.snapshot.estimated_cost_usd:.4f} with limit ${error.snapshot.budget_usd:.4f}. "
                        "Reduce deep scan or raise budget."
                    ),
                    openai_usage=error.snapshot.to_dict(),
                )
                return
            except TimeoutError as error:
                fail_job(db, job, error_message=str(error))
                return

            complete_job(
                db,
                job,
                query=query,
                metrics=asdict(metrics),
                matches=matches,
                openai_usage=usage_tracker.snapshot().to_dict(),
            )
    except Exception as error:
        try:
            fallback_job = db.scalar(select(RecommendationJob).where(RecommendationJob.id == job_id))
            if fallback_job is not None:
                fail_job(db, fallback_job, error_message=str(error))
        except Exception:
            pass
    finally:
        with _active_lock:
            _active_jobs.discard(job_id)
        db.close()
