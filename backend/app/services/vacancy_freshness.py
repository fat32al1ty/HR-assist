from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vacancy import Vacancy

logger = logging.getLogger(__name__)

_HH_VACANCY_API = "https://api.hh.ru/vacancies/{hh_id}"
_HH_URL_RE = re.compile(r"hh\.ru/vacancy/(\d+)", re.IGNORECASE)


def _extract_hh_id(source_url: str | None) -> str | None:
    if not source_url:
        return None
    m = _HH_URL_RE.search(source_url)
    if m:
        return m.group(1)
    return None


def check_vacancy_alive(db: Session, *, vacancy: Vacancy) -> bool:
    """GET https://api.hh.ru/vacancies/{hh_id}.

    Returns True if the vacancy is still live, False if archived/404.
    Sets last_freshness_check = now() on every reachable response (200, 4xx,
    5xx) so a single 5xx doesn't trap the row on the front of the sweep
    queue forever. ONLY a network-layer error (DNS / refused / timeout)
    leaves last_freshness_check unset — those rows are retried on the next
    sweep at the same priority.
    """
    hh_id = _extract_hh_id(vacancy.source_url)
    if hh_id is None:
        return True

    url = _HH_VACANCY_API.format(hh_id=hh_id)
    try:
        response = httpx.get(url, timeout=5.0, follow_redirects=True)
    except httpx.RequestError as exc:
        logger.warning(
            "vacancy_freshness_network_error vacancy_id=%s url=%s error=%s",
            vacancy.id,
            url,
            exc,
        )
        return True

    now = datetime.now(UTC)

    if response.status_code in (404, 410):
        vacancy.last_freshness_check = now
        vacancy.archived_at = now
        vacancy.status = "archived"
        db.add(vacancy)
        db.commit()
        return False

    if response.status_code >= 500:
        logger.warning(
            "vacancy_freshness_5xx vacancy_id=%s status=%s",
            vacancy.id,
            response.status_code,
        )
        vacancy.last_freshness_check = now
        db.add(vacancy)
        db.commit()
        return True

    vacancy.last_freshness_check = now

    try:
        payload = response.json()
    except Exception:
        db.add(vacancy)
        db.commit()
        return True

    if isinstance(payload, dict) and payload.get("archived") is True:
        vacancy.archived_at = now
        vacancy.status = "archived"
        db.add(vacancy)
        db.commit()
        return False

    db.add(vacancy)
    db.commit()
    return True


def sweep_stale_vacancies(
    db: Session,
    *,
    limit: int,
    max_runtime_seconds: float = 600.0,
) -> dict[str, int]:
    """Re-check up to `limit` rows ordered by last_freshness_check ASC NULLS FIRST,
    then by shown_count DESC. Returns {"checked": ..., "archived": ..., "stopped_early": ...}.

    Bounded by `max_runtime_seconds` so a sustained HH 5xx wave can't stall the
    warmup worker for ~46 minutes (worst case = limit × (httpx_timeout + sleep)).
    The remaining rows roll into the next nightly window.
    """
    # v0.23.0: persistent log row so we can SQL-graph the nightly yield
    # over time. Best-effort — if the import or insert breaks, the sweep
    # itself still runs.
    sweep_log_id: int | None = None
    sweep_started_dt = datetime.now(UTC)
    try:
        from app.models.freshness_sweep_log import FreshnessSweepLog

        log_row = FreshnessSweepLog(started_at=sweep_started_dt, checked=0, archived=0)
        db.add(log_row)
        db.commit()
        db.refresh(log_row)
        sweep_log_id = log_row.id
    except Exception:
        db.rollback()

    rows = db.scalars(
        select(Vacancy)
        .where(Vacancy.status == "indexed", Vacancy.source == "hh_api")
        .order_by(Vacancy.last_freshness_check.asc().nullsfirst(), Vacancy.shown_count.desc())
        .limit(limit)
    ).all()

    started_at = time.monotonic()
    checked = 0
    archived = 0
    stopped_early = 0
    for vacancy in rows:
        if time.monotonic() - started_at > max_runtime_seconds:
            stopped_early = 1
            logger.info(
                "vacancy_freshness_sweep_budget_exhausted checked=%d remaining=%d budget_seconds=%.1f",
                checked,
                len(rows) - checked,
                max_runtime_seconds,
            )
            break
        hh_id = _extract_hh_id(vacancy.source_url)
        if hh_id is None:
            continue
        alive = check_vacancy_alive(db, vacancy=vacancy)
        checked += 1
        if not alive:
            archived += 1
        time.sleep(0.5)

    logger.info(
        "vacancy_freshness_sweep_done checked=%d archived=%d stopped_early=%d",
        checked,
        archived,
        stopped_early,
    )

    # Update the persistent log row + bump Prometheus archive counter.
    if sweep_log_id is not None:
        try:
            from app.models.freshness_sweep_log import FreshnessSweepLog

            log_row = db.scalar(
                select(FreshnessSweepLog).where(FreshnessSweepLog.id == sweep_log_id)
            )
            if log_row is not None:
                log_row.finished_at = datetime.now(UTC)
                log_row.checked = checked
                log_row.archived = archived
                log_row.stopped_early = stopped_early
                db.add(log_row)
                db.commit()
        except Exception:
            db.rollback()
    if archived > 0:
        try:
            from app.services.metrics_registry import record_freshness_archived

            record_freshness_archived(source="hh_api", count=archived)
        except Exception:
            pass

    return {"checked": checked, "archived": archived, "stopped_early": stopped_early}


async def _check_one(
    client: httpx.AsyncClient,
    db: Session,
    vacancy: Vacancy,
) -> int | None:
    """Return vacancy.id if archived, else None."""
    hh_id = _extract_hh_id(vacancy.source_url)
    if hh_id is None:
        return None
    url = _HH_VACANCY_API.format(hh_id=hh_id)
    now = datetime.now(UTC)
    try:
        response = await client.get(url, follow_redirects=True)
    except httpx.RequestError as exc:
        logger.warning(
            "vacancy_freshness_async_network_error vacancy_id=%s error=%s",
            vacancy.id,
            exc,
        )
        return None

    if response.status_code in (404, 410):
        vacancy.last_freshness_check = now
        vacancy.archived_at = now
        vacancy.status = "archived"
        db.add(vacancy)
        return vacancy.id

    if response.status_code >= 500:
        vacancy.last_freshness_check = now
        db.add(vacancy)
        return None

    vacancy.last_freshness_check = now
    try:
        payload = response.json()
    except Exception as exc:
        # Treat malformed HH responses as alive — a 200 with broken JSON
        # is more likely an HH-side glitch than an archive marker. Log so
        # we can spot patterns if it becomes systematic.
        logger.debug(
            "vacancy_freshness_async_json_parse_failed vacancy_id=%s error=%s",
            vacancy.id,
            exc,
        )
        db.add(vacancy)
        return None

    if isinstance(payload, dict) and payload.get("archived") is True:
        vacancy.archived_at = now
        vacancy.status = "archived"
        db.add(vacancy)
        return vacancy.id

    db.add(vacancy)
    return None


def check_vacancies_alive_concurrently(
    db: Session,
    *,
    vacancies: list[Vacancy],
    max_concurrency: int = 10,
) -> set[int]:
    """Check each vacancy in parallel. Returns the set of vacancy IDs that are archived."""
    if not vacancies:
        return set()

    async def _run() -> set[int]:
        limits = httpx.Limits(
            max_connections=max_concurrency, max_keepalive_connections=max_concurrency
        )
        async with httpx.AsyncClient(timeout=5.0, limits=limits) as client:
            sem = asyncio.Semaphore(max_concurrency)

            async def _guarded(v: Vacancy) -> int | None:
                async with sem:
                    return await _check_one(client, db, v)

            results = await asyncio.gather(*[_guarded(v) for v in vacancies])

        archived: set[int] = set()
        for r in results:
            if r is not None:
                archived.add(r)
        return archived

    # IMPLICIT CONTRACT: this function MUST be called from a sync context
    # (no running event loop). FastAPI dispatches sync `def` handlers via
    # anyio's worker thread pool, so the calling thread has no loop and
    # `asyncio.run()` is safe. If the instant route is ever converted to
    # `async def`, asyncio.run() will raise from inside the running loop —
    # at that point convert this helper to `async def` + `await _run()`
    # and have callers `await` it.
    archived_ids = asyncio.run(_run())
    try:
        db.commit()
    except Exception as exc:
        logger.warning("vacancy_freshness_concurrent_commit_error error=%s", exc)
        db.rollback()
    return archived_ids
