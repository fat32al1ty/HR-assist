from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RequirementOverride(Base):
    """Per-(resume, vacancy, requirement) manual status override.

    User clicks a checklist item on a match card to flip status between
    'ok' (есть) and 'missing' (нет). Stored with section so must_have and
    nice_to_have entries with the same text don't collide.
    """

    __tablename__ = "requirement_overrides"
    __table_args__ = (
        CheckConstraint(
            "section IN ('must_have', 'nice_to_have')",
            name="ck_requirement_overrides_section",
        ),
        CheckConstraint(
            "status IN ('ok', 'missing')",
            name="ck_requirement_overrides_status",
        ),
        Index(
            "uq_requirement_overrides_pair_section_text",
            "resume_id",
            "vacancy_id",
            "section",
            text("lower(requirement_text)"),
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("resumes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    vacancy_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vacancies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    section: Mapped[str] = mapped_column(String(16), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
