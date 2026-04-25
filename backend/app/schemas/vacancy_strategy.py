from pydantic import BaseModel


class MatchHighlight(BaseModel):
    experience_index: int
    company: str | None
    quote: str


class GapMitigation(BaseModel):
    requirement: str
    user_signal: str | None
    mitigation_text: str


class VacancyStrategyOut(BaseModel):
    resume_id: int
    vacancy_id: int
    match_highlights: list[MatchHighlight]
    gap_mitigations: list[GapMitigation]
    cover_letter_draft: str
    template_mode: bool
    prompt_version: str
    computed_at: str
