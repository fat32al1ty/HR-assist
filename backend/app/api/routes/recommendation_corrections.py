from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.recommendation_correction import RecommendationCorrection
from app.models.resume import Resume
from app.models.user import User
from app.models.vacancy import Vacancy
from app.models.vacancy_strategy import VacancyStrategy
from app.schemas.recommendation_correction import (
    RecommendationCorrectionCreate,
    RecommendationCorrectionRead,
)

router = APIRouter()


@router.post(
    "/recommendation-corrections",
    response_model=RecommendationCorrectionRead,
    status_code=201,
)
def create_correction(
    payload: RecommendationCorrectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecommendationCorrectionRead:
    resume = db.scalar(
        select(Resume).where(
            Resume.id == payload.resume_id,
            Resume.user_id == current_user.id,
        )
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    vacancy = db.get(Vacancy, payload.vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    # Require an existing strategy for this (resume, vacancy) — corrections only
    # make sense as a response to a rendered strategy. Without this gate, any
    # authenticated user could spam corrections against arbitrary vacancy IDs.
    strategy = db.scalar(
        select(VacancyStrategy.id).where(
            VacancyStrategy.resume_id == payload.resume_id,
            VacancyStrategy.vacancy_id == payload.vacancy_id,
        )
    )
    if strategy is None:
        raise HTTPException(
            status_code=409,
            detail="No strategy exists for this resume/vacancy pair yet.",
        )

    correction = RecommendationCorrection(
        user_id=current_user.id,
        resume_id=payload.resume_id,
        vacancy_id=payload.vacancy_id,
        correction_type=payload.correction_type,
        subject_index=payload.subject_index,
        subject_text=payload.subject_text,
    )
    db.add(correction)
    db.commit()
    db.refresh(correction)

    return RecommendationCorrectionRead(
        id=correction.id,
        resume_id=correction.resume_id,
        vacancy_id=correction.vacancy_id,
        correction_type=correction.correction_type,
        subject_index=correction.subject_index,
        subject_text=correction.subject_text,
        created_at=correction.created_at.isoformat(),
    )
