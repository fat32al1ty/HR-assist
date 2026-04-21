from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.recommendation_job import RecommendationJob
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.models.vacancy import Vacancy
from app.models.vacancy_profile import VacancyProfile
from app.repositories.resumes import get_resume_for_user
from app.schemas.dashboard import DashboardStatsRead, QdrantStatsRead, ResumeStatsRead
from app.services.vector_store import get_vector_store

router = APIRouter()


def _count_indexed_vacancies(db: Session) -> int:
    return int(db.scalar(select(func.count(Vacancy.id)).where(Vacancy.status == "indexed")) or 0)


def _count_profiled_vacancies(db: Session) -> int:
    return int(db.scalar(select(func.count(VacancyProfile.id))) or 0)


@router.get("/stats", response_model=DashboardStatsRead)
def dashboard_stats(
    resume_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardStatsRead:
    vector_store = get_vector_store()
    qdrant_health = vector_store.healthcheck()
    indexed_vacancies = _count_indexed_vacancies(db)
    profiled_vacancies = _count_profiled_vacancies(db)
    coverage = 0.0
    if indexed_vacancies > 0:
        coverage = round((profiled_vacancies / indexed_vacancies) * 100.0, 2)

    positive_pref, negative_pref = vector_store.get_user_preference_vectors(user_id=current_user.id)
    qdrant_stats = QdrantStatsRead(
        status=str(qdrant_health.get("status") or "unknown"),
        collections=list(qdrant_health.get("collections", [])),
        indexed_vacancies=indexed_vacancies,
        profiled_vacancies=profiled_vacancies,
        profile_coverage_percent=coverage,
        preference_positive_ready=positive_pref is not None,
        preference_negative_ready=negative_pref is not None,
    )

    if resume_id is None:
        return DashboardStatsRead(
            generated_at=datetime.now(UTC),
            qdrant=qdrant_stats,
            resume=None,
        )

    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    query_vector = vector_store.get_resume_vector(resume_id=resume_id)
    vector_candidates_top300 = 0
    relevant_over_55_top300 = 0
    if query_vector is not None:
        vector_found = vector_store.search_vacancy_profiles(query_vector=query_vector, limit=300)
        vector_candidates_top300 = len(vector_found)
        relevant_over_55_top300 = sum(1 for _, score, _ in vector_found if float(score) >= 0.55)

    selected_count = int(
        db.scalar(
            select(func.count(UserVacancyFeedback.id)).where(
                UserVacancyFeedback.user_id == current_user.id,
                UserVacancyFeedback.liked.is_(True),
            )
        )
        or 0
    )
    disliked_count = int(
        db.scalar(
            select(func.count(UserVacancyFeedback.id)).where(
                UserVacancyFeedback.user_id == current_user.id,
                UserVacancyFeedback.disliked.is_(True),
            )
        )
        or 0
    )
    latest_job = db.scalar(
        select(RecommendationJob)
        .where(
            RecommendationJob.user_id == current_user.id,
            RecommendationJob.resume_id == resume_id,
        )
        .order_by(RecommendationJob.created_at.desc())
        .limit(1)
    )

    analysis = resume.analysis or {}
    target_role = (
        analysis.get("target_role") if isinstance(analysis.get("target_role"), str) else None
    )
    specialization = (
        analysis.get("specialization") if isinstance(analysis.get("specialization"), str) else None
    )
    last_metrics = latest_job.metrics if latest_job and isinstance(latest_job.metrics, dict) else {}
    last_matches = (
        len(latest_job.matches) if latest_job and isinstance(latest_job.matches, list) else None
    )
    last_query = latest_job.query if latest_job else None

    resume_stats = ResumeStatsRead(
        resume_id=resume_id,
        resume_embedded=query_vector is not None,
        target_role=target_role,
        specialization=specialization,
        indexed_vacancies=indexed_vacancies,
        vector_candidates_top300=vector_candidates_top300,
        relevant_over_55_top300=relevant_over_55_top300,
        selected_count=selected_count,
        disliked_count=disliked_count,
        last_job_id=latest_job.id if latest_job else None,
        last_job_status=latest_job.status if latest_job else None,
        last_job_matches=last_matches,
        last_job_sources=int(last_metrics.get("fetched", 0) or 0) if latest_job else None,
        last_job_analyzed=int(last_metrics.get("analyzed", 0) or 0) if latest_job else None,
        last_job_created_at=latest_job.created_at if latest_job else None,
        last_query=last_query,
    )

    return DashboardStatsRead(
        generated_at=datetime.now(UTC),
        qdrant=qdrant_stats,
        resume=resume_stats,
    )
