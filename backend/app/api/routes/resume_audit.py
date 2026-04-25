from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.resumes import get_resume_for_user
from app.schemas.resume_audit import ResumeAuditOut
from app.services.resume_audit import compute_audit

router = APIRouter()


@router.get("/{resume_id}/audit", response_model=ResumeAuditOut)
def get_resume_audit(
    resume_id: int,
    force: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumeAuditOut:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    try:
        return compute_audit(db, resume_id, current_user.id, force=force)
    except LookupError:
        raise HTTPException(status_code=404, detail="Resume not found")
    except ValueError as exc:
        if "no_profile" in str(exc):
            raise HTTPException(
                status_code=422,
                detail="Resume analysis is still in progress. Try again later.",
            )
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        if "resume_audit_disabled" in str(exc):
            raise HTTPException(status_code=503, detail="Audit feature is disabled.")
        raise
