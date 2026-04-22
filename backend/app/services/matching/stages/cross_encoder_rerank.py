"""Cross-encoder rerank stage (Phase 2.5a).

Runs after ``DedupeStage``, before ``MMRDiversifyStage``. Takes the top
``candidate_limit`` candidates by ``hybrid_score``, rebuilds a short
query + per-vacancy document, calls the reranker, and blends the
cross-encoder score back into ``hybrid_score`` using ``blend_weight``.

Disabled by default — flip ``settings.rerank_enabled`` to turn on.
When disabled, the stage is a no-op (no model load, no latency).
"""

from __future__ import annotations

import logging

from app.core.config import settings

from ..state import MatchingState
from .base import BaseStage

logger = logging.getLogger(__name__)


class CrossEncoderRerankStage(BaseStage):
    name = "cross_encoder_rerank"

    def __init__(
        self,
        *,
        candidate_limit: int | None = None,
        blend_weight: float | None = None,
    ) -> None:
        self._candidate_limit = candidate_limit or settings.rerank_candidate_limit
        self._blend_weight = (
            blend_weight if blend_weight is not None else settings.rerank_blend_weight
        )

    def run(self, state: MatchingState) -> MatchingState:
        if not settings.rerank_enabled:
            return state

        surviving = [c for c in state.candidates if not c.drop_reason]
        if not surviving:
            return state

        surviving.sort(key=lambda c: c.hybrid_score, reverse=True)
        head = surviving[: self._candidate_limit]
        tail = surviving[self._candidate_limit :]

        query = _build_query(state)
        pairs = [(query, _build_document(cand)) for cand in head]

        try:
            from app.services.rerank_model import predict_pairs  # noqa: PLC0415

            scores = predict_pairs(pairs)
        except Exception as error:  # noqa: BLE001
            # Reranker load or inference failure must not tank the
            # request — we fall back to the pre-rerank ordering.
            logger.exception("cross-encoder rerank failed, falling back: %s", error)
            state.diagnostics.custom["rerank_fallback"] = (
                state.diagnostics.custom.get("rerank_fallback", 0) + 1
            )
            return state

        for cand, raw_score in zip(head, scores, strict=True):
            normalised = _sigmoid(raw_score)
            cand.annotations["rerank_score"] = normalised
            cand.hybrid_score = (
                1.0 - self._blend_weight
            ) * cand.hybrid_score + self._blend_weight * normalised

        head.sort(key=lambda c: c.hybrid_score, reverse=True)
        surviving_after = head + tail
        dropped = [c for c in state.candidates if c.drop_reason]
        state.candidates = surviving_after + dropped
        state.diagnostics.custom["rerank_applied"] = len(head)
        return state


def _build_query(state: MatchingState) -> str:
    ctx = state.resume_context
    analysis = ctx.analysis or {}
    role = analysis.get("target_role") or analysis.get("specialization") or ""
    seniority = analysis.get("seniority") or ""
    top_skills = ", ".join((ctx.resume_hard_skills or [])[:8])
    parts = [p for p in (role, seniority, top_skills) if p]
    return " | ".join(parts) if parts else (role or "vacancy match")


def _build_document(cand) -> str:
    payload = cand.payload or {}
    vacancy = cand.vacancy
    title = getattr(vacancy, "title", "") or payload.get("role") or ""
    summary = payload.get("summary") or ""
    must = ", ".join((payload.get("must_have_skills") or [])[:12])
    parts = [p for p in (title, must, summary) if p]
    return "\n".join(parts)[:1800]


def _sigmoid(x: float) -> float:
    # BGE reranker emits logits, not bounded probabilities. Sigmoid
    # bounds them into [0, 1] so the blend weight behaves linearly.
    import math  # noqa: PLC0415

    if x >= 50:
        return 1.0
    if x <= -50:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))
