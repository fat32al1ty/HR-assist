from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.auth_otp_code import AuthOtpCode

PURPOSE_EMAIL_VERIFY: Final[str] = "email_verify"
PURPOSE_LOGIN_2FA: Final[str] = "login_2fa"


def invalidate_active_codes(db: Session, *, email: str, purpose: str) -> None:
    now = datetime.now(UTC)
    active_codes = db.scalars(
        select(AuthOtpCode).where(
            and_(
                AuthOtpCode.email == email.lower(),
                AuthOtpCode.purpose == purpose,
                AuthOtpCode.consumed_at.is_(None),
                AuthOtpCode.expires_at > now,
            )
        )
    ).all()
    for row in active_codes:
        row.consumed_at = now
        db.add(row)
    if active_codes:
        db.commit()


def create_otp_code(
    db: Session,
    *,
    user_id: int | None,
    email: str,
    purpose: str,
    challenge_id: str | None,
    code_hash: str,
    expires_at: datetime,
    max_attempts: int,
) -> AuthOtpCode:
    row = AuthOtpCode(
        user_id=user_id,
        email=email.lower(),
        purpose=purpose,
        challenge_id=challenge_id,
        code_hash=code_hash,
        attempts=0,
        max_attempts=max_attempts,
        expires_at=expires_at,
        consumed_at=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_active_otp_code(
    db: Session,
    *,
    email: str,
    purpose: str,
    challenge_id: str | None,
) -> AuthOtpCode | None:
    now = datetime.now(UTC)
    query = select(AuthOtpCode).where(
        and_(
            AuthOtpCode.email == email.lower(),
            AuthOtpCode.purpose == purpose,
            AuthOtpCode.consumed_at.is_(None),
            AuthOtpCode.expires_at > now,
        )
    )
    if challenge_id:
        query = query.where(AuthOtpCode.challenge_id == challenge_id)
    return db.scalar(query.order_by(AuthOtpCode.created_at.desc()))


def register_failed_attempt(db: Session, *, code_row: AuthOtpCode) -> None:
    code_row.attempts = int(code_row.attempts) + 1
    if code_row.attempts >= int(code_row.max_attempts):
        code_row.consumed_at = datetime.now(UTC)
    db.add(code_row)
    db.commit()


def consume_code(db: Session, *, code_row: AuthOtpCode) -> None:
    code_row.consumed_at = datetime.now(UTC)
    db.add(code_row)
    db.commit()
