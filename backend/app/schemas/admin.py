from datetime import datetime

from pydantic import BaseModel, Field


class QdrantStatsRead(BaseModel):
    status: str
    collections: list[str] = Field(default_factory=list)
    indexed_vacancies: int
    profiled_vacancies: int
    profile_coverage_percent: float
    preference_positive_ready: bool
    preference_negative_ready: bool


class ResumeStatsRead(BaseModel):
    resume_id: int
    resume_embedded: bool
    target_role: str | None = None
    specialization: str | None = None
    indexed_vacancies: int
    vector_candidates_top300: int
    relevant_over_55_top300: int
    selected_count: int
    disliked_count: int
    last_job_id: str | None = None
    last_job_status: str | None = None
    last_job_matches: int | None = None
    last_job_sources: int | None = None
    last_job_analyzed: int | None = None
    last_job_created_at: datetime | None = None
    last_query: str | None = None


class AdminDashboardStatsRead(BaseModel):
    generated_at: datetime
    qdrant: QdrantStatsRead
    resume: ResumeStatsRead | None = None


class AdminRoleCount(BaseModel):
    role: str
    count: int


class AdminActiveJob(BaseModel):
    id: str
    user_id: int
    user_email: str | None = None
    resume_id: int
    target_role: str | None = None
    status: str
    stage: str
    progress: int
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None = None


class AdminRecentJob(BaseModel):
    id: str
    user_id: int
    user_email: str | None = None
    resume_id: int
    target_role: str | None = None
    status: str
    stage: str
    progress: int
    query: str | None = None
    matches_count: int = 0
    created_at: datetime
    finished_at: datetime | None = None


class AdminOverviewRead(BaseModel):
    generated_at: datetime
    users_total: int
    users_active_last_day: int
    resumes_total: int
    vacancies_total: int
    vacancies_indexed: int
    top_searched_roles: list[AdminRoleCount] = Field(default_factory=list)
    active_jobs: list[AdminActiveJob] = Field(default_factory=list)
    recent_jobs: list[AdminRecentJob] = Field(default_factory=list)


class AdminJobCancelResponse(BaseModel):
    id: str
    status: str
    cancel_requested: bool


class AdminFunnelStage(BaseModel):
    """One row of the admin waterfall.

    ``value`` is the count for the stage. ``kind`` lets the UI distinguish
    between cumulative counters that a vacancy passes through (``flow``),
    exclusive drop buckets (``drop``), and meta counters (``meta`` — e.g.
    matcher_runs_total). ``key`` is the raw metrics-dict key so the UI can
    link back to the full metrics blob for debugging.
    """

    key: str
    label: str
    value: int
    kind: str = "flow"


class AdminJobFunnelRead(BaseModel):
    job_id: str
    status: str
    stage: str
    user_id: int
    user_email: str | None = None
    resume_id: int
    target_role: str | None = None
    query: str | None = None
    stages: list[AdminFunnelStage] = Field(default_factory=list)
    drops: list[AdminFunnelStage] = Field(default_factory=list)
    matcher_stages: list[AdminFunnelStage] = Field(default_factory=list)
    shown_to_user: int
    fetched_raw: int
    total_drops: int
    residual: int
    metrics: dict[str, int] = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
