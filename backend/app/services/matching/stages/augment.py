"""Gap-insight augmentation stage.

Runs ``_augment_profile_with_gap_insights`` per candidate and stores
the enriched profile in ``cand.augmented_profile``. Shared embedding
cache + budget sit on ``state.scratch`` so we don't duplicate OpenAI
calls across two candidates asking about the same requirement.

Kept as its own stage so the expensive embedding calls are
concentrated in one place — easier to cap, log, or swap out (Phase
2.5 may take this over).
"""

from __future__ import annotations

from ..state import MatchingState
from .base import BaseStage


class AugmentStage(BaseStage):
    name = "augment"

    def run(self, state: MatchingState) -> MatchingState:
        from app.services.matching_service import (
            SEMANTIC_GAP_MAX_EMBED_CALLS,
            _augment_profile_with_gap_insights,
        )

        ctx = state.resume_context
        resume_phrase_vectors = state.scratch.setdefault("resume_phrase_vectors", {})
        embedding_cache = state.scratch.setdefault("embedding_cache", {})
        embedding_budget = state.scratch.setdefault(
            "embedding_budget", {"calls_left": SEMANTIC_GAP_MAX_EMBED_CALLS}
        )
        for cand in state.candidates:
            cand.augmented_profile = _augment_profile_with_gap_insights(
                cand.payload,
                ctx.resume_skills,
                resume_hard_skills=ctx.resume_hard_skills,
                resume_skill_phrases=ctx.resume_skill_phrases,
                resume_phrase_aliases=ctx.resume_phrase_aliases,
                resume_phrase_vectors=resume_phrase_vectors,
                embedding_cache=embedding_cache,
                embedding_budget=embedding_budget,
                resume_total_experience_years=ctx.resume_total_years,
                vacancy_id=cand.vacancy.id,
                rejected_skill_norms=ctx.rejected_skill_norms,
            )
        return state
