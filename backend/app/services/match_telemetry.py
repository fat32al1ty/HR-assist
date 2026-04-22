"""Impression / click / dwell telemetry writers.

Phase 2.6. Append-only, best-effort — if Postgres is choking we log
and drop the row rather than let a telemetry insert tank a match
response. LTR training prep downstream is tolerant to gaps; serving
latency is not.

Clicks and dwell come in from the frontend via the telemetry router;
impressions are written server-side at the tail of
``match_vacancies_for_resume`` so we capture exactly what the user
was shown.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.match_telemetry import MatchClick, MatchDwell, MatchImpression

logger = logging.getLogger(__name__)

ALLOWED_CLICK_KINDS = frozenset({"open_card", "open_source", "apply", "like", "dislike"})


def log_impressions(
    db: Session,
    *,
    user_id: int,
    resume_id: int,
    match_run_id: uuid.UUID,
    matches: list[dict[str, Any]],
) -> int:
    """Bulk-insert one impression per visible match card.

    Returns the number of rows written. On DB failure we log and return
    0 — the caller must not retry or fail the user request over it.
    """
    if not matches:
        return 0
    rows: list[dict[str, Any]] = []
    for position, match in enumerate(matches):
        profile = match.get("profile") if isinstance(match, dict) else None
        profile_d = profile if isinstance(profile, dict) else {}
        rows.append(
            {
                "user_id": user_id,
                "resume_id": resume_id,
                "vacancy_id": match["vacancy_id"],
                "match_run_id": match_run_id,
                "position": position,
                "tier": str(match.get("tier") or "maybe")[:10],
                "vector_score": _coerce_float(profile_d.get("vector_score")),
                "hybrid_score": _coerce_float(match.get("similarity_score")),
                "rerank_score": _coerce_float(profile_d.get("rerank_score")),
                "llm_confidence": _coerce_float(profile_d.get("llm_confidence")),
                "role_family": _coerce_str(profile_d.get("role_family"), limit=40),
            }
        )
    try:
        db.execute(insert(MatchImpression), rows)
        db.commit()
    except Exception as error:  # noqa: BLE001
        db.rollback()
        logger.warning("failed to log impressions (run=%s): %s", match_run_id, error)
        return 0
    return len(rows)


def log_click(
    db: Session,
    *,
    user_id: int,
    vacancy_id: int,
    click_kind: str,
    resume_id: int | None = None,
    match_run_id: uuid.UUID | None = None,
    position: int | None = None,
) -> bool:
    """Write a single click row. Returns False on validation failure."""
    if click_kind not in ALLOWED_CLICK_KINDS:
        return False
    row = MatchClick(
        user_id=user_id,
        resume_id=resume_id,
        vacancy_id=vacancy_id,
        match_run_id=match_run_id,
        position=position,
        click_kind=click_kind,
    )
    try:
        db.add(row)
        db.commit()
    except Exception as error:  # noqa: BLE001
        db.rollback()
        logger.warning("failed to log click (user=%s vac=%s): %s", user_id, vacancy_id, error)
        return False
    return True


def log_dwell_batch(
    db: Session,
    *,
    match_run_id: uuid.UUID,
    entries: list[tuple[int, int]],
) -> int:
    """Upsert a batch of (vacancy_id, ms) dwell entries for one run.

    Postgres ON CONFLICT sums existing ms into the incoming value so
    multiple flushes from the same mount accumulate instead of
    clobbering. ``updated_at`` refreshed on each upsert.
    """
    if not entries:
        return 0
    rows = [
        {"match_run_id": match_run_id, "vacancy_id": vac_id, "ms": max(0, int(ms))}
        for vac_id, ms in entries
    ]
    try:
        stmt = pg_insert(MatchDwell).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["match_run_id", "vacancy_id"],
            set_={
                "ms": MatchDwell.ms + stmt.excluded.ms,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        db.execute(stmt)
        db.commit()
    except Exception as error:  # noqa: BLE001
        db.rollback()
        logger.warning("failed to log dwell (run=%s): %s", match_run_id, error)
        return 0
    return len(rows)


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_str(value: Any, *, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped[:limit]
