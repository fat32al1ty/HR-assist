"""Domain-compatibility gate (Phase 2.1 soft-penalty version).

If the vacancy's declared domains don't overlap with the resume's
target domain and the vector score is below the hard-drop threshold,
kill the candidate outright. Above the threshold we let it through
but annotate ``domain_compatible=False`` so the scoring stage can
apply a soft penalty.

Soft-gated candidates do not block the pipeline; the scoring stage
reads ``cand.annotations["domain_compatible"]`` and subtracts
``DOMAIN_MISMATCH_PENALTY`` from hybrid score.
"""

from __future__ import annotations

from ..state import MatchingState
from .base import BaseStage


class DomainGateStage(BaseStage):
    name = "domain_gate"

    def run(self, state: MatchingState) -> MatchingState:
        from app.services.matching_service import (
            DOMAIN_MISMATCH_HARD_DROP_VECTOR_THRESHOLD,
            _has_domain_compatibility,
        )

        ctx = state.resume_context
        for cand in state.candidates:
            compatible = _has_domain_compatibility(ctx.analysis, cand.payload)
            cand.annotations["domain_compatible"] = compatible
            if not compatible:
                state.diagnostics.drop_domain_mismatch += 1
                if cand.vector_score < DOMAIN_MISMATCH_HARD_DROP_VECTOR_THRESHOLD:
                    cand.drop_reason = "domain_mismatch_low_vec"
        return state
