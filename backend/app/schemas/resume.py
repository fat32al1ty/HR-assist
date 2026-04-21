from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import (
    HOME_CITY_MAX,
    JOB_TITLE_MAX,
    PREFERRED_TITLES_MAX,
    RelocationMode,
    WorkFormat,
)

Seniority = Literal["junior", "middle", "senior", "lead"]

# Part A edit constraints — the self-check fields the user can override after LLM parse.
TARGET_ROLE_MAX = 200
SPECIALIZATION_MAX = 200
TOP_SKILLS_MAX = 3
RESUME_LABEL_MAX = 32


class ResumeRead(BaseModel):
    id: int
    original_filename: str
    content_type: str
    status: str
    extracted_text: str | None
    analysis: dict[str, Any] | None
    error_message: str | None
    is_active: bool
    label: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeLabelUpdate(BaseModel):
    """PATCH /resumes/{id} payload for the multi-profile switcher label.

    Empty string clears the label (UI then falls back to the filename).
    Anything over RESUME_LABEL_MAX chars is rejected so the badge pill stays
    on a single line at typical viewport widths.
    """

    label: str | None = Field(default=None, max_length=RESUME_LABEL_MAX)

    @field_validator("label")
    @classmethod
    def _strip_or_null(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ResumeAnalysisUpdate(BaseModel):
    """Part A of the profile card — «Мы поняли тебя так».

    PATCH-style: unset fields leave resume.analysis unchanged. Empty strings
    for target_role/specialization are coerced to null so the user can clear
    a wrong parse.
    """

    target_role: str | None = Field(default=None, max_length=TARGET_ROLE_MAX)
    specialization: str | None = Field(default=None, max_length=SPECIALIZATION_MAX)
    seniority: Seniority | None = None
    total_experience_years: float | None = Field(default=None, ge=0, le=80)
    top_skills: list[str] | None = Field(default=None, max_length=TOP_SKILLS_MAX)

    @field_validator("target_role", "specialization")
    @classmethod
    def _strip_or_null(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("top_skills")
    @classmethod
    def _clean_top_skills(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        for raw in value:
            skill = raw.strip()
            if not skill:
                continue
            if len(skill) > JOB_TITLE_MAX:
                raise ValueError(f"skill longer than {JOB_TITLE_MAX} characters")
            cleaned.append(skill)
        return cleaned


class ResumePreferenceUpdate(BaseModel):
    """Part B of the profile card — «Что ищешь».

    Same shape as UserPreferencesUpdate but duplicated here so the combined
    endpoint can validate both halves in one Pydantic model. Empty home_city
    sent as "" is stored as NULL.
    """

    preferred_work_format: WorkFormat | None = None
    relocation_mode: RelocationMode | None = None
    home_city: str | None = Field(default=None, max_length=HOME_CITY_MAX)
    preferred_titles: list[str] | None = Field(default=None, max_length=PREFERRED_TITLES_MAX)
    clear_home_city: bool = False

    @field_validator("preferred_titles")
    @classmethod
    def _clean_titles(cls, value: list[str] | None) -> list[str] | None:
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


class ResumeProfileConfirmRequest(BaseModel):
    """Combined "Подтвердить и найти работу" payload.

    Either or both halves may be present. An empty request (no fields set) is
    rejected so the endpoint never silently succeeds with nothing to save.
    """

    analysis_updates: ResumeAnalysisUpdate | None = None
    preference_updates: ResumePreferenceUpdate | None = None


class ResumeProfileConfirmResponse(BaseModel):
    resume: ResumeRead
    preferences: dict[str, Any]
