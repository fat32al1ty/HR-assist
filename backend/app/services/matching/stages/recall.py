"""Recall stage — query Qdrant for top-K candidates for this resume.

Reads the (blended) resume vector off the vector store, searches
vacancy profiles, fetches the ORM ``Vacancy`` row for each hit, and
emits a ``Candidate`` per surviving row. No scoring, no filtering —
just "here are the vacancies worth looking at."

Only sanity-filters applied here are the cheapest: rows marked
non-indexed, the wrong source (HH only), and rows the user has
already liked / disliked (opt-out of the pool).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.vacancies import get_vacancy_by_id

from ..state import Candidate, MatchingState
from .base import BaseStage


class VectorRecallStage(BaseStage):
    """Pull top-K candidates from Qdrant, hydrate with ORM rows."""

    name = "recall"

    def __init__(self, *, db: Session, vector_store, limit: int):
        self._db = db
        self._vector_store = vector_store
        self._limit = limit

    def run(self, state: MatchingState) -> MatchingState:
        from app.services.matching_service import PRIMARY_VACANCY_SOURCE

        ctx = state.resume_context
        found = self._vector_store.search_vacancy_profiles(
            query_vector=ctx.query_vector, limit=self._limit
        )
        state.diagnostics.recall_count = len(found)

        for vacancy_id, score, payload in found:
            if vacancy_id in ctx.excluded_vacancy_ids:
                continue
            if isinstance(payload, dict) and "is_vacancy" in payload:
                if payload.get("is_vacancy") is not True:
                    continue
            vacancy = get_vacancy_by_id(self._db, vacancy_id=vacancy_id)
            if vacancy is None or vacancy.status != "indexed":
                continue
            if (vacancy.source or "").strip().lower() != PRIMARY_VACANCY_SOURCE:
                continue
            state.candidates.append(
                Candidate(
                    vacancy_id=vacancy.id,
                    vacancy=vacancy,
                    payload=payload if isinstance(payload, dict) else {},
                    vector_score=float(score),
                )
            )
        return state
