from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str | None = None,
    email_verified: bool = False,
) -> User:
    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        full_name=full_name,
        email_verified=email_verified,
        email_verified_at=datetime.now(UTC) if email_verified else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def mark_email_verified(db: Session, user: User) -> User:
    user.email_verified = True
    user.email_verified_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_preferences(
    db: Session,
    user: User,
    *,
    preferred_work_format: str | None = None,
    relocation_mode: str | None = None,
    home_city: str | None = None,
    preferred_titles: list[str] | None = None,
    clear_home_city: bool = False,
) -> User:
    """Apply a partial update to the four job-preference columns.

    Pass `clear_home_city=True` to explicitly set home_city to NULL (since
    `home_city=None` alone is indistinguishable from "leave unchanged").
    """

    if preferred_work_format is not None:
        user.preferred_work_format = preferred_work_format
    if relocation_mode is not None:
        user.relocation_mode = relocation_mode
    if home_city is not None:
        user.home_city = home_city
    elif clear_home_city:
        user.home_city = None
    if preferred_titles is not None:
        user.preferred_titles = preferred_titles
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
