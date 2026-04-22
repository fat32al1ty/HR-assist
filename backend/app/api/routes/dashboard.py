from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.recommendation_job import RecommendationJob
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.repositories.resumes import get_active_resume_for_user, get_resume_for_user
from app.schemas.dashboard import UserDashboardRead, UserFunnelStatsRead
from app.services.vacancy_warmup import get_vacancy_warmup_status

router = APIRouter()


@router.get("/stats", response_model=UserDashboardRead)
def dashboard_stats(
    resume_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserDashboardRead:
    resolved_resume_id = resume_id
    if resolved_resume_id is None:
        active_resume = get_active_resume_for_user(db, user_id=current_user.id)
        if active_resume is not None:
            resolved_resume_id = int(active_resume.id)

    if (
        resolved_resume_id is not None
        and get_resume_for_user(db, resume_id=resolved_resume_id, user_id=current_user.id) is None
    ):
        resolved_resume_id = None

    analyzed_count = 0
    matched_count = 0
    selected_count = 0
    last_search_at: datetime | None = None

    if resolved_resume_id is not None:
        selected_count = int(
            db.scalar(
                select(func.count(UserVacancyFeedback.id)).where(
                    UserVacancyFeedback.user_id == current_user.id,
                    UserVacancyFeedback.resume_id == resolved_resume_id,
                    UserVacancyFeedback.liked.is_(True),
                )
            )
            or 0
        )
        latest_job = db.scalar(
            select(RecommendationJob)
            .where(
                RecommendationJob.user_id == current_user.id,
                RecommendationJob.resume_id == resolved_resume_id,
            )
            .order_by(RecommendationJob.created_at.desc())
            .limit(1)
        )
        if latest_job:
            last_search_at = latest_job.created_at
            metrics = latest_job.metrics if isinstance(latest_job.metrics, dict) else {}
            analyzed_count = int(metrics.get("analyzed", 0) or 0)
            matches = latest_job.matches
            matched_count = len(matches) if isinstance(matches, list) else 0

    next_warmup_eta: datetime | None = None
    warmup = get_vacancy_warmup_status()
    if warmup.get("enabled"):
        last_finished = warmup.get("last_finished_at")
        interval = warmup.get("interval_seconds")
        if last_finished is not None and interval is not None:
            if isinstance(last_finished, datetime):
                next_warmup_eta = last_finished + timedelta(seconds=int(interval))

    funnel = UserFunnelStatsRead(
        resume_id=resolved_resume_id,
        analyzed_count=analyzed_count,
        matched_count=matched_count,
        selected_count=selected_count,
        last_search_at=last_search_at,
        next_warmup_eta=next_warmup_eta,
    )
    return UserDashboardRead(generated_at=datetime.now(UTC), funnel=funnel)
