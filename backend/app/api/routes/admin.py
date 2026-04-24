from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import settings
from app.db.session import get_db
from app.models.recommendation_job import RecommendationJob
from app.models.resume import Resume
from app.models.user import User
from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.models.vacancy import Vacancy
from app.models.vacancy_profile import VacancyProfile
from app.repositories.resumes import get_active_resume_for_user, get_resume_for_user
from app.schemas.admin import (
    AdminActiveJob,
    AdminDashboardStatsRead,
    AdminJobCancelResponse,
    AdminOverviewRead,
    AdminRoleCount,
    QdrantStatsRead,
    ResumeStatsRead,
)
from app.services.recommendation_jobs import cancel_job_as_admin
from app.services.vacancy_warmup import get_vacancy_warmup_status
from app.services.vector_store import get_vector_store

router = APIRouter()


def _count_indexed_vacancies(db: Session) -> int:
    return int(db.scalar(select(func.count(Vacancy.id)).where(Vacancy.status == "indexed")) or 0)


def _count_profiled_vacancies(db: Session) -> int:
    return int(db.scalar(select(func.count(VacancyProfile.id))) or 0)


@router.get("/stats", response_model=AdminDashboardStatsRead)
def admin_stats(
    resume_id: int | None = Query(default=None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminDashboardStatsRead:
    vector_store = get_vector_store()
    qdrant_health = vector_store.healthcheck()
    indexed_vacancies = _count_indexed_vacancies(db)
    profiled_vacancies = _count_profiled_vacancies(db)
    coverage = 0.0
    if indexed_vacancies > 0:
        coverage = round((profiled_vacancies / indexed_vacancies) * 100.0, 2)

    preference_resume_id = resume_id
    if preference_resume_id is None:
        active_resume = get_active_resume_for_user(db, user_id=current_user.id)
        if active_resume is not None:
            preference_resume_id = int(active_resume.id)

    if preference_resume_id is not None:
        positive_pref, negative_pref = vector_store.get_user_preference_vectors(
            user_id=current_user.id, resume_id=preference_resume_id
        )
    else:
        positive_pref, negative_pref = None, None

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
        return AdminDashboardStatsRead(
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
                UserVacancyFeedback.resume_id == resume_id,
                UserVacancyFeedback.liked.is_(True),
            )
        )
        or 0
    )
    disliked_count = int(
        db.scalar(
            select(func.count(UserVacancyFeedback.id)).where(
                UserVacancyFeedback.user_id == current_user.id,
                UserVacancyFeedback.resume_id == resume_id,
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

    return AdminDashboardStatsRead(
        generated_at=datetime.now(UTC),
        qdrant=qdrant_stats,
        resume=resume_stats,
    )


@router.get("/overview", response_model=AdminOverviewRead)
def admin_overview(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminOverviewRead:
    now = datetime.now(UTC)
    one_day_ago = now - timedelta(days=1)

    users_total = int(db.scalar(select(func.count(User.id))) or 0)
    users_active_last_day = int(
        db.scalar(select(func.count(User.id)).where(User.last_login_at >= one_day_ago)) or 0
    )
    resumes_total = int(db.scalar(select(func.count(Resume.id))) or 0)
    vacancies_total = int(db.scalar(select(func.count(Vacancy.id))) or 0)
    vacancies_indexed = _count_indexed_vacancies(db)

    # Roles searched: for each recommendation_jobs row, take the target_role
    # from the linked resume's analysis JSON. Group and order by frequency.
    # Column is sqlalchemy `JSON` (not JSONB), so `.astext` isn't available —
    # use Postgres' json_extract_path_text which returns TEXT directly.
    role_expr = func.json_extract_path_text(Resume.analysis, "target_role")
    role_rows = db.execute(
        select(role_expr.label("role"), func.count(RecommendationJob.id).label("cnt"))
        .select_from(RecommendationJob)
        .join(Resume, Resume.id == RecommendationJob.resume_id)
        .where(role_expr.isnot(None))
        .where(func.length(func.trim(role_expr)) > 0)
        .group_by(role_expr)
        .order_by(func.count(RecommendationJob.id).desc())
        .limit(10)
    ).all()
    top_searched_roles = [AdminRoleCount(role=str(r.role), count=int(r.cnt)) for r in role_rows]

    active_rows = db.execute(
        select(RecommendationJob, User.email, Resume.analysis)
        .join(User, User.id == RecommendationJob.user_id)
        .join(Resume, Resume.id == RecommendationJob.resume_id)
        .where(RecommendationJob.status.in_(("queued", "running")))
        .order_by(RecommendationJob.created_at.desc())
    ).all()
    active_jobs: list[AdminActiveJob] = []
    for job, email, analysis in active_rows:
        target_role: str | None = None
        if isinstance(analysis, dict):
            raw = analysis.get("target_role")
            if isinstance(raw, str) and raw.strip():
                target_role = raw.strip()
        active_jobs.append(
            AdminActiveJob(
                id=job.id,
                user_id=int(job.user_id),
                user_email=email,
                resume_id=int(job.resume_id),
                target_role=target_role,
                status=job.status,
                stage=job.stage,
                progress=int(job.progress or 0),
                cancel_requested=bool(job.cancel_requested),
                created_at=job.created_at,
                started_at=job.started_at,
            )
        )

    return AdminOverviewRead(
        generated_at=now,
        users_total=users_total,
        users_active_last_day=users_active_last_day,
        resumes_total=resumes_total,
        vacancies_total=vacancies_total,
        vacancies_indexed=vacancies_indexed,
        top_searched_roles=top_searched_roles,
        active_jobs=active_jobs,
    )


@router.post("/jobs/{job_id}/cancel", response_model=AdminJobCancelResponse)
def admin_cancel_job(
    job_id: str,
    current_user: User = Depends(require_admin),
) -> AdminJobCancelResponse:
    snapshot = cancel_job_as_admin(job_id=job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return AdminJobCancelResponse(
        id=str(snapshot["id"]),
        status=str(snapshot["status"]),
        cancel_requested=bool(snapshot.get("cancel_requested", False)),
    )


@router.get("/warmup")
def admin_warmup(current_user: User = Depends(require_admin)) -> dict[str, object]:
    return get_vacancy_warmup_status()


@router.get("/config-check")
def admin_config_check(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception:
        database_status = "unavailable"

    jwt_secret_status = "configured"
    if settings.jwt_secret_key == "change-me-before-production":
        jwt_secret_status = "weak_default"

    vector_store_status = get_vector_store().healthcheck()

    return {
        "app_env": settings.app_env,
        "database": database_status,
        "openai": {
            "api_key": "configured" if settings.openai_api_key else "missing",
            "base_url": "configured" if settings.openai_base_url else "default",
            "analysis_model": settings.openai_analysis_model,
            "matching_model": settings.openai_matching_model,
            "reasoning_effort": settings.openai_reasoning_effort,
            "embedding_model": settings.openai_embedding_model,
        },
        "vector_store": {
            "provider": "qdrant",
            "status": vector_store_status["status"],
            "url": vector_store_status.get("url"),
            "collection_prefix": settings.qdrant_collection_prefix,
            "vector_size": settings.vector_size,
            "collections": vector_store_status.get("collections", []),
            "api_key": "configured" if settings.qdrant_api_key else "missing",
        },
        "vacancy_sources": {
            "brave_api": {
                "status": "configured" if settings.brave_api_key else "missing",
                "web_search_url": settings.brave_web_search_url,
            }
        },
        "jwt_secret_key": jwt_secret_status,
        "secrets": {
            "source": "runtime_environment",
            "values_exposed": False,
        },
    }
