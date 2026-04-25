from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResumeClarification(Base):
    __tablename__ = "resume_clarifications"
    __table_args__ = (
        UniqueConstraint(
            "resume_id", "question_id", name="uq_resume_clarifications_resume_question"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(String(64))
    answer_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    resume = relationship("Resume")
