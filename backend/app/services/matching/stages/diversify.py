"""MMR diversification stage.

Classic Maximal Marginal Relevance: iteratively pick the candidate
that maximizes ``λ·score(i) - (1-λ)·max_j_in_selected sim(i, j)``.

Similarity between two candidates is Jaccard overlap of their skill
token sets. We use the bag-of-tokens proxy (not vacancy embeddings)
because:

- it's already computed in ``ScoringStage`` — free to reuse;
- it doesn't require a second Qdrant round-trip to fetch vectors,
  keeping the offline eval harness free;
- on observation it correlates strongly with "two postings for the
  same role at different companies" — the duplication pattern we
  actually want to break up.

λ is configurable — 0.7 (relevance-dominant) is the default; tune on
the eval harness. A ``top_n`` larger than ``limit`` gives MMR room
to swap out a high-score-but-redundant item for a lower-score item
that adds diversity. The stage reorders ``state.candidates`` in place
so downstream tier slicing sees the MMR-picked order first.
"""

from __future__ import annotations

from ..state import MatchingState
from .base import BaseStage


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    inter = len(left & right)
    if inter == 0:
        return 0.0
    return inter / len(left | right)


class MMRDiversifyStage(BaseStage):
    """Reorder candidates by MMR over a bounded top-N window."""

    name = "diversify"

    def __init__(self, *, lambda_: float = 0.7, top_n: int = 30):
        if not 0.0 <= lambda_ <= 1.0:
            raise ValueError(f"lambda must be in [0, 1], got {lambda_}")
        if top_n <= 0:
            raise ValueError(f"top_n must be positive, got {top_n}")
        self._lambda = lambda_
        self._top_n = top_n

    def run(self, state: MatchingState) -> MatchingState:
        from app.services.matching_service import _build_vacancy_skill_set

        if len(state.candidates) <= 1:
            return state

        state.candidates.sort(key=lambda c: c.hybrid_score, reverse=True)
        window = state.candidates[: self._top_n]
        tail = state.candidates[self._top_n :]

        skills: dict[int, set[str]] = {
            id(cand): _build_vacancy_skill_set(cand.payload) for cand in window
        }
        remaining = list(window)
        selected: list = []
        if remaining:
            # First pick: the top scorer — MMR reduces to score when nothing is
            # selected yet.
            first = remaining.pop(0)
            selected.append(first)

        while remaining:
            best_idx = 0
            best_val = -float("inf")
            for idx, cand in enumerate(remaining):
                cand_skills = skills[id(cand)]
                max_sim = 0.0
                for picked in selected:
                    sim = _jaccard(cand_skills, skills[id(picked)])
                    if sim > max_sim:
                        max_sim = sim
                mmr = self._lambda * cand.hybrid_score - (1.0 - self._lambda) * max_sim
                if mmr > best_val:
                    best_val = mmr
                    best_idx = idx
            selected.append(remaining.pop(best_idx))

        state.candidates = selected + tail
        return state
