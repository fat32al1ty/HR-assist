from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import HOME_CITY_MAX, JOB_TITLE_MAX, PREFERRED_TITLES_MAX


class VacancyDiscoverRequest(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    count: int = Field(default=30, ge=1, le=100)
    rf_only: bool = True
    use_brave_fallback: bool = False


class VacancyRead(BaseModel):
    id: int
    source: str
    source_url: str
    title: str
    company: str | None
    location: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VacancyDiscoverResponse(BaseModel):
    indexed: int
    fetched: int
    prefiltered: int
    analyzed: int
    filtered: int
    failed: int
    already_indexed_skipped: int
    skipped_parse_errors: int = 0
    sources: list[str] = Field(default_factory=list)
    vacancies: list[VacancyRead]


class VacancyMatchRead(BaseModel):
    vacancy_id: int
    title: str
    source_url: str
    company: str | None
    location: str | None
    similarity_score: float
    profile: dict[str, Any] | None = None
    # "strong" (score >= 0.60), "maybe" (0.45 <= score < 0.60), or null for
    # older/lexical-fallback items. The UI groups strong and maybe into
    # separate blocks; null falls through to "maybe".
    tier: str | None = None


class PreferenceOverrides(BaseModel):
    """Per-request overrides for job preferences — do not persist to the user row.

    Lets a jobseeker say "just this one search, any city" without having to
    edit their profile preferences.
    """

    preferred_work_format: Literal["remote", "hybrid", "office", "any"] | None = None
    relocation_mode: Literal["home_only", "any_city"] | None = None
    home_city: str | None = Field(default=None, max_length=HOME_CITY_MAX)
    preferred_titles: list[str] | None = Field(default=None, max_length=PREFERRED_TITLES_MAX)

    @field_validator("preferred_titles")
    @classmethod
    def _validate_titles(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        for raw in value:
            title = raw.strip()
            if not title:
                continue
            if len(title) > JOB_TITLE_MAX:
                raise ValueError(f"title longer than {JOB_TITLE_MAX} characters")
            cleaned.append(title)
        return cleaned

    @field_validator("home_city")
    @classmethod
    def _normalize_city(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class VacancyRecommendRequest(BaseModel):
    discover_count: int = Field(default=40, ge=1, le=100)
    match_limit: int = Field(default=40, ge=1, le=50)
    deep_scan: bool = True
    rf_only: bool = True
    use_brave_fallback: bool = False
    use_prefetched_index: bool = True
    discover_if_few_matches: bool = True
    min_prefetched_matches: int = Field(default=10, ge=1, le=20)
    preference_overrides: PreferenceOverrides | None = None


class OpenAIUsageRead(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    embedding_tokens: int
    total_tokens: int
    api_calls: int
    estimated_cost_usd: float
    budget_usd: float
    budget_exceeded: bool
    budget_enforced: bool


class VacancyRecommendResponse(BaseModel):
    query: str
    indexed: int
    fetched: int
    prefiltered: int
    analyzed: int
    filtered: int
    failed: int
    already_indexed_skipped: int
    skipped_parse_errors: int = 0
    sources: list[str] = Field(default_factory=list)
    openai_usage: OpenAIUsageRead
    matches: list[VacancyMatchRead]


class VacancyFeedbackRequest(BaseModel):
    vacancy_id: int


class VacancyFeedbackResponse(BaseModel):
    vacancy_id: int
    disliked: bool
    liked: bool


class RecommendationJobStartResponse(BaseModel):
    job_id: str
    status: str


class RecommendationJobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int
    query: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    matches: list[VacancyMatchRead] = Field(default_factory=list)
    openai_usage: OpenAIUsageRead | None = None
    error_message: str | None = None
    active: bool = False
    cancel_requested: bool = False
