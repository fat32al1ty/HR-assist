import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.repositories.resume_user_skills import (
    count_recent_added_curations,
    delete_curated_skill,
    list_curated_skills,
    upsert_curated_skill,
)
from app.repositories.resumes import (
    ResumeLimitExceeded,
    activate_resume,
    delete_resume,
    get_active_resume_for_user,
    get_resume_for_user,
    list_resumes_for_user,
    merge_resume_analysis,
    update_resume_label,
)
from app.repositories.users import update_preferences
from app.schemas.resume import (
    CuratedSkillCreate,
    CuratedSkillRead,
    CuratedSkillResponse,
    ResumeLabelUpdate,
    ResumeProfileConfirmRequest,
    ResumeProfileConfirmResponse,
    ResumeRead,
)
from app.services.resume_pipeline import process_resume_upload
from app.services.resume_profile_pipeline import (
    delete_resume_profile_vector,
    persist_resume_profile,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[ResumeRead])
def list_resumes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ResumeRead]:
    return list_resumes_for_user(db, user_id=current_user.id)


@router.post("", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumeRead:
    allowed_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF and DOCX files are supported"
        )

    if file.filename and len(file.filename) > 255:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File name is too long (max 255 characters)",
        )

    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large"
        )

    try:
        return process_resume_upload(db, user_id=current_user.id, upload=file, content=content)
    except ResumeLimitExceeded as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "resume_limit_exceeded",
                "limit": error.limit,
            },
        ) from error


@router.get("/active", response_model=ResumeRead)
def get_active_resume(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumeRead:
    resume = get_active_resume_for_user(db, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_active_resume")
    return resume


@router.get("/{resume_id}", response_model=ResumeRead)
def get_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumeRead:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    return resume


@router.patch("/{resume_id}", response_model=ResumeRead)
def patch_resume(
    resume_id: int,
    payload: ResumeLabelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumeRead:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return update_resume_label(db, resume, label=payload.label)


@router.post("/{resume_id}/activate", response_model=ResumeRead)
def activate_resume_endpoint(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumeRead:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return activate_resume(db, resume=resume)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    delete_resume_profile_vector(resume_id=resume.id)
    delete_resume(db, resume)


@router.post("/{resume_id}/profile-confirm", response_model=ResumeProfileConfirmResponse)
def confirm_resume_profile(
    resume_id: int,
    payload: ResumeProfileConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumeProfileConfirmResponse:
    """Combined "Подтвердить и найти работу" save.

    Applies Part A (resume.analysis overrides) and Part B (user preferences)
    in one request so the UI never ends up with a desync between what the user
    just saved and what the matcher actually uses.
    """
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    analysis = payload.analysis_updates
    prefs = payload.preference_updates
    if analysis is None and prefs is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No updates supplied",
        )

    if analysis is not None:
        analysis_patch: dict = {}
        for key in ("target_role", "specialization", "seniority", "total_experience_years"):
            value = getattr(analysis, key)
            if value is not None:
                analysis_patch[key] = value
        if analysis.top_skills is not None:
            analysis_patch["hard_skills"] = analysis.top_skills
        if analysis_patch:
            resume = merge_resume_analysis(db, resume, analysis_patch)
            try:
                persist_resume_profile(
                    db,
                    resume_id=resume.id,
                    user_id=current_user.id,
                    profile=resume.analysis or {},
                )
            except Exception as error:
                # Qdrant re-embed is best-effort — matcher will backfill lazily.
                logger.warning(
                    "resume_profile_reembed_failed resume_id=%s error=%s", resume.id, error
                )

    if prefs is not None:
        fields = prefs.model_dump(exclude_unset=True)
        clear_home = bool(
            prefs.clear_home_city or ("home_city" in fields and fields["home_city"] is None)
        )
        current_user = update_preferences(
            db,
            current_user,
            preferred_work_format=fields.get("preferred_work_format"),
            relocation_mode=fields.get("relocation_mode"),
            home_city=fields.get("home_city"),
            preferred_titles=fields.get("preferred_titles"),
            clear_home_city=clear_home,
        )

    db.refresh(resume)
    db.refresh(current_user)

    preferences = {
        "preferred_work_format": current_user.preferred_work_format,
        "relocation_mode": current_user.relocation_mode,
        "home_city": current_user.home_city,
        "preferred_titles": list(current_user.preferred_titles or []),
    }
    return ResumeProfileConfirmResponse(
        resume=ResumeRead.model_validate(resume),
        preferences=preferences,
    )


# Phase 1.9 PR C1 — user-curated skills (✓ "у меня это есть" / ✗ "не моё").
# After B1 + B2 tightened the matcher, these endpoints give users an
# explicit override for the remaining cases where the automation is
# still wrong. One-click per card, case-insensitive dedupe per resume.
CURATED_SKILL_WARN_THRESHOLD = 5


@router.post(
    "/{resume_id}/skills/curate",
    response_model=CuratedSkillResponse,
    status_code=status.HTTP_201_CREATED,
)
def curate_resume_skill(
    resume_id: int,
    payload: CuratedSkillCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CuratedSkillResponse:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    try:
        row = upsert_curated_skill(
            db,
            resume_id=resume.id,
            skill_text=payload.skill,
            direction=payload.direction,
            source_vacancy_id=payload.vacancy_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    recent_added = count_recent_added_curations(db, resume_id=resume.id)
    return CuratedSkillResponse(
        skill=CuratedSkillRead.model_validate(row),
        warn_sanity_check=recent_added > CURATED_SKILL_WARN_THRESHOLD,
        recent_added_count=recent_added,
    )


@router.get(
    "/{resume_id}/skills/curate",
    response_model=list[CuratedSkillRead],
)
def list_resume_curated_skills(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CuratedSkillRead]:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    rows = list_curated_skills(db, resume_id=resume.id)
    return [CuratedSkillRead.model_validate(row) for row in rows]


@router.delete(
    "/{resume_id}/skills/curate/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_resume_curated_skill(
    resume_id: int,
    skill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    removed = delete_curated_skill(db, resume_id=resume.id, skill_id=skill_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="curated_skill_not_found")
