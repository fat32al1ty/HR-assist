from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ApplicationStatus = Literal[
    "draft",
    "applied",
    "viewed",
    "replied",
    "rejected",
    "interview",
    "offer",
    "declined",
]

NOTES_MAX = 2000
COVER_LETTER_MAX = 6000
TITLE_MAX = 512
URL_MAX = 2048
COMPANY_MAX = 255


class ApplicationRead(BaseModel):
    id: int
    vacancy_id: int | None
    status: ApplicationStatus
    source_url: str
    vacancy_title: str
    vacancy_company: str | None
    notes: str | None
    cover_letter_text: str | None
    applied_at: datetime | None
    last_status_change_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationCreateRequest(BaseModel):
    """Create a new application row.

    `vacancy_id` is optional so a user can track a hand-entered listing
    (e.g. pasted hh.ru link not in our index). When `vacancy_id` is present
    and the vacancy exists, title/company/source_url are auto-filled from
    the vacancy record — the caller-provided values act as fallback only.
    """

    vacancy_id: int | None = None
    source_url: str | None = Field(default=None, max_length=URL_MAX)
    vacancy_title: str | None = Field(default=None, max_length=TITLE_MAX)
    vacancy_company: str | None = Field(default=None, max_length=COMPANY_MAX)
    notes: str | None = Field(default=None, max_length=NOTES_MAX)
    status: ApplicationStatus = "draft"

    @field_validator("source_url", "vacancy_title", "vacancy_company", "notes")
    @classmethod
    def _strip_or_null(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ApplicationUpdateRequest(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX)
    cover_letter_text: str | None = Field(default=None, max_length=COVER_LETTER_MAX)
    clear_notes: bool = False
    clear_cover_letter: bool = False

    @field_validator("notes", "cover_letter_text")
    @classmethod
    def _strip_or_null(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
