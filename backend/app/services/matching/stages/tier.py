"""Strong / maybe tier split.

The monolith used to do two pass-throughs over the ranked list to
split strong (≥ strict threshold) from maybe (≥ relaxed but below
strict). This stage assigns ``cand.tier`` in a single pass; the
wrapper slices strong and maybe lists off the sorted survivors.

Candidates below the ``MAYBE`` threshold are NOT dropped here — the
wrapper's last-resort pass uses them to fill when both strong and
maybe buckets came up empty.
"""

from __future__ import annotations

from ..state import MatchingState
from .base import BaseStage


class TierStage(BaseStage):
    name = "tier"

    def run(self, state: MatchingState) -> MatchingState:
        from app.services.matching_service import (
            MAYBE_MATCH_THRESHOLD,
            RELAXED_MIN_RELEVANCE_SCORE,
            STRONG_MATCH_THRESHOLD,
        )

        for cand in state.candidates:
            score = cand.hybrid_score
            if score >= STRONG_MATCH_THRESHOLD:
                cand.tier = "strong"
            elif score >= MAYBE_MATCH_THRESHOLD:
                cand.tier = "maybe"
            elif score >= RELAXED_MIN_RELEVANCE_SCORE:
                cand.tier = "relaxed"
            else:
                cand.tier = "below"
        return state
