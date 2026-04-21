from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.resume import Resume

RESUME_LIMIT_PER_USER = 2


class ResumeLimitExceeded(RuntimeError):
    """Raised when a user attempts to own more than RESUME_LIMIT_PER_USER resumes."""

    def __init__(self, limit: int = RESUME_LIMIT_PER_USER) -> None:
        super().__init__(f"resume_limit_exceeded: max {limit} resumes per user")
        self.limit = limit


def count_resumes_for_user(db: Session, *, user_id: int) -> int:
    return int(
        db.scalar(select(func.count()).select_from(Resume).where(Resume.user_id == user_id)) or 0
    )


def create_resume_record(
    db: Session,
    *,
    user_id: int,
    original_filename: str,
    content_type: str,
    storage_path: str,
) -> Resume:
    if count_resumes_for_user(db, user_id=user_id) >= RESUME_LIMIT_PER_USER:
        raise ResumeLimitExceeded()

    has_active = (
        db.scalar(
            select(func.count())
            .select_from(Resume)
            .where(Resume.user_id == user_id, Resume.is_active.is_(True))
        )
        or 0
    )
    resume = Resume(
        user_id=user_id,
        original_filename=original_filename,
        content_type=content_type,
        storage_path=storage_path,
        status="uploaded",
        is_active=has_active == 0,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def list_resumes_for_user(db: Session, *, user_id: int) -> list[Resume]:
    return list(
        db.scalars(
            select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc())
        )
    )


def get_resume_for_user(db: Session, *, resume_id: int, user_id: int) -> Resume | None:
    return db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id))


def get_active_resume_for_user(db: Session, *, user_id: int) -> Resume | None:
    return db.scalar(select(Resume).where(Resume.user_id == user_id, Resume.is_active.is_(True)))


def activate_resume(db: Session, *, resume: Resume) -> Resume:
    """Flip the active flag to this resume atomically (only one active per user)."""
    db.execute(
        update(Resume)
        .where(Resume.user_id == resume.user_id, Resume.is_active.is_(True))
        .values(is_active=False)
    )
    resume.is_active = True
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def delete_resume(db: Session, resume: Resume) -> None:
    was_active = bool(resume.is_active)
    user_id = resume.user_id
    db.delete(resume)
    db.commit()

    # If we deleted the active resume, promote the next most-recent one so the
    # "one active per user" invariant is preserved.
    if was_active:
        replacement = db.scalar(
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc(), Resume.id.desc())
            .limit(1)
        )
        if replacement is not None:
            replacement.is_active = True
            db.add(replacement)
            db.commit()


def update_resume_processing_result(
    db: Session,
    resume: Resume,
    *,
    status: str,
    extracted_text: str | None = None,
    analysis: dict | None = None,
    error_message: str | None = None,
) -> Resume:
    resume.status = status
    resume.extracted_text = extracted_text
    resume.analysis = analysis
    resume.error_message = error_message
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def merge_resume_analysis(db: Session, resume: Resume, patch: dict) -> Resume:
    """Shallow-merge a partial analysis patch into resume.analysis.

    JSONB column is reassigned (SQLAlchemy won't track in-place mutation of
    a dict). Non-None values in the patch override existing keys; None values
    in the patch clear the corresponding key.
    """
    current = dict(resume.analysis) if isinstance(resume.analysis, dict) else {}
    for key, value in patch.items():
        if value is None:
            current[key] = None
        else:
            current[key] = value
    resume.analysis = current
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume
