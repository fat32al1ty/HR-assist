from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResumeAudit(Base):
    __tablename__ = "resume_audits"
    __table_args__ = (UniqueConstraint("resume_id", name="uq_resume_audits_resume_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), index=True, unique=True
    )
    audit_json: Mapped[dict] = mapped_column(JSON)
    prompt_version: Mapped[str] = mapped_column(String(32))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    resume = relationship("Resume", back_populates="audit")
