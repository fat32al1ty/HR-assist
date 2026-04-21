from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.resume import Resume


def create_resume_record(
    db: Session,
    *,
    user_id: int,
    original_filename: str,
    content_type: str,
    storage_path: str,
) -> Resume:
    resume = Resume(
        user_id=user_id,
        original_filename=original_filename,
        content_type=content_type,
        storage_path=storage_path,
        status="uploaded",
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


def delete_resume(db: Session, resume: Resume) -> None:
    db.delete(resume)
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
