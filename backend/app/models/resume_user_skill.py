from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResumeUserSkill(Base):
    """Phase 1.9 PR C1 — user-curated skills on a resume.

    direction='added': user explicitly claims the skill (boost matching).
    direction='rejected': user says "not me" (suppress matched_skills entry).
    """

    __tablename__ = "resume_user_skills"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('added', 'rejected')",
            name="ck_resume_user_skills_direction",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("resumes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    skill_text: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    source_vacancy_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("vacancies.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
