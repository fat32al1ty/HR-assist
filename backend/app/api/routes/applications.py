from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.applications import (
    create_application,
    delete_application,
    get_application_by_user_vacancy,
    get_application_for_user,
    list_applications_for_user,
    update_application,
)
from app.repositories.vacancies import get_vacancy_by_id
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationRead,
    ApplicationStatus,
    ApplicationUpdateRequest,
)

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found"
            )
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No updates supplied"
        )

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
