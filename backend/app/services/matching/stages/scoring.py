"""Scoring stage — compute the final ``hybrid_score`` for each candidate.

Applies, in order, the same overlays the old monolith did:

1. ``_hybrid_score(vector_score, skill_overlap)`` — the base blend.
2. role overlap (0.05 × token overlap between resume roles and
   vacancy title).
3. ``DOMAIN_MISMATCH_PENALTY`` when ``domain_compatible=False`` (set
   by ``DomainGateStage``).
4. Leadership bonus / penalty when the resume asked for leadership.
5. Seniority mismatch penalty (±0.15).
6. Preferred-title boost (+0.05 or +0.10, capped at 1.0).

All helpers are re-used from ``matching_service`` — this stage is
pure composition, no new math.
"""

from __future__ import annotations

from ..state import MatchingState
from .base import BaseStage

_NEGATIVE_TERM_PENALTY_PER_TERM = 0.02
_NEGATIVE_TERM_PENALTY_CAP = 0.06


def _negative_term_penalty(vacancy_payload: dict | None, negative_term_set: set[str]) -> float:
    """Return a deduction [0.0, _NEGATIVE_TERM_PENALTY_CAP] based on how many
    tokens from negative_term_set appear in the vacancy's must_have_skills.

    Never drops a vacancy — soft signal only.
    """
    if not negative_term_set or not isinstance(vacancy_payload, dict):
        return 0.0
    must_have = vacancy_payload.get("must_have_skills")
    if not isinstance(must_have, list) or not must_have:
        return 0.0
    vac_tokens = {s.strip().lower() for s in must_have if isinstance(s, str) and s.strip()}
    overlap_count = len(vac_tokens & negative_term_set)
    if overlap_count == 0:
        return 0.0
    return min(_NEGATIVE_TERM_PENALTY_CAP, overlap_count * _NEGATIVE_TERM_PENALTY_PER_TERM)


class ScoringStage(BaseStage):
    name = "score"

    def run(self, state: MatchingState) -> MatchingState:
        from app.services.matching_service import (
            DOMAIN_MISMATCH_PENALTY,
            LEADERSHIP_BONUS,
            LEADERSHIP_MISSING_PENALTY,
            ROLE_FAMILY_MISMATCH_PENALTY,
            TITLE_BOOST,
            TITLE_BOOST_SCORE_CAP,
            _build_vacancy_skill_set,
            _domain_preference_boost,
            _hybrid_score,
            _overlap_score,
            _preferred_title_boost_score,
            _seniority_mismatch_penalty,
            _title_has_leadership_hint,
            _tokenize_rich_text,
        )

        ctx = state.resume_context
        diag = state.diagnostics
        for cand in state.candidates:
            vacancy = cand.vacancy
            vacancy_skills = _build_vacancy_skill_set(cand.payload)
            vacancy_title_tokens = _tokenize_rich_text(vacancy.title or "")
            overlap = _overlap_score(ctx.resume_skills, vacancy_skills)
            role_overlap = (
                _overlap_score(ctx.resume_roles, vacancy_title_tokens) if ctx.resume_roles else 0.0
            )
            hybrid = _hybrid_score(cand.vector_score, overlap) + (0.05 * role_overlap)
            if cand.annotations.get("domain_compatible") is False:
                hybrid -= DOMAIN_MISMATCH_PENALTY
            role_distance = float(cand.annotations.get("role_family_distance") or 0.0)
            if role_distance > 0.0:
                hybrid -= ROLE_FAMILY_MISMATCH_PENALTY * role_distance
            has_leadership_hint = _title_has_leadership_hint(vacancy.title or "", cand.payload)
            if ctx.leadership_preferred:
                if has_leadership_hint:
                    hybrid += LEADERSHIP_BONUS
                else:
                    hybrid -= LEADERSHIP_MISSING_PENALTY
            seniority_delta = _seniority_mismatch_penalty(ctx.analysis, cand.payload)
            if seniority_delta != 0.0:
                hybrid += seniority_delta
                diag.seniority_penalty_applied += 1
            title_boost = _preferred_title_boost_score(vacancy.title, ctx.preferred_titles)
            if title_boost > 0.0:
                hybrid = min(TITLE_BOOST_SCORE_CAP, hybrid + title_boost)
                if title_boost >= TITLE_BOOST:
                    diag.title_boost_applied += 1
            domain_boost = _domain_preference_boost(cand.payload, ctx.preferred_domains)
            if domain_boost > 0.0:
                hybrid = min(TITLE_BOOST_SCORE_CAP, hybrid + domain_boost)
                diag.domain_preference_boost_applied += 1
            neg_penalty = _negative_term_penalty(cand.payload, ctx.negative_term_set)
            if neg_penalty > 0.0:
                hybrid -= neg_penalty
                diag.negative_term_penalty_applied += 1
            cand.lexical_score = overlap
            cand.hybrid_score = hybrid
            cand.annotations["leadership_hint"] = has_leadership_hint
        state.candidates.sort(key=lambda c: c.hybrid_score, reverse=True)
        return state
