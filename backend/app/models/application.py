from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vacancy_id: Mapped[int | None] = mapped_column(
        ForeignKey("vacancies.id", ondelete="SET NULL"), nullable=True
    )
    resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft", index=True
    )
    cover_letter_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, default="", server_default=""
    )
    vacancy_title: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", server_default=""
    )
    vacancy_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    track: Mapped[str | None] = mapped_column(String(16), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_change_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    resume = relationship("Resume", foreign_keys=[resume_id])

    @property
    def resume_label(self) -> str | None:
        """Label shown on the Kanban badge; None when the resume was deleted
        after the application was created, so the UI can fall back to 'Профиль'."""
        return self.resume.label if self.resume is not None else None
