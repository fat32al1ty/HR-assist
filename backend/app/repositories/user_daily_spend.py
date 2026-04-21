from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.user_daily_spend import UserDailySpend


def today_utc() -> date:
    return datetime.now(UTC).date()


def get_daily_spend_usd(db: Session, *, user_id: int, on_date: date | None = None) -> float:
    target = on_date or today_utc()
    row = db.scalar(
        select(UserDailySpend).where(
            UserDailySpend.user_id == user_id,
            UserDailySpend.date == target,
        )
    )
    if row is None:
        return 0.0
    return float(row.spend_usd)


def increment_daily_spend(
    db: Session, *, user_id: int, amount_usd: float, on_date: date | None = None
) -> float:
    """Atomic UPSERT on (user_id, date); returns the new running total in USD.

    Uses Postgres INSERT ... ON CONFLICT so two concurrent jobs by the same
    user can't race and under-count. Safe to call many times per second.
    """
    target = on_date or today_utc()
    delta = Decimal(str(max(0.0, float(amount_usd))))

    stmt = (
        pg_insert(UserDailySpend)
        .values(user_id=user_id, date=target, spend_usd=delta)
        .on_conflict_do_update(
            constraint="uq_user_daily_spend_user_date",
            set_={
                "spend_usd": UserDailySpend.spend_usd + delta,
                "updated_at": datetime.now(UTC),
            },
        )
        .returning(UserDailySpend.spend_usd)
    )
    new_total = db.execute(stmt).scalar_one()
    db.commit()
    return float(new_total)
