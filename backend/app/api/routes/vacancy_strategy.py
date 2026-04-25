from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.resume import Resume
from app.models.user import User
from app.models.vacancy_strategy import VacancyStrategy
from app.schemas.vacancy_strategy import VacancyStrategyOut
from app.services.vacancy_strategy import compute_strategy

router = APIRouter()

_RATE_LIMIT_PER_HOUR = 2


@router.get(
    "/resumes/{resume_id}/vacancies/{vacancy_id}/strategy",
    response_model=VacancyStrategyOut,
)
def get_strategy(
    resume_id: int,
    vacancy_id: int,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VacancyStrategyOut:
    resume = db.scalar(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == current_user.id,
        )
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    from app.models.vacancy import Vacancy

    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    # Rate limit: 2 strategy computations per hour per user (DB-enforced)
    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    user_resume_ids = db.scalars(select(Resume.id).where(Resume.user_id == current_user.id)).all()
    recent_count = db.scalar(
        select(func.count(VacancyStrategy.id)).where(
            VacancyStrategy.resume_id.in_(user_resume_ids),
            VacancyStrategy.computed_at >= one_hour_ago,
        )
    )
    # Only enforce the rate limit when actually recomputing (not serving from cache)
    cached = db.scalar(
        select(VacancyStrategy).where(
            VacancyStrategy.resume_id == resume_id,
            VacancyStrategy.vacancy_id == vacancy_id,
        )
    )
    from datetime import timedelta as _td

    from app.core.config import settings

    is_fresh = False
    if cached:
        age = datetime.now(UTC) - cached.computed_at.replace(tzinfo=UTC)
        is_fresh = age < _td(days=settings.vacancy_strategy_cache_ttl_days)

    if not is_fresh and not force and int(recent_count or 0) >= _RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail="Rate limit: at most 2 strategy computations per hour. Try again later.",
        )

    try:
        return compute_strategy(db, resume_id, vacancy_id, current_user.id, force=force)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        msg = str(exc)
        if "no_resume_profile" in msg:
            raise HTTPException(
                status_code=422,
                detail="Resume analysis is still in progress. Try again later.",
            )
        if "no_vacancy_profile" in msg:
            raise HTTPException(
                status_code=422,
                detail="Vacancy has not been analyzed yet. Try again later.",
            )
        raise HTTPException(status_code=422, detail=msg)
    except RuntimeError as exc:
        if "vacancy_strategy_disabled" in str(exc):
            raise HTTPException(status_code=503, detail="Vacancy strategy feature is disabled.")
        raise
