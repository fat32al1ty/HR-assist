"""Hard-filter stage — cheap url / title / stack / preference drops.

Applies the substring / token rules that knock a candidate out before
anything expensive runs. The sub-filters are deliberately kept in a
fixed order; earlier ones short-circuit cheaper than later ones.

Archive detection additionally mutates DB + Qdrant state: once we've
detected an archived page at match time we mark the row ``filtered``
and evict the embedding so the next recall call does not spend
retrieval K on it. That side effect is the reason this stage holds
references to ``db`` + ``vector_store``.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..state import MatchingState
from .base import BaseStage

logger = logging.getLogger(__name__)


class HardFilterStage(BaseStage):
    """Drop candidates that shouldn't even enter the scoring bracket."""

    name = "hard_filter"

    def __init__(self, *, db: Session, vector_store):
        self._db = db
        self._vector_store = vector_store

    def run(self, state: MatchingState) -> MatchingState:
        from app.services.matching_service import (
            _hard_filter_drop_reason,
            _has_sufficient_skill_overlap,
            _host_allowed_for_matching,
            _looks_archived_vacancy_strict,
            _looks_business_monitoring_role,
            _looks_hard_non_it_role,
            _looks_like_listing_page,
            _looks_non_vacancy_page,
            _looks_unlikely_stack,
        )

        ctx = state.resume_context
        diag = state.diagnostics
        for cand in state.candidates:
            vacancy = cand.vacancy
            if not _host_allowed_for_matching(vacancy.source_url):
                cand.drop_reason = "host_not_allowed"
                diag.drop_host_not_allowed += 1
                continue
            if _looks_non_vacancy_page(vacancy.source_url):
                cand.drop_reason = "non_vacancy_page"
                diag.drop_non_vacancy_page += 1
                continue
            if _looks_archived_vacancy_strict(vacancy.source_url, vacancy.title, vacancy.raw_text):
                self._mark_archived(vacancy)
                cand.drop_reason = "archived"
                diag.drop_archived += 1
                continue
            if _looks_like_listing_page(vacancy.source_url, vacancy.title):
                cand.drop_reason = "listing_page"
                diag.drop_listing_page += 1
                continue
            if _looks_unlikely_stack(vacancy.title, ctx.resume_skills):
                cand.drop_reason = "unlikely_stack"
                diag.drop_unlikely_stack += 1
                continue
            if _looks_business_monitoring_role(vacancy.title or "", ctx.resume_skills):
                cand.drop_reason = "business_role"
                diag.drop_business_role += 1
                continue
            if _looks_hard_non_it_role(vacancy.title or "", cand.payload, vacancy.raw_text):
                cand.drop_reason = "hard_non_it"
                diag.drop_hard_non_it += 1
                continue
            drop_reason = _hard_filter_drop_reason(
                vacancy_profile=cand.payload,
                vacancy_location=vacancy.location,
                prefs=ctx.preferences,
            )
            if drop_reason == "work_format":
                cand.drop_reason = "work_format"
                diag.drop_work_format += 1
                continue
            if drop_reason == "geo":
                cand.drop_reason = "geo"
                diag.drop_geo += 1
                continue
            if not _has_sufficient_skill_overlap(
                ctx.resume_skills, ctx.resume_hard_skills, cand.payload
            ):
                cand.drop_reason = "no_skill_overlap"
                diag.drop_no_skill_overlap += 1
                continue
        return state

    def _mark_archived(self, vacancy) -> None:
        """Persist archive status + evict from Qdrant so next run skips the row."""
        try:
            vacancy.status = "filtered"
            vacancy.error_message = "archived detected at match time"
            self._db.add(vacancy)
            self._db.commit()
            self._vector_store.delete_vacancy_profile(vacancy_id=vacancy.id)
        except Exception:
            self._db.rollback()
