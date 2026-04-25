from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Resume Intelligence Platform"
    app_env: str = "local"
    database_url: str = (
        "postgresql+psycopg://resume_user:resume_pass@localhost:5432/resume_platform"
    )
    jwt_secret_key: str = Field(default="change-me-before-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    beta_tester_keys: str | None = None
    auth_email_delivery_mode: str = "console"
    auth_email_from: str = "no-reply@hr-assistant.local"
    auth_email_smtp_host: str | None = None
    auth_email_smtp_port: int = 587
    auth_email_smtp_username: str | None = None
    auth_email_smtp_password: str | None = None
    auth_email_smtp_starttls: bool = True
    auth_email_smtp_ssl: bool = False
    auth_email_code_ttl_minutes: int = 15
    auth_login_code_ttl_minutes: int = 10
    auth_code_max_attempts: int = 5
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_analysis_model: str = "gpt-5.4-mini"
    openai_matching_model: str = "gpt-5.4"
    openai_reasoning_effort: str = "none"
    openai_analysis_timeout_seconds: int = 60
    openai_embedding_model: str = "text-embedding-3-large"
    openai_request_budget_usd: float = 0.10
    openai_enforce_request_budget: bool = True
    openai_user_daily_budget_usd: float = 1.00
    openai_enforce_user_daily_budget: bool = True
    recommendation_job_timeout_seconds: int = 420
    vacancy_warmup_enabled: bool = True
    vacancy_warmup_interval_seconds: int = 600
    vacancy_warmup_queries_per_cycle: int = 2
    vacancy_warmup_discover_count: int = 25
    vacancy_warmup_max_analyzed_per_query: int = 2
    vacancy_warmup_cycle_timeout_seconds: int = 120
    vacancy_warmup_rf_only: bool = True
    vacancy_warmup_on_resume_upload: bool = True
    vacancy_warmup_on_upload_discover_count: int = 40
    vacancy_warmup_on_upload_max_analyzed: int = 40
    vacancy_profile_backfill_enabled: bool = True
    vacancy_profile_backfill_limit_per_cycle: int = 3
    preference_decay_enabled: bool = False
    preference_decay_half_life_days: float = 30.0
    rerank_enabled: bool = False
    rerank_model_name: str = "BAAI/bge-reranker-v2-m3"
    rerank_candidate_limit: int = 50
    rerank_blend_weight: float = 0.6
    rerank_batch_size: int = 16
    llm_rerank_enabled: bool = False
    llm_rerank_model: str = "gpt-4o-mini"
    llm_rerank_top_k: int = 20
    llm_rerank_budget_floor_usd: float = 0.05
    llm_rerank_cache_ttl_hours: int = 24
    openai_responses_input_usd_per_1m: float = 2.0
    openai_responses_output_usd_per_1m: float = 8.0
    openai_embeddings_input_usd_per_1m: float = 0.13
    openai_cost_safety_multiplier: float = 1.15
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str | None = None
    qdrant_collection_prefix: str = "hr_assistant"
    vector_size: int = 3072
    brave_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("BRAVE_API_KEY", "BRAVE_API")
    )
    brave_web_search_url: str = "https://api.search.brave.com/res/v1/web/search"
    hh_api_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("HH_API_TOKEN", "HH_TOKEN", "HH_ACCESS_TOKEN"),
    )
    hh_area: int = 113
    superjob_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPERJOB_API_KEY", "SUPERJOB_KEY", "SUPERJOB_APP_ID"),
    )
    superjob_vacancies_url: str = "https://api.superjob.ru/2.0/vacancies/"
    habr_career_api_url: str = "https://career.habr.com/api/v1/vacancies"
    habr_career_api_token: str | None = Field(
        default=None, validation_alias=AliasChoices("HABR_CAREER_API_TOKEN")
    )
    storage_dir: str = "storage"
    max_upload_size_mb: int = 10
    cors_origins: list[str] = ["http://localhost:3000"]
    # Level 2 D2: exclude vacancies already shown to the user within a
    # rolling window from matcher recall. Keeps the user from seeing the
    # same top-N twice while the pool is still small.
    feature_exclude_seen_enabled: bool = True
    feature_exclude_seen_window_days: int = 14
    feature_superjob_enabled: bool = False
    feature_habr_enabled: bool = False
    feature_public_sources_enabled: bool = False
    matching_pipeline_version: str = "3.0"
    matching_score_cache_ttl_days: int = 7
    matching_score_cache_enabled: bool = True
    feature_salary_predictor_enabled: bool = True
    feature_salary_baseline_enabled: bool = False
    feature_resume_audit_enabled: bool = True
    feature_resume_audit_template_mode_enabled: bool = False
    feature_onboarding_llm_classifier_enabled: bool = False
    resume_audit_cost_cap_usd_per_day: float = 0.05
    resume_audit_cache_ttl_days: int = 7

    @field_validator(
        "openai_api_key",
        "openai_base_url",
        "qdrant_api_key",
        "brave_api_key",
        "hh_api_token",
        "superjob_api_key",
        "habr_career_api_token",
        "beta_tester_keys",
        "auth_email_smtp_host",
        "auth_email_smtp_username",
        "auth_email_smtp_password",
        mode="before",
    )
    @classmethod
    def blank_string_to_none(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def validate_runtime_settings() -> None:
    is_production = settings.app_env.lower() == "production"
    weak_jwt_secret = (
        not settings.jwt_secret_key or settings.jwt_secret_key == "change-me-before-production"
    )
    beta_keys = {
        item.strip() for item in (settings.beta_tester_keys or "").split(",") if item.strip()
    }

    if is_production and weak_jwt_secret:
        raise RuntimeError("JWT_SECRET_KEY must be configured with a strong secret in production")
    if is_production and not beta_keys:
        raise RuntimeError("BETA_TESTER_KEYS must be configured in production")
    if (
        settings.app_env.lower() not in {"local", "test"}
        and settings.auth_email_delivery_mode.lower() == "console"
    ):
        raise RuntimeError(
            "AUTH_EMAIL_DELIVERY_MODE=console is not allowed outside local/test environments"
        )
    if is_production and settings.auth_email_delivery_mode.lower() != "smtp":
        raise RuntimeError("AUTH_EMAIL_DELIVERY_MODE must be smtp in production")
    if is_production and settings.auth_email_delivery_mode.lower() == "smtp":
        if (
            not settings.auth_email_smtp_host
            or not settings.auth_email_smtp_username
            or not settings.auth_email_smtp_password
        ):
            raise RuntimeError("SMTP settings must be configured in production")
