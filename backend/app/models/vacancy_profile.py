from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class VacancyProfile(Base):
    __tablename__ = "vacancy_profiles"
    __table_args__ = (UniqueConstraint("vacancy_id", name="uq_vacancy_profiles_vacancy_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), index=True
    )
    schema_version: Mapped[str] = mapped_column(String(32), default="2026-04-16")
    profile: Mapped[dict] = mapped_column(JSON)
    canonical_text: Mapped[str] = mapped_column(Text)
    qdrant_collection: Mapped[str] = mapped_column(String(255))
    qdrant_point_id: Mapped[str] = mapped_column(String(64))
    embedded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    vacancy = relationship("Vacancy", back_populates="profile")
