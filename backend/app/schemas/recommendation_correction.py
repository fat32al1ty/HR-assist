from typing import Literal

from pydantic import BaseModel, Field

CorrectionType = Literal["match_highlight_invalid", "gap_mitigation_invalid"]


class RecommendationCorrectionCreate(BaseModel):
    resume_id: int
    vacancy_id: int
    correction_type: CorrectionType
    subject_index: int = Field(ge=0, le=10)
    subject_text: str | None = Field(default=None, max_length=500)


class RecommendationCorrectionRead(BaseModel):
    id: int
    resume_id: int
    vacancy_id: int
    correction_type: CorrectionType
    subject_index: int
    subject_text: str | None
    created_at: str  # ISO

    model_config = {"from_attributes": True}
