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


class AdminOverviewRead(BaseModel):
    generated_at: datetime
    users_total: int
    users_active_last_day: int
    resumes_total: int
    vacancies_total: int
    vacancies_indexed: int
    top_searched_roles: list[AdminRoleCount] = Field(default_factory=list)
    active_jobs: list[AdminActiveJob] = Field(default_factory=list)


class AdminJobCancelResponse(BaseModel):
    id: str
    status: str
    cancel_requested: bool
