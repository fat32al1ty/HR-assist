from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrackGapAnalysis(Base):
    __tablename__ = "track_gap_analyses"
    __table_args__ = (UniqueConstraint("resume_id", name="uq_tga_resume"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    analysis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
