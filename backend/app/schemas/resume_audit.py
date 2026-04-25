from datetime import datetime

from pydantic import BaseModel, Field


class AltRole(BaseModel):
    role_family: str
    seniority: str | None
    confidence: float


class RoleRead(BaseModel):
    primary: dict  # {role_family, seniority, confidence}
    alt: list[AltRole] = Field(default_factory=list)


class MarketSalaryBand(BaseModel):
    p25: int
    p50: int
    p75: int
    currency: str = "RUB"
    model_version: str
    user_expectation: int | None = None
    gap_to_median_pct: float | None = None
    sample_size: int | None = None


class SkillGap(BaseModel):
    skill: str
    vacancies_with_skill_pct: float
    vacancies_count_in_segment: int
    owned: bool = False


class ResumeQualityIssue(BaseModel):
    rule_id: str
    severity: str  # "info" | "warn" | "error"
    message: str


class ResumeAuditOut(BaseModel):
    resume_id: int
    computed_at: datetime
    prompt_version: str
    role_read: RoleRead
    market_salary: MarketSalaryBand | None = None
    skill_gaps: list[SkillGap] = Field(default_factory=list)
    quality_issues: list[ResumeQualityIssue] = Field(default_factory=list)
    triggered_question_ids: list[str] = Field(default_factory=list)
    template_mode_active: bool = False
