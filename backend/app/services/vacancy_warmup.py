from __future__ import annotations

import logging
from datetime import UTC, datetime
from threading import Event, Lock, Thread

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.models.vacancy import Vacancy
from app.services.vacancy_pipeline import discover_and_index_vacancies
from app.services.vacancy_profile_backfill import backfill_missing_vacancy_profiles

logger = logging.getLogger(__name__)

_worker_thread: Thread | None = None
_stop_event = Event()
_state_lock = Lock()
_state: dict[str, object] = {
    "enabled": False,
    "running": False,
    "cycle": 0,
    "last_started_at": None,
    "last_finished_at": None,
    "last_duration_seconds": None,
    "last_error": None,
    "last_queries": [],
    "last_metrics": {},
}


def _as_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                result.append(text)
    return result


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item.strip())
    return output


def _query_from_resume_analysis(analysis: dict | None) -> str | None:
    if not isinstance(analysis, dict):
        return None

    role = analysis.get("target_role")
    specialization = analysis.get("specialization")
    keywords = _as_strings(analysis.get("matching_keywords"))
    hard_skills = _as_strings(analysis.get("hard_skills"))

    parts: list[str] = []
    if isinstance(role, str) and role.strip():
        parts.append(role.strip())
    if isinstance(specialization, str) and specialization.strip():
        parts.append(specialization.strip())
    parts.extend(keywords[:4])
    parts.extend(hard_skills[:4])

    compact = _dedupe(parts)
    if not compact:
        return None
    return " ".join(compact[:10])


def _collect_warmup_queries() -> list[str]:
    db = SessionLocal()
    try:
        queries: list[str] = []
        recent_resumes = db.scalars(
            select(Resume)
            .where(Resume.status == "completed")
            .order_by(Resume.updated_at.desc())
            .limit(24)
        ).all()
        for resume in recent_resumes:
            query = _query_from_resume_analysis(resume.analysis)
            if query:
                queries.append(query)

        liked_titles = db.scalars(
            select(Vacancy.title)
            .join(UserVacancyFeedback, UserVacancyFeedback.vacancy_id == Vacancy.id)
            .where(UserVacancyFeedback.liked.is_(True), Vacancy.status == "indexed")
            .order_by(UserVacancyFeedback.updated_at.desc())
            .limit(12)
        ).all()
        for title in liked_titles:
            if isinstance(title, str) and title.strip():
                queries.append(title.strip())

        fallback = [
            "python backend engineer observability",
            "devops engineer sre platform",
            "monitoring zabbix prometheus grafana",
            "platform services infrastructure engineer",
        ]
        queries.extend(fallback)
        return _dedupe(queries)[: max(1, settings.vacancy_warmup_queries_per_cycle)]
    finally:
        db.close()


def _run_warmup_cycle() -> tuple[list[str], dict[str, int]]:
    db = SessionLocal()
    try:
        queries = _collect_warmup_queries()
        started_at = datetime.now(UTC)
        aggregate = {
            "fetched": 0,
            "prefiltered": 0,
            "analyzed": 0,
            "filtered": 0,
            "indexed": 0,
            "failed": 0,
            "already_indexed_skipped": 0,
            "skipped_parse_errors": 0,
            "backfill_considered": 0,
            "backfill_profiled": 0,
            "backfill_filtered": 0,
            "backfill_failed": 0,
        }
        for query in queries:
            elapsed_seconds = (datetime.now(UTC) - started_at).total_seconds()
            if elapsed_seconds > max(30, settings.vacancy_warmup_cycle_timeout_seconds):
                break
            result = discover_and_index_vacancies(
                db,
                query=query,
                count=settings.vacancy_warmup_discover_count,
                rf_only=settings.vacancy_warmup_rf_only,
                force_reindex=False,
                use_brave_fallback=False,
                max_analyzed=settings.vacancy_warmup_max_analyzed_per_query,
            )
            aggregate["fetched"] += int(result.metrics.fetched or 0)
            aggregate["prefiltered"] += int(result.metrics.prefiltered or 0)
            aggregate["analyzed"] += int(result.metrics.analyzed or 0)
            aggregate["filtered"] += int(result.metrics.filtered or 0)
            aggregate["indexed"] += int(result.metrics.indexed or 0)
            aggregate["failed"] += int(result.metrics.failed or 0)
            aggregate["already_indexed_skipped"] += int(result.metrics.already_indexed_skipped or 0)
            aggregate["skipped_parse_errors"] += int(result.metrics.skipped_parse_errors or 0)

        if settings.vacancy_profile_backfill_enabled:
            elapsed_seconds = (datetime.now(UTC) - started_at).total_seconds()
            if elapsed_seconds <= max(30, settings.vacancy_warmup_cycle_timeout_seconds):
                backfill = backfill_missing_vacancy_profiles(
                    db,
                    limit=max(0, settings.vacancy_profile_backfill_limit_per_cycle),
                )
                aggregate["backfill_considered"] += int(backfill.get("considered", 0))
                aggregate["backfill_profiled"] += int(backfill.get("profiled", 0))
                aggregate["backfill_filtered"] += int(backfill.get("filtered", 0))
                aggregate["backfill_failed"] += int(backfill.get("failed", 0))
        return queries, aggregate
    finally:
        db.close()


def _set_state(**kwargs: object) -> None:
    with _state_lock:
        _state.update(kwargs)


def _worker_loop() -> None:
    while not _stop_event.is_set():
        started = datetime.now(UTC)
        _set_state(running=True, last_started_at=started.isoformat(), last_error=None)
        try:
            queries, metrics = _run_warmup_cycle()
            finished = datetime.now(UTC)
            _set_state(
                running=False,
                cycle=int(_state.get("cycle", 0)) + 1,
                last_finished_at=finished.isoformat(),
                last_duration_seconds=max(0, int((finished - started).total_seconds())),
                last_queries=queries,
                last_metrics=metrics,
            )
        except Exception as error:
            finished = datetime.now(UTC)
            _set_state(
                running=False,
                cycle=int(_state.get("cycle", 0)) + 1,
                last_finished_at=finished.isoformat(),
                last_duration_seconds=max(0, int((finished - started).total_seconds())),
                last_error=str(error),
            )
        if _stop_event.wait(max(10, settings.vacancy_warmup_interval_seconds)):
            break


def start_vacancy_warmup_worker() -> None:
    global _worker_thread
    if not settings.vacancy_warmup_enabled:
        _set_state(enabled=False, running=False)
        return
    if _worker_thread is not None and _worker_thread.is_alive():
        return

    _stop_event.clear()
    _set_state(enabled=True)
    _worker_thread = Thread(target=_worker_loop, daemon=True, name="vacancy-warmup-worker")
    _worker_thread.start()


def stop_vacancy_warmup_worker() -> None:
    _stop_event.set()
    if _worker_thread is not None and _worker_thread.is_alive():
        _worker_thread.join(timeout=3.0)
    _set_state(running=False)


def _run_resume_upload_warmup(*, user_id: int, resume_id: int) -> None:
    db = SessionLocal()
    try:
        resume = db.get(Resume, resume_id)
        if resume is None or resume.user_id != user_id:
            return
        query = _query_from_resume_analysis(resume.analysis)
        if not query:
            return
        discover_and_index_vacancies(
            db,
            query=query,
            count=max(1, settings.vacancy_warmup_on_upload_discover_count),
            rf_only=settings.vacancy_warmup_rf_only,
            force_reindex=False,
            use_brave_fallback=False,
            max_analyzed=max(1, settings.vacancy_warmup_on_upload_max_analyzed),
        )
    except Exception as error:
        logger.warning(
            "resume_upload_warmup_failed user_id=%s resume_id=%s error=%s",
            user_id,
            resume_id,
            error,
        )
    finally:
        db.close()


def trigger_warmup_for_resume(*, user_id: int, resume_id: int) -> Thread | None:
    """Prime the vacancy index for this user's resume in a background thread.

    Returns the spawned Thread (or None when disabled) so callers that care
    about completion — primarily tests — can join it.
    """
    if not settings.vacancy_warmup_on_resume_upload:
        return None
    thread = Thread(
        target=_run_resume_upload_warmup,
        kwargs={"user_id": user_id, "resume_id": resume_id},
        daemon=True,
        name=f"resume-upload-warmup-{resume_id}",
    )
    thread.start()
    return thread


def get_vacancy_warmup_status() -> dict[str, object]:
    with _state_lock:
        snapshot = dict(_state)
    snapshot["enabled"] = bool(settings.vacancy_warmup_enabled)
    snapshot["interval_seconds"] = int(settings.vacancy_warmup_interval_seconds)
    snapshot["queries_per_cycle"] = int(settings.vacancy_warmup_queries_per_cycle)
    snapshot["discover_count"] = int(settings.vacancy_warmup_discover_count)
    snapshot["max_analyzed_per_query"] = int(settings.vacancy_warmup_max_analyzed_per_query)
    snapshot["cycle_timeout_seconds"] = int(settings.vacancy_warmup_cycle_timeout_seconds)
    snapshot["profile_backfill_enabled"] = bool(settings.vacancy_profile_backfill_enabled)
    snapshot["profile_backfill_limit_per_cycle"] = int(
        settings.vacancy_profile_backfill_limit_per_cycle
    )
    return snapshot
