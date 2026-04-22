"""Append-only telemetry rows for match impressions / clicks / dwell.

Phase 2.6. Kept deliberately flat — no JSON columns, no enums in
Python, so the SQL-level consumer (LTR training prep, eyeball queries)
doesn't need to know anything about our ORM.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MatchImpression(Base):
    __tablename__ = "match_impression"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"))
    match_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    position: Mapped[int] = mapped_column(Integer)
    tier: Mapped[str] = mapped_column(String(10))
    vector_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hybrid_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rerank_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    role_family: Mapped[str | None] = mapped_column(String(40), nullable=True)


class MatchClick(Base):
    __tablename__ = "match_click"
    __table_args__ = (
        CheckConstraint(
            "click_kind IN ('open_card', 'open_source', 'apply', 'like', 'dislike')",
            name="ck_match_click_kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=True
    )
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"))
    match_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    click_kind: Mapped[str] = mapped_column(String(20))


class MatchDwell(Base):
    __tablename__ = "match_dwell"

    match_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), primary_key=True
    )
    ms: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
