from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResumeVacancyScore(Base):
    __tablename__ = "resume_vacancy_scores"
    __table_args__ = (
        UniqueConstraint(
            "resume_id",
            "vacancy_id",
            "pipeline_version",
            name="uq_rvs_resume_vacancy_pipeline",
        ),
        Index("ix_rvs_resume_computed", "resume_id", "computed_at"),
        Index("ix_rvs_vacancy", "vacancy_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    vacancy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    vector_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    scores_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    track: Mapped[str | None] = mapped_column(String(16), nullable=True)
