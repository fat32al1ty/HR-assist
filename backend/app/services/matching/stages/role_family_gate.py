"""Role-family compatibility gate (Phase 2.4b).

Runs after ``HardFilterStage`` and before ``DomainGateStage``. Two
behaviours:

1. **Hard-drop:** a resume whose role is classified technical
   (``role_is_technical=True``) against a vacancy classified
   non-technical is almost always a false positive — regardless of
   domain overlap. The technical/non-technical split crosses ESCO
   ISCO major groups and the vector space cannot distinguish them
   reliably. Drop the candidate outright.

2. **Soft penalty:** within the technical-to-technical or
   non-technical-to-non-technical side, annotate a family-distance
   the scoring stage multiplies into ``hybrid_score`` via
   ``ROLE_FAMILY_MISMATCH_PENALTY``.

Missing fields (null ``role_family``, null ``role_is_technical``) do
nothing — same-as-before behaviour keeps legacy vacancies that haven't
been re-analysed yet from being silently hard-dropped.
"""

from __future__ import annotations

from ..role_family import family_distance
from ..state import MatchingState
from .base import BaseStage


class RoleFamilyGateStage(BaseStage):
    name = "role_family_gate"

    def run(self, state: MatchingState) -> MatchingState:
        analysis = state.resume_context.analysis or {}
        resume_family = analysis.get("role_family")
        resume_is_technical = analysis.get("role_is_technical")

        for cand in state.candidates:
            if cand.drop_reason:
                continue
            payload = cand.payload
            vac_family = payload.get("role_family")
            vac_is_technical = payload.get("role_is_technical")

            if resume_is_technical is True and vac_is_technical is False:
                cand.drop_reason = "role_family_non_technical"
                state.diagnostics.custom["drop_role_family_non_technical"] = (
                    state.diagnostics.custom.get("drop_role_family_non_technical", 0) + 1
                )
                continue

            distance = family_distance(resume_family, vac_family)
            cand.annotations["role_family_distance"] = distance
            if distance >= 0.75:
                state.diagnostics.custom["role_family_mismatch"] = (
                    state.diagnostics.custom.get("role_family_mismatch", 0) + 1
                )
        return state
