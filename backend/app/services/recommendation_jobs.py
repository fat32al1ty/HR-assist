from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
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
    request_job_cancel,
    update_job_progress,
)
from app.repositories.user_daily_spend import get_daily_spend_usd
from app.services.openai_usage import (
    DAILY_BUDGET_USER_MESSAGE,
    DailyBudgetExceeded,
    OpenAIBudgetExceeded,
    openai_budget_scope,
)
from app.services.vacancy_recommendation import recommend_vacancies_for_resume

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="recommendation-job")
_active_jobs: set[str] = set()
_active_lock = Lock()
JOB_TIMEOUT_MESSAGE = (
    "Recommendation job timed out. Current search configuration is too heavy. "
    "Retry with narrower query or lower scan depth."
)
JOB_CANCELLED_MESSAGE = "Подбор остановлен по запросу пользователя."


class DailyBudgetReachedBeforeStart(RuntimeError):
    """User already spent their daily budget before this job could start.

    Raised by start_recommendation_job so the API layer can translate it
    into a 429 with the Russian user-facing message.
    """


class RecommendationJobCancelled(RuntimeError):
    """Raised inside the worker when the user has asked to stop the job.

    The worker catches this and transitions the job to failed with the
    Russian user-facing message so the frontend can show a friendly label.
    """


def start_recommendation_job(
    *,
    user_id: int,
    resume_id: int,
    request_payload: dict,
) -> str:
    if settings.openai_enforce_user_daily_budget:
        db_check = SessionLocal()
        try:
            current_spend = get_daily_spend_usd(db_check, user_id=user_id)
        finally:
            db_check.close()
        if current_spend >= settings.openai_user_daily_budget_usd:
            raise DailyBudgetReachedBeforeStart(DAILY_BUDGET_USER_MESSAGE)

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
    elapsed_seconds = (datetime.now(UTC) - job.started_at).total_seconds()
    return elapsed_seconds > settings.recommendation_job_timeout_seconds


def _force_fail_if_timed_out(db, job: RecommendationJob) -> RecommendationJob:
    if _timed_out(job):
        fail_job(db, job, error_message=JOB_TIMEOUT_MESSAGE)
        with _active_lock:
            _active_jobs.discard(job.id)
    return job


def check_job_alive(db, job: RecommendationJob) -> None:
    """Raise if the user has requested cancel or the job has timed out.

    Refreshes the row from the DB first so a cancel flip by another process
    (the API handler) is picked up by the worker at the next poll. Called
    from the worker's progress callback; the exception bubbles up to the
    outer try/except in `_run_recommendation_job`.
    """
    db.refresh(job)
    if job.cancel_requested:
        raise RecommendationJobCancelled(JOB_CANCELLED_MESSAGE)
    if _timed_out(job):
        raise TimeoutError(JOB_TIMEOUT_MESSAGE)


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
        "cancel_requested": bool(job.cancel_requested),
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


def cancel_job_for_user(*, job_id: str, user_id: int) -> dict | None:
    """Request cancellation of the given job for the given user.

    Returns the updated snapshot so the caller can return it to the frontend
    without a second round-trip. Returns None if the job does not exist or
    doesn't belong to this user. Idempotent on terminal jobs — the snapshot
    just reflects the existing terminal state.
    """
    db = SessionLocal()
    try:
        job = get_recommendation_job_for_user(db, job_id=job_id, user_id=user_id)
        if job is None:
            return None
        job = request_job_cancel(db, job)
        return _snapshot_from_job(job)
    finally:
        db.close()


def cancel_job_as_admin(*, job_id: str) -> dict | None:
    """Admin-scoped cancel — flip cancel_requested regardless of owning user.

    Returns the updated snapshot or None if the job doesn't exist. Idempotent
    on terminal jobs.
    """
    db = SessionLocal()
    try:
        job = db.scalar(select(RecommendationJob).where(RecommendationJob.id == job_id))
        if job is None:
            return None
        job = request_job_cancel(db, job)
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

        def on_progress(stage: str, progress: int, metrics: dict | None = None) -> None:
            check_job_alive(db, job)
            update_job_progress(db, job, stage=stage, progress=progress, metrics=metrics)

        with openai_budget_scope(
            budget_usd=settings.openai_request_budget_usd,
            budget_enforced=settings.openai_enforce_request_budget,
            user_id=user_id,
            daily_budget_usd=settings.openai_user_daily_budget_usd,
            daily_budget_enforced=settings.openai_enforce_user_daily_budget,
        ) as usage_tracker:
            try:
                overrides_raw = payload.get("preference_overrides")
                preference_overrides = overrides_raw if isinstance(overrides_raw, dict) else None
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
                    max_runtime_seconds=max(
                        30, int(settings.recommendation_job_timeout_seconds) - 30
                    ),
                    preference_overrides=preference_overrides,
                )
                check_job_alive(db, job)
            except RecommendationJobCancelled as error:
                fail_job(db, job, error_message=str(error))
                return
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
            except DailyBudgetExceeded:
                fail_job(
                    db,
                    job,
                    error_message=DAILY_BUDGET_USER_MESSAGE,
                    openai_usage=usage_tracker.snapshot().to_dict(),
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
            fallback_job = db.scalar(
                select(RecommendationJob).where(RecommendationJob.id == job_id)
            )
            if fallback_job is not None:
                fail_job(db, fallback_job, error_message=str(error))
        except Exception:
            pass
    finally:
        with _active_lock:
            _active_jobs.discard(job_id)
        db.close()
