from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

# Length caps for job-preference fields. Phase 2.0 data model: every
# user-supplied string must be bounded or it becomes a blow-up vector.
HOME_CITY_MAX = 120
JOB_TITLE_MAX = 100
PREFERRED_TITLES_MAX = 10
DOMAIN_MAX = 64
PREFERRED_DOMAINS_MAX = 3

WorkFormat = Literal["remote", "hybrid", "office", "any"]
RelocationMode = Literal["home_only", "any_city"]

_NOISE_PREFERRED_TITLE_TOKENS: frozenset[str] = frozenset(
    {
        "product",
        "manager",
        "lead",
        "head",
        "director",
        "specialist",
        "engineer",
        "developer",
        "analyst",
    }
)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    is_active: bool
    email_verified: bool
    created_at: datetime
    preferred_work_format: WorkFormat
    relocation_mode: RelocationMode
    home_city: str | None
    preferred_titles: list[str]
    preferred_domains: list[str]
    expected_salary_min: int | None = None
    expected_salary_max: int | None = None
    expected_salary_currency: str = "RUB"
    is_admin: bool = False

    model_config = {"from_attributes": True}


class UserPreferencesUpdate(BaseModel):
    """Partial update: any subset of the job-preference fields.

    Unset fields are left unchanged. ``home_city`` may be cleared by
    sending an empty string — stored as NULL. ``expected_salary_min`` /
    ``expected_salary_max`` accept 0 to clear the stored value.
    """

    preferred_work_format: WorkFormat | None = None
    relocation_mode: RelocationMode | None = None
    home_city: str | None = Field(default=None, max_length=HOME_CITY_MAX)
    preferred_titles: list[str] | None = Field(default=None, max_length=PREFERRED_TITLES_MAX)
    preferred_domains: list[str] | None = Field(default=None, max_length=PREFERRED_DOMAINS_MAX)
    expected_salary_min: int | None = Field(default=None, ge=0, le=10_000_000)
    expected_salary_max: int | None = Field(default=None, ge=0, le=10_000_000)
    expected_salary_currency: str | None = Field(default=None, min_length=3, max_length=3)

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
            if len(title) < 4:
                continue
            if title.lower() in _NOISE_PREFERRED_TITLE_TOKENS:
                continue
            if len(title) > JOB_TITLE_MAX:
                raise ValueError(f"title longer than {JOB_TITLE_MAX} characters")
            cleaned.append(title)
        return cleaned

    @field_validator("preferred_domains")
    @classmethod
    def _validate_domains(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        for raw in value:
            domain = raw.strip()
            if not domain:
                continue
            if len(domain) > DOMAIN_MAX:
                raise ValueError(f"domain longer than {DOMAIN_MAX} characters")
            cleaned.append(domain)
        return cleaned

    @field_validator("home_city")
    @classmethod
    def _normalize_city(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
