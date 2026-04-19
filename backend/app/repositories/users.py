from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def create_user(db: Session, *, email: str, password: str, full_name: str | None = None, email_verified: bool = False) -> User:
    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        full_name=full_name,
        email_verified=email_verified,
        email_verified_at=datetime.now(timezone.utc) if email_verified else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def mark_email_verified(db: Session, user: User) -> User:
    user.email_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
