"""CRUD for per-(resume, vacancy, requirement) status overrides."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.requirement_override import RequirementOverride

VALID_SECTIONS = ("must_have", "nice_to_have")
VALID_STATUSES = ("ok", "missing")


def _normalize(text: str) -> str:
    return " ".join(text.strip().split()).strip()


def upsert_override(
    db: Session,
    *,
    resume_id: int,
    vacancy_id: int,
    section: str,
    requirement_text: str,
    status: str,
) -> RequirementOverride:
    if section not in VALID_SECTIONS:
        raise ValueError(f"invalid section: {section}")
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status}")
    normalized = _normalize(requirement_text)
    if not normalized:
        raise ValueError("requirement_text is empty")

    existing = db.scalar(
        select(RequirementOverride).where(
            RequirementOverride.resume_id == resume_id,
            RequirementOverride.vacancy_id == vacancy_id,
            RequirementOverride.section == section,
            func.lower(RequirementOverride.requirement_text) == normalized.lower(),
        )
    )
    if existing is None:
        row = RequirementOverride(
            resume_id=resume_id,
            vacancy_id=vacancy_id,
            section=section,
            requirement_text=normalized,
            status=status,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    if existing.status != status:
        existing.status = status
        db.add(existing)
        db.commit()
        db.refresh(existing)
    return existing


def delete_override(
    db: Session,
    *,
    resume_id: int,
    vacancy_id: int,
    section: str,
    requirement_text: str,
) -> int:
    normalized = _normalize(requirement_text)
    if not normalized:
        return 0
    result = db.execute(
        delete(RequirementOverride).where(
            RequirementOverride.resume_id == resume_id,
            RequirementOverride.vacancy_id == vacancy_id,
            RequirementOverride.section == section,
            func.lower(RequirementOverride.requirement_text) == normalized.lower(),
        )
    )
    db.commit()
    return result.rowcount or 0


def list_for_pair(
    db: Session,
    *,
    resume_id: int,
    vacancy_id: int,
) -> list[RequirementOverride]:
    return list(
        db.scalars(
            select(RequirementOverride).where(
                RequirementOverride.resume_id == resume_id,
                RequirementOverride.vacancy_id == vacancy_id,
            )
        )
    )


def list_for_resume(
    db: Session,
    *,
    resume_id: int,
    vacancy_ids: list[int] | None = None,
) -> list[RequirementOverride]:
    """Bulk-load overrides for a resume across multiple vacancies (one round-trip)."""
    stmt = select(RequirementOverride).where(RequirementOverride.resume_id == resume_id)
    if vacancy_ids is not None:
        if not vacancy_ids:
            return []
        stmt = stmt.where(RequirementOverride.vacancy_id.in_(vacancy_ids))
    return list(db.scalars(stmt))
