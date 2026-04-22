"""Smoke tests for the matching pipeline foundation (Phase 2.3).

Exercises the raw dataclasses + ``run_pipeline`` — no real matcher yet.
When stages start landing, their own test files in
``backend/tests/test_matching_stages/`` cover behavior; this file only
guards the plumbing: pruning between stages, diagnostics export,
``surviving()`` semantics.
"""

from __future__ import annotations

import unittest
from typing import Any

from app.services.matching import (
    BaseStage,
    Candidate,
    MatchingDiagnostics,
    MatchingState,
    ResumeContext,
    run_pipeline,
)


def _ctx() -> ResumeContext:
    return ResumeContext(
        resume_id=1,
        user_id=1,
        analysis=None,
        query_vector=[0.0] * 8,
        resume_skills=set(),
        resume_roles=set(),
        resume_skill_phrases=[],
        resume_hard_skills=[],
        resume_phrase_aliases=set(),
        resume_total_years=None,
        leadership_preferred=False,
        preferences={},
        preferred_titles=[],
        excluded_vacancy_ids=set(),
        rejected_skill_norms=set(),
    )


def _cand(vid: int, score: float = 0.5) -> Candidate:
    return Candidate(
        vacancy_id=vid,
        vacancy=None,
        payload={},
        vector_score=score,
    )


class _DropEvensStage(BaseStage):
    name = "drop_evens"

    def run(self, state: MatchingState) -> MatchingState:
        for cand in state.candidates:
            if cand.vacancy_id % 2 == 0:
                cand.drop_reason = "even"
        return state


class _CountStage(BaseStage):
    name = "count"

    def __init__(self) -> None:
        self.observed: int | None = None

    def run(self, state: MatchingState) -> MatchingState:
        self.observed = len(state.candidates)
        return state


class PipelineFoundationTest(unittest.TestCase):
    def test_run_pipeline_prunes_dropped_candidates_between_stages(self) -> None:
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(i) for i in range(1, 6)],
        )
        counter = _CountStage()
        run_pipeline(state, [_DropEvensStage(), counter])
        self.assertEqual(counter.observed, 3)
        # Final state retains only the survivors too.
        self.assertEqual({c.vacancy_id for c in state.candidates}, {1, 3, 5})

    def test_surviving_helper_matches_runner_behavior(self) -> None:
        state = MatchingState(
            resume_context=_ctx(),
            candidates=[_cand(1), _cand(2)],
        )
        state.candidates[0].drop_reason = "mock"
        alive = state.surviving()
        self.assertEqual([c.vacancy_id for c in alive], [2])

    def test_diagnostics_export_preserves_legacy_metric_keys(self) -> None:
        diag = MatchingDiagnostics(
            drop_work_format=1,
            drop_geo=2,
            drop_no_skill_overlap=3,
            drop_domain_mismatch=4,
            seniority_penalty_applied=5,
            drop_archived=6,
            title_boost_applied=7,
        )
        diag.custom["hard_filter_drop_unlikely_stack"] = 9
        bucket: dict[str, Any] = {}
        diag.export_to(bucket)
        self.assertEqual(bucket["hard_filter_drop_work_format"], 1)
        self.assertEqual(bucket["hard_filter_drop_geo"], 2)
        self.assertEqual(bucket["hard_filter_drop_no_skill_overlap"], 3)
        self.assertEqual(bucket["hard_filter_drop_domain_mismatch"], 4)
        self.assertEqual(bucket["seniority_penalty_applied"], 5)
        self.assertEqual(bucket["archived_at_match_time"], 6)
        self.assertEqual(bucket["title_boost_applied"], 7)
        self.assertEqual(bucket["hard_filter_drop_unlikely_stack"], 9)

    def test_diagnostics_export_is_noop_when_metrics_is_none(self) -> None:
        diag = MatchingDiagnostics(drop_work_format=1)
        diag.export_to(None)  # must not raise


if __name__ == "__main__":
    unittest.main()
