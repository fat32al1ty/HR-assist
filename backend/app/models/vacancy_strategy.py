from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VacancyStrategy(Base):
    __tablename__ = "vacancy_strategies"
    __table_args__ = (
        UniqueConstraint(
            "resume_id", "vacancy_id", "prompt_version", name="uq_vs_resume_vacancy_prompt"
        ),
        Index("ix_vs_resume_computed", "resume_id", "computed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    vacancy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False
    )
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    template_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
