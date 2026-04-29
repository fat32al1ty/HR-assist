from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MatchEvent(Base):
    """Persistent storage for `POST /api/telemetry/event`.

    Before v0.23 the endpoint validated payload + size and then dropped
    everything on the floor. With this table the same events feed
    activation-funnel and quality dashboards.
    """

    __tablename__ = "match_event"
    __table_args__ = (
        Index("ix_match_event_user_ts", "user_id", "ts"),
        Index("ix_match_event_event_ts", "event", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
