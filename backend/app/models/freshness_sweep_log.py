from datetime import datetime

from sqlalchemy import DateTime, Integer, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FreshnessSweepLog(Base):
    """One row per nightly `sweep_stale_vacancies` cycle.

    Lets the operator answer "how many archived vacancies did we prune
    yesterday?" without parsing logs. Replaces the in-memory
    `_state["last_freshness_sweep_at"]` single-value with a history.
    """

    __tablename__ = "freshness_sweep_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stopped_early: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
