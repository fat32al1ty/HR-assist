from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.user_vacancy_seen import UserVacancySeen


def list_seen_vacancy_ids(
    db: Session,
    *,
    user_id: int,
    within_days: int,
) -> set[int]:
    """Return vacancy IDs shown to ``user_id`` in the last ``within_days`` days.

    The dedup window is intentionally user-wide (not resume-scoped): if the
    user has seen a vacancy under any resume, we don't want to show it again
    under another one within the cooling-off window.
    """
    if within_days <= 0:
        return set()
    cutoff = datetime.now(UTC) - timedelta(days=within_days)
    rows = db.scalars(
        select(UserVacancySeen.vacancy_id).where(
            UserVacancySeen.user_id == user_id,
            UserVacancySeen.shown_at >= cutoff,
        )
    ).all()
    return {int(row) for row in rows}


def upsert_seen_vacancies(
    db: Session,
    *,
    user_id: int,
    vacancy_ids: Iterable[int],
) -> int:
    """Record a vacancy as shown to the user. Refreshes ``shown_at`` on
    existing rows (so a repeat view bumps the window forward). Returns the
    number of rows touched."""
    ids = [int(v) for v in vacancy_ids if v is not None]
    if not ids:
        return 0
    now = datetime.now(UTC)
    stmt = insert(UserVacancySeen).values(
        [{"user_id": user_id, "vacancy_id": vid, "shown_at": now} for vid in ids]
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_user_vacancy_seen",
        set_={"shown_at": now},
    )
    db.execute(stmt)
    db.commit()
    return len(ids)
