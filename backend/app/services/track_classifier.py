from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Track = Literal["match", "grow", "stretch"]

SENIORITY_ORDER = ["intern", "junior", "middle", "senior", "lead", "principal"]

# Calibrated bands. Tuned against the 20 audit_bootstrap fixtures so most
# real candidates land in match (vector >= 0.78), with grow / stretch
# requiring meaningful seniority gap. Off-track candidates get tier-based
# fallback to the closest band (no candidate gets dropped — the matcher's
# own filter does that).


@dataclass(frozen=True)
class TrackDecision:
    track: Track
    reason: str  # short human-readable: "точка: profile fits"
    seniority_diff: int  # vacancy_seniority - resume_seniority (negative if vacancy is below)
    skills_overlap: float  # 0..1


def _seniority_index(s: str | None) -> int | None:
    if not s:
        return None
    s = s.lower().strip()
    return SENIORITY_ORDER.index(s) if s in SENIORITY_ORDER else None


def _skills_overlap(resume_skills: set[str], vacancy_skills: list[str]) -> float:
    if not vacancy_skills:
        return 0.0
    lower_resume = {s.lower().strip() for s in resume_skills if isinstance(s, str)}
    lower_vacancy = {s.lower().strip() for s in vacancy_skills if isinstance(s, str)}
    if not lower_vacancy:
        return 0.0
    matched = lower_vacancy & lower_resume
    return len(matched) / len(lower_vacancy)


def classify(
    *,
    vector_score: float,
    resume_seniority: str | None,
    vacancy_seniority: str | None,
    resume_skills: set[str],
    vacancy_must_have_skills: list[str],
) -> TrackDecision:
    """Return TrackDecision. Default = match (matcher already filtered out junk)."""
    overlap = _skills_overlap(resume_skills, vacancy_must_have_skills)
    r_idx = _seniority_index(resume_seniority)
    v_idx = _seniority_index(vacancy_seniority)
    diff = (v_idx - r_idx) if (r_idx is not None and v_idx is not None) else 0

    # stretch: 2 levels above OR (1 level above AND low overlap)
    if vector_score >= 0.55 and (diff >= 2 or (diff == 1 and overlap < 0.5)):
        return TrackDecision(
            track="stretch",
            reason=f"стрейч: на {diff} уровень выше, overlap {overlap:.0%}",
            seniority_diff=diff,
            skills_overlap=overlap,
        )

    # grow: 1 level above with reasonable overlap
    if vector_score >= 0.65 and diff == 1 and overlap >= 0.5:
        return TrackDecision(
            track="grow",
            reason=f"вырост: на ступень выше, overlap {overlap:.0%}",
            seniority_diff=diff,
            skills_overlap=overlap,
        )

    # match: same level or below, overlap good
    return TrackDecision(
        track="match",
        reason=f"точка: уровень совпадает, overlap {overlap:.0%}",
        seniority_diff=diff,
        skills_overlap=overlap,
    )
