from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserVacancySeen(Base):
    """Level 2 D2: dedup log of vacancies that were shown to a user.

    One row per (user_id, vacancy_id). ``shown_at`` refreshes on every
    re-show so we can apply a rolling 14-day exclusion window in the
    matcher. ``dismissed_at`` is reserved for an explicit "hide forever"
    gesture from the UI (not wired up yet — None means the row is only
    subject to the automatic window).
    """

    __tablename__ = "user_vacancy_seen"
    __table_args__ = (
        UniqueConstraint("user_id", "vacancy_id", name="uq_user_vacancy_seen"),
        Index("ix_user_vacancy_seen_user_shown", "user_id", "shown_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    vacancy_id: Mapped[int] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), index=True
    )
    shown_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
