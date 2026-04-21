from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    preferred_work_format: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="any"
    )
    relocation_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="home_only"
    )
    home_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preferred_titles: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default="{}"
    )

    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    auth_otp_codes = relationship(
        "AuthOtpCode", back_populates="user", cascade="all, delete-orphan"
    )
