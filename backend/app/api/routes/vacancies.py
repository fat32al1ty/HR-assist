from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.repositories.resumes import get_active_resume_for_user, get_resume_for_user
from app.repositories.user_vacancy_feedback import (
    list_disliked_vacancies,
    list_disliked_vacancy_ids,
    list_liked_vacancies,
    list_liked_vacancy_ids,
    set_vacancy_disliked,
    set_vacancy_liked,
)
from app.repositories.vacancies import list_vacancies
from app.schemas.vacancy import (
    RecommendationJobStartResponse,
    RecommendationJobStatusResponse,
    VacancyDiscoverRequest,
    VacancyDiscoverResponse,
    VacancyFeedbackRequest,
    VacancyFeedbackResponse,
    VacancyMatchRead,
    VacancyRead,
    VacancyRecommendRequest,
    VacancyRecommendResponse,
)
from app.services.matching_service import match_vacancies_for_resume
from app.services.openai_usage import (
    DAILY_BUDGET_USER_MESSAGE,
    DailyBudgetExceeded,
    OpenAIBudgetExceeded,
    openai_budget_scope,
)
from app.services.recommendation_jobs import (
    DailyBudgetReachedBeforeStart,
    cancel_job_for_user,
    get_job_snapshot_for_user,
    get_latest_job_snapshot_for_user,
    start_recommendation_job,
)
from app.services.user_preference_profile_pipeline import recompute_user_preference_profile
from app.services.vacancy_pipeline import discover_and_index_vacancies
from app.services.vacancy_recommendation import recommend_vacancies_for_resume

router = APIRouter()


def _require_active_resume_id(db: Session, user: User) -> int:
    resume = get_active_resume_for_user(db, user_id=user.id)
    if resume is None:
        raise HTTPException(status_code=409, detail="no_active_resume")
    return int(resume.id)


def _excluded_ids_for_active_resume(db: Session, user: User) -> set[int]:
    resume = get_active_resume_for_user(db, user_id=user.id)
    if resume is None:
        return set()
    return list_disliked_vacancy_ids(db, user_id=user.id, resume_id=int(resume.id)).union(
        list_liked_vacancy_ids(db, user_id=user.id, resume_id=int(resume.id))
    )


def _filter_matches_by_feedback(*, matches: list[dict], excluded_ids: set[int]) -> list[dict]:
    if not matches or not excluded_ids:
        return matches
    filtered: list[dict] = []
    for item in matches:
        if not isinstance(item, dict):
            continue
        vacancy_id = item.get("vacancy_id")
        try:
            normalized = int(vacancy_id)
        except (TypeError, ValueError):
            filtered.append(item)
            continue
        if normalized in excluded_ids:
            continue
        filtered.append(item)
    return filtered


@router.post("/discover", response_model=VacancyDiscoverResponse)
def discover_vacancies(
    payload: VacancyDiscoverRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VacancyDiscoverResponse:
    _ = current_user
    result = discover_and_index_vacancies(
        db,
        query=payload.query,
        count=payload.count,
        rf_only=payload.rf_only,
        use_brave_fallback=payload.use_brave_fallback,
    )
    return VacancyDiscoverResponse(
        indexed=result.metrics.indexed,
        fetched=result.metrics.fetched,
        prefiltered=result.metrics.prefiltered,
        analyzed=result.metrics.analyzed,
        filtered=result.metrics.filtered,
        failed=result.metrics.failed,
        already_indexed_skipped=result.metrics.already_indexed_skipped,
        skipped_parse_errors=result.metrics.skipped_parse_errors,
        sources=result.metrics.sources or [],
        vacancies=result.indexed_vacancies,
    )


@router.get("", response_model=list[VacancyRead])
def get_vacancies(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VacancyRead]:
    _ = current_user
    return list_vacancies(db, limit=limit)


@router.get("/match/{resume_id}", response_model=list[VacancyMatchRead])
def match_vacancies(
    resume_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VacancyMatchRead]:
    return match_vacancies_for_resume(db, resume_id=resume_id, user_id=current_user.id, limit=limit)


@router.post("/recommend/{resume_id}", response_model=VacancyRecommendResponse)
def recommend_vacancies(
    resume_id: int,
    payload: VacancyRecommendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VacancyRecommendResponse:
    with openai_budget_scope(
        budget_usd=settings.openai_request_budget_usd,
        budget_enforced=settings.openai_enforce_request_budget,
        user_id=current_user.id,
        daily_budget_usd=settings.openai_user_daily_budget_usd,
        daily_budget_enforced=settings.openai_enforce_user_daily_budget,
    ) as usage_tracker:
        try:
            query, metrics, matches = recommend_vacancies_for_resume(
                db,
                resume_id=resume_id,
                user_id=current_user.id,
                discover_count=payload.discover_count,
                match_limit=payload.match_limit,
                deep_scan=payload.deep_scan,
                rf_only=payload.rf_only,
                use_brave_fallback=payload.use_brave_fallback,
                use_prefetched_index=payload.use_prefetched_index,
                discover_if_few_matches=payload.discover_if_few_matches,
                min_prefetched_matches=payload.min_prefetched_matches,
                preference_overrides=(
                    payload.preference_overrides.model_dump(exclude_unset=True)
                    if payload.preference_overrides is not None
                    else None
                ),
            )
        except DailyBudgetExceeded as error:
            raise HTTPException(status_code=429, detail=DAILY_BUDGET_USER_MESSAGE) from error
        except OpenAIBudgetExceeded as error:
            snapshot = error.snapshot
            raise HTTPException(
                status_code=422,
                detail=(
                    "OpenAI budget exceeded for this request. "
                    f"Spent ${snapshot.estimated_cost_usd:.4f} with limit ${snapshot.budget_usd:.4f}. "
                    "Reduce search depth/count or increase budget."
                ),
            ) from error

        usage = usage_tracker.snapshot().to_dict()
    return VacancyRecommendResponse(
        query=query,
        indexed=metrics.indexed,
        fetched=metrics.fetched,
        prefiltered=metrics.prefiltered,
        analyzed=metrics.analyzed,
        filtered=metrics.filtered,
        failed=metrics.failed,
        already_indexed_skipped=metrics.already_indexed_skipped,
        skipped_parse_errors=metrics.skipped_parse_errors,
        sources=metrics.sources or [],
        openai_usage=usage,
        matches=matches,
    )


@router.post("/recommend/start/{resume_id}", response_model=RecommendationJobStartResponse)
def start_recommendation(
    resume_id: int,
    payload: VacancyRecommendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationJobStartResponse:
    if get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    try:
        job_id = start_recommendation_job(
            user_id=current_user.id,
            resume_id=resume_id,
            request_payload=payload.model_dump(),
        )
    except DailyBudgetReachedBeforeStart as error:
        raise HTTPException(status_code=429, detail=DAILY_BUDGET_USER_MESSAGE) from error
    return RecommendationJobStartResponse(job_id=job_id, status="queued")


@router.get("/recommend/status/{job_id}", response_model=RecommendationJobStatusResponse)
def recommendation_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationJobStatusResponse:
    snapshot = get_job_snapshot_for_user(job_id=job_id, user_id=current_user.id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Recommendation job not found")
    excluded_ids = _excluded_ids_for_active_resume(db, current_user)
    matches = _filter_matches_by_feedback(
        matches=snapshot.get("matches") or [], excluded_ids=excluded_ids
    )
    return RecommendationJobStatusResponse(
        job_id=snapshot["id"],
        status=snapshot["status"],
        stage=snapshot["stage"],
        progress=int(snapshot["progress"]),
        query=snapshot.get("query"),
        metrics=snapshot.get("metrics") or {},
        matches=matches,
        openai_usage=snapshot.get("openai_usage") or None,
        error_message=snapshot.get("error_message"),
        active=bool(snapshot.get("active")),
        cancel_requested=bool(snapshot.get("cancel_requested")),
    )


@router.get("/recommend/latest", response_model=RecommendationJobStatusResponse)
def latest_recommendation_status(
    resume_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationJobStatusResponse:
    snapshot = get_latest_job_snapshot_for_user(user_id=current_user.id, resume_id=resume_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Recommendation job not found")
    excluded_ids = _excluded_ids_for_active_resume(db, current_user)
    matches = _filter_matches_by_feedback(
        matches=snapshot.get("matches") or [], excluded_ids=excluded_ids
    )
    return RecommendationJobStatusResponse(
        job_id=snapshot["id"],
        status=snapshot["status"],
        stage=snapshot["stage"],
        progress=int(snapshot["progress"]),
        query=snapshot.get("query"),
        metrics=snapshot.get("metrics") or {},
        matches=matches,
        openai_usage=snapshot.get("openai_usage") or None,
        error_message=snapshot.get("error_message"),
        active=bool(snapshot.get("active")),
        cancel_requested=bool(snapshot.get("cancel_requested")),
    )


@router.delete("/recommend/{job_id}", response_model=RecommendationJobStatusResponse)
def cancel_recommendation(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationJobStatusResponse:
    """Mark a running or queued job for cancellation.

    The worker polls the cancel flag between stages and exits at the next
    safe boundary, so the response is immediate but the actual transition
    to `failed`/`cancelled` lands on the next status poll.
    """
    snapshot = cancel_job_for_user(job_id=job_id, user_id=current_user.id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Recommendation job not found")
    excluded_ids = _excluded_ids_for_active_resume(db, current_user)
    matches = _filter_matches_by_feedback(
        matches=snapshot.get("matches") or [], excluded_ids=excluded_ids
    )
    return RecommendationJobStatusResponse(
        job_id=snapshot["id"],
        status=snapshot["status"],
        stage=snapshot["stage"],
        progress=int(snapshot["progress"]),
        query=snapshot.get("query"),
        metrics=snapshot.get("metrics") or {},
        matches=matches,
        openai_usage=snapshot.get("openai_usage") or None,
        error_message=snapshot.get("error_message"),
        active=bool(snapshot.get("active")),
        cancel_requested=bool(snapshot.get("cancel_requested")),
    )


@router.post("/feedback/dislike", response_model=VacancyFeedbackResponse)
def dislike_vacancy(
    payload: VacancyFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VacancyFeedbackResponse:
    resume_id = _require_active_resume_id(db, current_user)
    feedback = set_vacancy_disliked(
        db,
        user_id=current_user.id,
        resume_id=resume_id,
        vacancy_id=payload.vacancy_id,
        disliked=True,
    )
    recompute_user_preference_profile(db, user_id=current_user.id, resume_id=resume_id)
    return VacancyFeedbackResponse(
        vacancy_id=feedback.vacancy_id, disliked=feedback.disliked, liked=feedback.liked
    )


@router.post("/feedback/like", response_model=VacancyFeedbackResponse)
def like_vacancy(
    payload: VacancyFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VacancyFeedbackResponse:
    resume_id = _require_active_resume_id(db, current_user)
    feedback = set_vacancy_liked(
        db,
        user_id=current_user.id,
        resume_id=resume_id,
        vacancy_id=payload.vacancy_id,
        liked=True,
    )
    recompute_user_preference_profile(db, user_id=current_user.id, resume_id=resume_id)
    return VacancyFeedbackResponse(
        vacancy_id=feedback.vacancy_id, disliked=feedback.disliked, liked=feedback.liked
    )


@router.post("/feedback/unlike", response_model=VacancyFeedbackResponse)
def unlike_vacancy(
    payload: VacancyFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VacancyFeedbackResponse:
    resume_id = _require_active_resume_id(db, current_user)
    feedback = set_vacancy_liked(
        db,
        user_id=current_user.id,
        resume_id=resume_id,
        vacancy_id=payload.vacancy_id,
        liked=False,
    )
    recompute_user_preference_profile(db, user_id=current_user.id, resume_id=resume_id)
    return VacancyFeedbackResponse(
        vacancy_id=feedback.vacancy_id, disliked=feedback.disliked, liked=feedback.liked
    )


@router.get("/feedback/selected", response_model=list[VacancyMatchRead])
def selected_vacancies(
    limit: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VacancyMatchRead]:
    resume_id = _require_active_resume_id(db, current_user)
    selected = list_liked_vacancies(db, user_id=current_user.id, resume_id=resume_id, limit=limit)
    return [
        VacancyMatchRead(
            vacancy_id=item.id,
            title=item.title,
            source_url=item.source_url,
            company=item.company,
            location=item.location,
            similarity_score=1.0,
            profile={"selected": True},
        )
        for item in selected
    ]


@router.post("/feedback/undislike", response_model=VacancyFeedbackResponse)
def undislike_vacancy(
    payload: VacancyFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VacancyFeedbackResponse:
    resume_id = _require_active_resume_id(db, current_user)
    set_vacancy_disliked(
        db,
        user_id=current_user.id,
        resume_id=resume_id,
        vacancy_id=payload.vacancy_id,
        disliked=False,
    )
    feedback = set_vacancy_liked(
        db,
        user_id=current_user.id,
        resume_id=resume_id,
        vacancy_id=payload.vacancy_id,
        liked=True,
    )
    recompute_user_preference_profile(db, user_id=current_user.id, resume_id=resume_id)
    return VacancyFeedbackResponse(
        vacancy_id=feedback.vacancy_id, disliked=feedback.disliked, liked=feedback.liked
    )


@router.get("/feedback/disliked", response_model=list[VacancyMatchRead])
def disliked_vacancies(
    limit: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VacancyMatchRead]:
    resume_id = _require_active_resume_id(db, current_user)
    disliked = list_disliked_vacancies(
        db, user_id=current_user.id, resume_id=resume_id, limit=limit
    )
    return [
        VacancyMatchRead(
            vacancy_id=item.id,
            title=item.title,
            source_url=item.source_url,
            company=item.company,
            location=item.location,
            similarity_score=0.0,
            profile={"disliked": True},
        )
        for item in disliked
    ]
