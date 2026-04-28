"""B7 — Extract discriminative negative-signal terms from disliked vacancies.

get_negative_term_set() surfaces tokens that frequently appear in the user's
recent disliked vacancies but are absent from their resume hard_skills.  The
matcher's scoring stage uses these as a soft penalty (B8) without ever
hard-dropping a vacancy.
"""

from __future__ import annotations

import time
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.models.vacancy_profile import VacancyProfile

# In-process cache: (user_id, resume_id) -> (expires_at, result_set)
_cache: dict[tuple[int, int], tuple[float, set[str]]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _skill_tokens(profile: dict) -> list[str]:
    """Flatten must_have_skills + nice_to_have_skills into a lowercased token list."""
    tokens: list[str] = []
    for key in ("must_have_skills", "nice_to_have_skills"):
        for item in profile.get(key) or []:
            if isinstance(item, str) and item.strip():
                tokens.append(item.strip().lower())
    return tokens


def get_negative_term_set(
    db: Session,
    *,
    user_id: int,
    resume_id: int,
    limit: int = 30,
) -> set[str]:
    """Return tokens that frequently appear in this user's recent (<=30d)
    disliked vacancies but NOT in their resume hard_skills.  Used as a soft
    signal — vacancies containing these tokens get a small score deduction.

    Results are cached in-process for 5 minutes per (user_id, resume_id) pair.
    """
    cache_key = (user_id, resume_id)
    now = time.monotonic()
    cached = _cache.get(cache_key)
    if cached is not None and now < cached[0]:
        return cached[1]

    result = _compute_negative_term_set(db, user_id=user_id, resume_id=resume_id, limit=limit)
    _cache[cache_key] = (now + _CACHE_TTL_SECONDS, result)
    return result


def _compute_negative_term_set(
    db: Session,
    *,
    user_id: int,
    resume_id: int,
    limit: int,
) -> set[str]:
    from datetime import UTC, datetime, timedelta

    from app.repositories.resumes import get_resume_for_user

    cutoff = datetime.now(UTC) - timedelta(days=30)

    disliked_ids: list[int] = list(
        db.scalars(
            select(UserVacancyFeedback.vacancy_id)
            .where(
                UserVacancyFeedback.user_id == user_id,
                UserVacancyFeedback.resume_id == resume_id,
                UserVacancyFeedback.disliked.is_(True),
                UserVacancyFeedback.updated_at >= cutoff,
            )
            .order_by(UserVacancyFeedback.updated_at.desc())
            .limit(30)
        ).all()
    )

    if not disliked_ids:
        return set()

    profiles = db.scalars(
        select(VacancyProfile).where(VacancyProfile.vacancy_id.in_(disliked_ids))
    ).all()

    if not profiles:
        return set()

    freq: Counter[str] = Counter()
    for vp in profiles:
        if not isinstance(vp.profile, dict):
            continue
        for token in _skill_tokens(vp.profile):
            freq[token] += 1

    resume = get_resume_for_user(db, resume_id=resume_id, user_id=user_id)
    resume_hard_lower: set[str] = set()
    if resume is not None and isinstance(resume.analysis, dict):
        for skill in resume.analysis.get("hard_skills") or []:
            if isinstance(skill, str) and skill.strip():
                resume_hard_lower.add(skill.strip().lower())

    result: set[str] = set()
    for token, count in freq.most_common():
        if count < 2:
            break
        if token not in resume_hard_lower:
            result.add(token)
        if len(result) >= limit:
            break

    return result
