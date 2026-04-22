"""Phase 1.9 PR C1 — CRUD for user-curated resume skills."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.resume_user_skill import ResumeUserSkill

CURATION_DIRECTIONS = ("added", "rejected")


def _normalize_skill(text: str) -> str:
    return " ".join(text.strip().split()).strip()


def upsert_curated_skill(
    db: Session,
    *,
    resume_id: int,
    skill_text: str,
    direction: str,
    source_vacancy_id: int | None = None,
) -> ResumeUserSkill:
    """Insert or flip-direction for a single curated skill.

    Case-insensitive on skill_text so "Kubernetes" and "kubernetes" map
    to the same row (matches the unique index on LOWER(skill_text)).
    """
    if direction not in CURATION_DIRECTIONS:
        raise ValueError(f"invalid direction: {direction}")
    normalized = _normalize_skill(skill_text)
    if not normalized:
        raise ValueError("skill_text is empty")

    existing = db.scalar(
        select(ResumeUserSkill).where(
            ResumeUserSkill.resume_id == resume_id,
            func.lower(ResumeUserSkill.skill_text) == normalized.lower(),
        )
    )
    if existing is None:
        row = ResumeUserSkill(
            resume_id=resume_id,
            skill_text=normalized,
            direction=direction,
            source_vacancy_id=source_vacancy_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    if existing.direction != direction:
        existing.direction = direction
    if source_vacancy_id and existing.source_vacancy_id != source_vacancy_id:
        existing.source_vacancy_id = source_vacancy_id
    db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def delete_curated_skill(db: Session, *, resume_id: int, skill_id: int) -> bool:
    result = db.execute(
        delete(ResumeUserSkill).where(
            ResumeUserSkill.id == skill_id,
            ResumeUserSkill.resume_id == resume_id,
        )
    )
    db.commit()
    return bool(result.rowcount)


def list_curated_skills(db: Session, *, resume_id: int) -> list[ResumeUserSkill]:
    stmt = (
        select(ResumeUserSkill)
        .where(ResumeUserSkill.resume_id == resume_id)
        .order_by(ResumeUserSkill.created_at.desc())
    )
    return list(db.scalars(stmt))


def list_added_skill_texts(db: Session, *, resume_id: int) -> list[str]:
    stmt = (
        select(ResumeUserSkill.skill_text)
        .where(
            ResumeUserSkill.resume_id == resume_id,
            ResumeUserSkill.direction == "added",
        )
        .order_by(ResumeUserSkill.created_at.asc())
    )
    return list(db.scalars(stmt))


def list_rejected_skill_texts(db: Session, *, resume_id: int) -> list[str]:
    stmt = (
        select(ResumeUserSkill.skill_text)
        .where(
            ResumeUserSkill.resume_id == resume_id,
            ResumeUserSkill.direction == "rejected",
        )
        .order_by(ResumeUserSkill.created_at.asc())
    )
    return list(db.scalars(stmt))


def count_recent_added_curations(
    db: Session,
    *,
    resume_id: int,
    window: timedelta = timedelta(hours=1),
) -> int:
    """Phase 1.9 PR C1 sanity-check gate.

    A burst of 'added' clicks within an hour suggests the user is
    gaming the score (or the matcher is badly miscalibrated and they're
    patching symptom by symptom). We don't block — we return the count
    so the API can warn the frontend.
    """
    cutoff = datetime.now(UTC) - window
    result = db.scalar(
        select(func.count())
        .select_from(ResumeUserSkill)
        .where(
            ResumeUserSkill.resume_id == resume_id,
            ResumeUserSkill.direction == "added",
            ResumeUserSkill.created_at >= cutoff,
        )
    )
    return int(result or 0)
