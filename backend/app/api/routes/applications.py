from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.repositories.applications import (
    create_application,
    delete_application,
    get_application_by_user_vacancy,
    get_application_for_user,
    list_applications_for_user,
    save_cover_letter,
    update_application,
)
from app.repositories.resumes import list_resumes_for_user
from app.repositories.vacancies import get_vacancy_by_id
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationRead,
    ApplicationStatus,
    ApplicationUpdateRequest,
    CoverLetterResponse,
)
from app.services.cover_letter import (
    CoverLetterUnavailable,
    build_resume_context,
    build_vacancy_context,
    generate_cover_letter_text,
)
from app.services.openai_usage import (
    DAILY_BUDGET_USER_MESSAGE,
    DailyBudgetExceeded,
    OpenAIBudgetExceeded,
    openai_budget_scope,
)

COVER_LETTER_COOLDOWN = timedelta(hours=24)

router = APIRouter()


@router.get("", response_model=list[ApplicationRead])
def list_applications(
    status_filter: ApplicationStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationRead]:
    rows = list_applications_for_user(db, user_id=current_user.id, status=status_filter)
    return [ApplicationRead.model_validate(row) for row in rows]


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application_endpoint(
    payload: ApplicationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    source_url = payload.source_url or ""
    title = payload.vacancy_title or ""
    company = payload.vacancy_company

    if payload.vacancy_id is not None:
        vacancy = get_vacancy_by_id(db, vacancy_id=payload.vacancy_id)
        if vacancy is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")
        # Reject duplicate trackers for the same vacancy — the match card's
        # "Откликнуться" button should be idempotent at the UI level, so
        # surfacing a 409 here tells the frontend to open the existing row.
        existing = get_application_by_user_vacancy(
            db, user_id=current_user.id, vacancy_id=payload.vacancy_id
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Application already exists for this vacancy",
                    "application_id": existing.id,
                },
            )
        # Authoritative values come from the vacancy row when we have one.
        source_url = vacancy.source_url or source_url
        title = vacancy.title or title
        company = vacancy.company if vacancy.company is not None else company

    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vacancy_title is required when vacancy_id is not supplied",
        )

    application = create_application(
        db,
        user_id=current_user.id,
        vacancy_id=payload.vacancy_id,
        source_url=source_url,
        vacancy_title=title,
        vacancy_company=company,
        status=payload.status,
        notes=payload.notes,
    )
    return ApplicationRead.model_validate(application)


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application_endpoint(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    application = get_application_for_user(
        db, application_id=application_id, user_id=current_user.id
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return ApplicationRead.model_validate(application)


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application_endpoint(
    application_id: int,
    payload: ApplicationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplicationRead:
    application = get_application_for_user(
        db, application_id=application_id, user_id=current_user.id
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates supplied")

    application = update_application(
        db,
        application,
        status=payload.status,
        notes=payload.notes,
        cover_letter_text=payload.cover_letter_text,
        clear_notes=payload.clear_notes,
        clear_cover_letter=payload.clear_cover_letter,
    )
    return ApplicationRead.model_validate(application)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application_endpoint(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    application = get_application_for_user(
        db, application_id=application_id, user_id=current_user.id
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    delete_application(db, application)


@router.post("/{application_id}/cover-letter", response_model=CoverLetterResponse)
def draft_cover_letter_endpoint(
    application_id: int,
    force: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CoverLetterResponse:
    application = get_application_for_user(
        db, application_id=application_id, user_id=current_user.id
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    # Serve the stored draft if it's fresh — one LLM call per application per day.
    if (
        not force
        and application.cover_letter_text
        and application.cover_letter_generated_at is not None
        and datetime.now(UTC) - application.cover_letter_generated_at < COVER_LETTER_COOLDOWN
    ):
        return CoverLetterResponse(
            id=application.id,
            cover_letter_text=application.cover_letter_text,
            cover_letter_generated_at=application.cover_letter_generated_at,
            cached=True,
        )

    resumes = list_resumes_for_user(db, user_id=current_user.id)
    resume_with_analysis = next(
        (resume for resume in resumes if isinstance(resume.analysis, dict) and resume.analysis),
        None,
    )
    if resume_with_analysis is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Resume with parsed analysis is required to draft a cover letter. "
                "Upload a resume first."
            ),
        )

    vacancy_profile_data: dict | None = None
    raw_text: str | None = None
    if application.vacancy_id is not None:
        vacancy = get_vacancy_by_id(db, vacancy_id=application.vacancy_id)
        if vacancy is not None:
            raw_text = vacancy.raw_text
            if vacancy.profile is not None and isinstance(vacancy.profile.profile, dict):
                vacancy_profile_data = vacancy.profile.profile

    resume_context = build_resume_context(resume_with_analysis.analysis)
    vacancy_context = build_vacancy_context(
        title=application.vacancy_title,
        company=application.vacancy_company,
        profile=vacancy_profile_data,
        raw_text=raw_text,
    )
    if not vacancy_context:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough vacancy context to draft a cover letter.",
        )

    try:
        with openai_budget_scope(
            budget_usd=settings.openai_request_budget_usd,
            budget_enforced=settings.openai_enforce_request_budget,
            user_id=current_user.id,
            daily_budget_usd=settings.openai_user_daily_budget_usd,
            daily_budget_enforced=settings.openai_enforce_user_daily_budget,
        ):
            letter_text = generate_cover_letter_text(
                resume_context=resume_context,
                vacancy_context=vacancy_context,
            )
    except DailyBudgetExceeded as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=DAILY_BUDGET_USER_MESSAGE,
        ) from error
    except OpenAIBudgetExceeded as error:
        snapshot = error.snapshot
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "OpenAI budget exceeded for this request. "
                f"Spent ${snapshot.estimated_cost_usd:.4f} with limit ${snapshot.budget_usd:.4f}."
            ),
        ) from error
    except CoverLetterUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    generated_at = datetime.now(UTC)
    application = save_cover_letter(db, application, text=letter_text, generated_at=generated_at)
    return CoverLetterResponse(
        id=application.id,
        cover_letter_text=application.cover_letter_text or letter_text,
        cover_letter_generated_at=application.cover_letter_generated_at or generated_at,
        cached=False,
    )
