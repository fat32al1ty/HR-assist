"""Phase 2.7 — SalaryFitStage unit tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.services.matching.stages.salary_fit import SalaryFitStage
from app.services.matching.state import (
    Candidate,
    MatchingDiagnostics,
    MatchingState,
    ResumeContext,
)


def _context(prefs: dict) -> ResumeContext:
    return ResumeContext(
        resume_id=1,
        user_id=1,
        analysis=None,
        query_vector=[],
        resume_skills=set(),
        resume_roles=set(),
        resume_skill_phrases=[],
        resume_hard_skills=[],
        resume_phrase_aliases=set(),
        resume_total_years=None,
        leadership_preferred=False,
        preferences=prefs,
        preferred_titles=[],
        excluded_vacancy_ids=set(),
        rejected_skill_norms=set(),
    )


def _candidate(*, vacancy_id: int, score: float, profile_attrs: dict) -> Candidate:
    profile = SimpleNamespace(**profile_attrs)
    vacancy = SimpleNamespace(id=vacancy_id, profile=profile)
    return Candidate(
        vacancy_id=vacancy_id,
        vacancy=vacancy,
        payload={},
        vector_score=score,
        hybrid_score=score,
    )


class SalaryFitStageTest(unittest.TestCase):
    def test_penalises_below_expectation_and_annotates(self) -> None:
        state = MatchingState(
            resume_context=_context(
                {
                    "expected_salary_min": 200_000,
                    "expected_salary_max": 300_000,
                    "expected_salary_currency": "RUB",
                }
            ),
            candidates=[
                _candidate(
                    vacancy_id=1,
                    score=0.8,
                    profile_attrs={
                        "salary_min": 80_000,
                        "salary_max": 100_000,
                        "salary_currency": "RUB",
                        "predicted_salary_p25": None,
                        "predicted_salary_p50": None,
                        "predicted_salary_p75": None,
                    },
                )
            ],
            diagnostics=MatchingDiagnostics(),
        )
        SalaryFitStage().run(state)
        cand = state.candidates[0]
        self.assertEqual(cand.annotations["salary_fit"], "below")
        self.assertEqual(cand.annotations["salary_source"], "stated")
        self.assertLess(cand.hybrid_score, 0.8)

    def test_no_expectation_gives_unknown_no_penalty(self) -> None:
        state = MatchingState(
            resume_context=_context({}),
            candidates=[
                _candidate(
                    vacancy_id=1,
                    score=0.5,
                    profile_attrs={
                        "salary_min": 100_000,
                        "salary_max": 120_000,
                        "salary_currency": "RUB",
                        "predicted_salary_p25": None,
                        "predicted_salary_p50": None,
                        "predicted_salary_p75": None,
                    },
                )
            ],
        )
        SalaryFitStage().run(state)
        cand = state.candidates[0]
        self.assertEqual(cand.annotations["salary_fit"], "unknown")
        self.assertEqual(cand.hybrid_score, 0.5)

    def test_uses_predicted_when_stated_missing(self) -> None:
        state = MatchingState(
            resume_context=_context(
                {
                    "expected_salary_min": 200_000,
                    "expected_salary_max": 300_000,
                    "expected_salary_currency": "RUB",
                }
            ),
            candidates=[
                _candidate(
                    vacancy_id=1,
                    score=0.7,
                    profile_attrs={
                        "salary_min": None,
                        "salary_max": None,
                        "salary_currency": None,
                        "predicted_salary_p25": 180_000,
                        "predicted_salary_p50": 220_000,
                        "predicted_salary_p75": 260_000,
                    },
                )
            ],
        )
        SalaryFitStage().run(state)
        cand = state.candidates[0]
        self.assertEqual(cand.annotations["salary_fit"], "match")
        self.assertEqual(cand.annotations["salary_source"], "predicted")
        self.assertEqual(cand.annotations["salary_min"], 180_000)
        self.assertEqual(cand.annotations["salary_max"], 260_000)

    def test_currency_mismatch_is_unknown(self) -> None:
        state = MatchingState(
            resume_context=_context(
                {
                    "expected_salary_min": 200_000,
                    "expected_salary_max": 300_000,
                    "expected_salary_currency": "RUB",
                }
            ),
            candidates=[
                _candidate(
                    vacancy_id=1,
                    score=0.6,
                    profile_attrs={
                        "salary_min": 5_000,
                        "salary_max": 6_000,
                        "salary_currency": "USD",
                        "predicted_salary_p25": None,
                        "predicted_salary_p50": None,
                        "predicted_salary_p75": None,
                    },
                )
            ],
        )
        SalaryFitStage().run(state)
        cand = state.candidates[0]
        self.assertEqual(cand.annotations["salary_fit"], "unknown")
        self.assertEqual(cand.hybrid_score, 0.6)


if __name__ == "__main__":
    unittest.main()
