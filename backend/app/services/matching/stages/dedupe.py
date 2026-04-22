"""Exact ``(title, company)`` dedupe.

A tiny stage that knocks out re-postings before MMR runs. MMR will
also enforce diversity, but it's a soft pressure — for identical
``(title, company)`` pairs we want a hard drop so the second copy
never even competes for a slot.
"""

from __future__ import annotations

from ..state import MatchingState
from .base import BaseStage


class DedupeStage(BaseStage):
    name = "dedupe"

    def run(self, state: MatchingState) -> MatchingState:
        seen: set[str] = set()
        for cand in state.candidates:
            vacancy = cand.vacancy
            key = (
                f"{(vacancy.title or '').strip().lower()}::"
                f"{(vacancy.company or '').strip().lower()}"
            )
            if key in seen:
                cand.drop_reason = "dedupe"
                state.diagnostics.drop_dedupe += 1
            else:
                seen.add(key)
        return state
