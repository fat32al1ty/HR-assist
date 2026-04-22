"""Phase 2.5a — CrossEncoderRerankStage unit tests.

``app.services.rerank_model.predict_pairs`` is monkey-patched so tests
never touch ``sentence_transformers`` or the real BGE weights. The
stage is still exercised end-to-end: input/output ordering, blend
formula, fallback-on-failure, and the feature flag gate.
"""

from __future__ import annotations

import math
import sys
import types
import unittest
from types import SimpleNamespace
from unittest import mock

from app.core.config import settings
from app.services.matching.stages.cross_encoder_rerank import (
    CrossEncoderRerankStage,
    _sigmoid,
)
from app.services.matching.state import (
    Candidate,
    MatchingDiagnostics,
    MatchingState,
    ResumeContext,
)


def _ctx() -> ResumeContext:
    return ResumeContext(
        resume_id=1,
        user_id=1,
        analysis={
            "target_role": "backend engineer",
            "seniority": "senior",
        },
        query_vector=[0.0],
        resume_skills=set(),
        resume_roles=set(),
        resume_skill_phrases=[],
        resume_hard_skills=["python", "postgres"],
        resume_phrase_aliases=set(),
        resume_total_years=None,
        leadership_preferred=False,
        preferences={},
        preferred_titles=[],
        excluded_vacancy_ids=set(),
        rejected_skill_norms=set(),
    )


def _cand(vac_id: int, *, hybrid: float, payload: dict | None = None) -> Candidate:
    cand = Candidate(
        vacancy_id=vac_id,
        vacancy=SimpleNamespace(id=vac_id, title=f"vacancy-{vac_id}", status="indexed"),
        payload=payload or {"summary": "backend role", "must_have_skills": ["python"]},
        vector_score=0.9,
    )
    cand.hybrid_score = hybrid
    return cand


def _install_fake_rerank_model(scores: list[float]) -> None:
    """Register a stub for app.services.rerank_model before import."""
    module = types.ModuleType("app.services.rerank_model")
    module.predict_pairs = mock.MagicMock(return_value=scores)
    sys.modules["app.services.rerank_model"] = module


def _uninstall_fake_rerank_model() -> None:
    sys.modules.pop("app.services.rerank_model", None)


class CrossEncoderRerankStageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._rerank_was_enabled = settings.rerank_enabled
        settings.rerank_enabled = True

    def tearDown(self) -> None:
        settings.rerank_enabled = self._rerank_was_enabled
        _uninstall_fake_rerank_model()

    def test_disabled_flag_is_noop(self) -> None:
        settings.rerank_enabled = False
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1, hybrid=0.7), _cand(2, hybrid=0.5)],
            diagnostics=MatchingDiagnostics(),
        )
        before = [c.hybrid_score for c in state.candidates]
        CrossEncoderRerankStage().run(state)
        self.assertEqual([c.hybrid_score for c in state.candidates], before)

    def test_rerank_flips_order_when_scores_disagree(self) -> None:
        # Pre-rerank order puts cand-1 ahead. The CE gives cand-2 a much
        # higher logit — after the blend cand-2 should overtake.
        _install_fake_rerank_model([0.0, 6.0])  # logits
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1, hybrid=0.8), _cand(2, hybrid=0.6)],
            diagnostics=MatchingDiagnostics(),
        )
        CrossEncoderRerankStage(candidate_limit=5, blend_weight=0.6).run(state)
        self.assertEqual(
            [c.vacancy_id for c in state.candidates if not c.drop_reason],
            [2, 1],
        )
        self.assertEqual(state.diagnostics.custom.get("rerank_applied"), 2)

    def test_rerank_blends_hybrid_with_sigmoid_normalisation(self) -> None:
        _install_fake_rerank_model([2.0])
        cand = _cand(1, hybrid=0.4)
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[cand],
            diagnostics=MatchingDiagnostics(),
        )
        CrossEncoderRerankStage(candidate_limit=5, blend_weight=0.6).run(state)
        expected_norm = _sigmoid(2.0)
        expected_hybrid = 0.4 * 0.4 + 0.6 * expected_norm
        self.assertAlmostEqual(cand.annotations["rerank_score"], expected_norm, places=6)
        self.assertAlmostEqual(cand.hybrid_score, expected_hybrid, places=6)

    def test_rerank_fallback_preserves_order_and_bumps_counter(self) -> None:
        module = types.ModuleType("app.services.rerank_model")

        def boom(_pairs):
            raise RuntimeError("bge unavailable")

        module.predict_pairs = boom
        sys.modules["app.services.rerank_model"] = module

        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1, hybrid=0.7), _cand(2, hybrid=0.3)],
            diagnostics=MatchingDiagnostics(),
        )
        before = [c.hybrid_score for c in state.candidates]
        CrossEncoderRerankStage().run(state)
        self.assertEqual([c.hybrid_score for c in state.candidates], before)
        self.assertEqual(state.diagnostics.custom.get("rerank_fallback"), 1)

    def test_rerank_only_touches_head_within_candidate_limit(self) -> None:
        _install_fake_rerank_model([4.0])  # one-pair batch
        tail_cand = _cand(2, hybrid=0.1)
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1, hybrid=0.9), tail_cand],
            diagnostics=MatchingDiagnostics(),
        )
        original_tail_hybrid = tail_cand.hybrid_score
        CrossEncoderRerankStage(candidate_limit=1, blend_weight=0.5).run(state)
        # Tail must pass through untouched.
        self.assertEqual(tail_cand.hybrid_score, original_tail_hybrid)
        self.assertNotIn("rerank_score", tail_cand.annotations)

    def test_sigmoid_bounds(self) -> None:
        self.assertEqual(_sigmoid(100), 1.0)
        self.assertEqual(_sigmoid(-100), 0.0)
        self.assertAlmostEqual(_sigmoid(0), 0.5, places=6)
        self.assertAlmostEqual(_sigmoid(1.0), 1.0 / (1.0 + math.exp(-1.0)), places=6)


if __name__ == "__main__":
    unittest.main()
