from datetime import UTC, datetime, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_login_event import UserLoginEvent


def record_login_event(db: Session, *, user_id: int) -> None:
    db.add(UserLoginEvent(user_id=user_id))
    db.flush()


def count_active_users_since(db: Session, *, since: datetime) -> int:
    result = db.scalar(
        select(func.count(distinct(UserLoginEvent.user_id))).where(
            UserLoginEvent.occurred_at >= since
        )
    )
    return int(result or 0)


def list_logins_by_day(db: Session, *, days: int) -> list[dict]:
    now = datetime.now(UTC)
    since = now - timedelta(days=days)

    rows = db.execute(
        select(
            func.date(UserLoginEvent.occurred_at).label("day"),
            func.count(UserLoginEvent.id).label("cnt"),
        )
        .where(UserLoginEvent.occurred_at >= since)
        .group_by(func.date(UserLoginEvent.occurred_at))
        .order_by(func.date(UserLoginEvent.occurred_at))
    ).all()

    counts: dict[str, int] = {str(r.day): int(r.cnt) for r in rows}
    result = []
    for i in range(days - 1, -1, -1):
        day = (now - timedelta(days=i)).date()
        result.append({"date": str(day), "count": counts.get(str(day), 0)})
    return result


def list_signups_by_day(db: Session, *, days: int) -> list[dict]:
    now = datetime.now(UTC)
    since = now - timedelta(days=days)

    rows = db.execute(
        select(
            func.date(User.created_at).label("day"),
            func.count(User.id).label("cnt"),
        )
        .where(User.created_at >= since)
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
    ).all()

    counts: dict[str, int] = {str(r.day): int(r.cnt) for r in rows}
    result = []
    for i in range(days - 1, -1, -1):
        day = (now - timedelta(days=i)).date()
        result.append({"date": str(day), "count": counts.get(str(day), 0)})
    return result
