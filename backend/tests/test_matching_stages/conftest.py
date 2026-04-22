"""Shared fixtures for stage-level unit tests.

Stage tests avoid spinning up real Postgres / Qdrant. They build
small fake ``vacancy`` objects (duck-typed with the attributes the
stages read) and a hand-authored ``ResumeContext``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.matching import Candidate, MatchingState, ResumeContext


@dataclass
class FakeVacancy:
    id: int
    title: str = ""
    company: str = ""
    source: str = "hh_api"
    source_url: str = "https://hh.ru/vacancy/1"
    location: str | None = None
    raw_text: str | None = None
    status: str = "indexed"
    error_message: str | None = None


def make_context(
    *,
    resume_id: int = 1,
    resume_skills: set[str] | None = None,
    resume_roles: set[str] | None = None,
    leadership_preferred: bool = False,
    preferences: dict[str, Any] | None = None,
    preferred_titles: list[str] | None = None,
    analysis: dict[str, Any] | None = None,
) -> ResumeContext:
    return ResumeContext(
        resume_id=resume_id,
        user_id=1,
        analysis=analysis,
        query_vector=[0.0] * 8,
        resume_skills=resume_skills or set(),
        resume_roles=resume_roles or set(),
        resume_skill_phrases=[],
        resume_hard_skills=[],
        resume_phrase_aliases=set(),
        resume_total_years=None,
        leadership_preferred=leadership_preferred,
        preferences=preferences or {"preferred_work_format": "any", "relocation_mode": "home_only"},
        preferred_titles=preferred_titles or [],
        excluded_vacancy_ids=set(),
        rejected_skill_norms=set(),
    )


def make_candidate(
    vid: int,
    *,
    title: str = "",
    company: str = "",
    source_url: str = "https://hh.ru/vacancy/{vid}",
    location: str | None = None,
    raw_text: str | None = None,
    vector_score: float = 0.5,
    payload: dict[str, Any] | None = None,
) -> Candidate:
    vacancy = FakeVacancy(
        id=vid,
        title=title,
        company=company,
        source_url=source_url.format(vid=vid),
        location=location,
        raw_text=raw_text,
    )
    return Candidate(
        vacancy_id=vid,
        vacancy=vacancy,
        payload=payload or {},
        vector_score=vector_score,
    )


def make_state(context: ResumeContext, candidates: list[Candidate]) -> MatchingState:
    return MatchingState(resume_context=context, candidates=candidates)
