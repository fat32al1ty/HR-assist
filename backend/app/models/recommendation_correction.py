from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RecommendationCorrection(Base):
    __tablename__ = "recommendation_corrections"
    __table_args__ = (
        Index("ix_rc_resume_vacancy", "resume_id", "vacancy_id"),
        Index("ix_rc_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    vacancy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False
    )
    correction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_index: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
