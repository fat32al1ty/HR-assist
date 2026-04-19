from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vacancy import Vacancy


def _sanitize_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("\x00", "").strip()


def get_vacancy_by_source_url(db: Session, *, source_url: str) -> Vacancy | None:
    return db.scalar(select(Vacancy).where(Vacancy.source_url == (_sanitize_text(source_url) or "")))


def create_vacancy(
    db: Session,
    *,
    source: str,
    source_url: str,
    title: str,
    company: str | None,
    location: str | None,
    raw_payload: dict | None,
    raw_text: str | None,
) -> Vacancy:
    vacancy = Vacancy(
        source=_sanitize_text(source) or "",
        source_url=_sanitize_text(source_url) or "",
        title=_sanitize_text(title) or "",
        company=_sanitize_text(company),
        location=_sanitize_text(location),
        status="indexed",
        raw_payload=raw_payload,
        raw_text=_sanitize_text(raw_text),
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


def update_vacancy(
    db: Session,
    vacancy: Vacancy,
    *,
    title: str,
    company: str | None,
    location: str | None,
    raw_payload: dict | None,
    raw_text: str | None,
    status: str = "indexed",
    error_message: str | None = None,
) -> Vacancy:
    vacancy.title = _sanitize_text(title) or vacancy.title
    vacancy.company = _sanitize_text(company)
    vacancy.location = _sanitize_text(location)
    vacancy.raw_payload = raw_payload
    vacancy.raw_text = _sanitize_text(raw_text)
    vacancy.status = status
    vacancy.error_message = error_message
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


def list_vacancies(db: Session, *, limit: int = 50) -> list[Vacancy]:
    stmt = select(Vacancy).where(Vacancy.status == "indexed").order_by(Vacancy.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))


def get_vacancy_by_id(db: Session, *, vacancy_id: int) -> Vacancy | None:
    return db.scalar(select(Vacancy).where(Vacancy.id == vacancy_id))
