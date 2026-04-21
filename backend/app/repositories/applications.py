from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application

APPLIED_STATUSES = {"applied", "viewed", "replied", "interview", "offer"}


def create_application(
    db: Session,
    *,
    user_id: int,
    vacancy_id: int | None,
    source_url: str,
    vacancy_title: str,
    vacancy_company: str | None,
    status: str = "draft",
    notes: str | None = None,
    cover_letter_text: str | None = None,
) -> Application:
    now = datetime.now(UTC)
    application = Application(
        user_id=user_id,
        vacancy_id=vacancy_id,
        status=status,
        source_url=source_url or "",
        vacancy_title=vacancy_title or "",
        vacancy_company=vacancy_company,
        notes=notes,
        cover_letter_text=cover_letter_text,
        last_status_change_at=now,
        applied_at=now if status in APPLIED_STATUSES else None,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def get_application_for_user(
    db: Session, *, application_id: int, user_id: int
) -> Application | None:
    return db.scalar(
        select(Application).where(Application.id == application_id, Application.user_id == user_id)
    )


def list_applications_for_user(
    db: Session, *, user_id: int, status: str | None = None
) -> list[Application]:
    query = select(Application).where(Application.user_id == user_id)
    if status is not None:
        query = query.where(Application.status == status)
    query = query.order_by(Application.created_at.desc())
    return list(db.scalars(query))


def get_application_by_user_vacancy(
    db: Session, *, user_id: int, vacancy_id: int
) -> Application | None:
    return db.scalar(
        select(Application).where(
            Application.user_id == user_id, Application.vacancy_id == vacancy_id
        )
    )


def update_application(
    db: Session,
    application: Application,
    *,
    status: str | None = None,
    notes: str | None = None,
    cover_letter_text: str | None = None,
    clear_notes: bool = False,
    clear_cover_letter: bool = False,
) -> Application:
    now = datetime.now(UTC)

    if status is not None and status != application.status:
        application.status = status
        application.last_status_change_at = now
        if status in APPLIED_STATUSES and application.applied_at is None:
            application.applied_at = now

    if clear_notes:
        application.notes = None
    elif notes is not None:
        application.notes = notes

    if clear_cover_letter:
        application.cover_letter_text = None
    elif cover_letter_text is not None:
        application.cover_letter_text = cover_letter_text

    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def delete_application(db: Session, application: Application) -> None:
    db.delete(application)
    db.commit()
