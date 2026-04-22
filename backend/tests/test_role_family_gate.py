"""Phase 2.4b — RoleFamilyGateStage unit tests.

Pure-Python stage; no DB needed. Drives the gate with hand-built
``MatchingState`` and checks drop counters + per-candidate annotations.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.services.matching.role_family import family_distance
from app.services.matching.stages.role_family_gate import RoleFamilyGateStage
from app.services.matching.state import (
    Candidate,
    MatchingDiagnostics,
    MatchingState,
    ResumeContext,
)


def _ctx(*, role_family: str | None, role_is_technical: bool | None) -> ResumeContext:
    analysis: dict = {}
    if role_family is not None:
        analysis["role_family"] = role_family
    if role_is_technical is not None:
        analysis["role_is_technical"] = role_is_technical
    return ResumeContext(
        resume_id=1,
        user_id=1,
        analysis=analysis,
        query_vector=[0.0],
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


def _cand(vac_id: int, payload: dict) -> Candidate:
    return Candidate(
        vacancy_id=vac_id,
        vacancy=SimpleNamespace(id=vac_id, title="x", status="indexed"),
        payload=payload,
        vector_score=0.9,
    )


class FamilyDistanceTableTest(unittest.TestCase):
    def test_identical_families_are_zero(self) -> None:
        self.assertEqual(family_distance("software_engineering", "software_engineering"), 0.0)

    def test_same_group_is_quarter(self) -> None:
        self.assertEqual(family_distance("software_engineering", "infrastructure_devops"), 0.25)

    def test_bridge_pair_is_half(self) -> None:
        self.assertEqual(family_distance("product_management", "software_engineering"), 0.5)
        self.assertEqual(family_distance("software_engineering", "product_management"), 0.5)

    def test_cross_group_is_three_quarters(self) -> None:
        self.assertEqual(family_distance("software_engineering", "sales_bd"), 0.75)

    def test_unknown_family_is_zero(self) -> None:
        self.assertEqual(family_distance("software_engineering", "definitely-not-real"), 0.0)

    def test_null_is_zero(self) -> None:
        self.assertEqual(family_distance(None, "software_engineering"), 0.0)


class RoleFamilyGateStageTest(unittest.TestCase):
    def test_tech_resume_drops_non_tech_vacancy(self) -> None:
        state = MatchingState(
            resume_context=_ctx(role_family="software_engineering", role_is_technical=True),
            candidates=[
                _cand(
                    1,
                    {
                        "role_family": "sales_bd",
                        "role_is_technical": False,
                    },
                )
            ],
            diagnostics=MatchingDiagnostics(),
        )
        RoleFamilyGateStage().run(state)
        self.assertEqual(state.candidates[0].drop_reason, "role_family_non_technical")
        self.assertEqual(state.diagnostics.custom.get("drop_role_family_non_technical"), 1)

    def test_tech_resume_keeps_tech_vacancy_with_zero_distance(self) -> None:
        state = MatchingState(
            resume_context=_ctx(role_family="software_engineering", role_is_technical=True),
            candidates=[
                _cand(
                    1,
                    {
                        "role_family": "software_engineering",
                        "role_is_technical": True,
                    },
                )
            ],
            diagnostics=MatchingDiagnostics(),
        )
        RoleFamilyGateStage().run(state)
        self.assertEqual(state.candidates[0].drop_reason, "")
        self.assertEqual(state.candidates[0].annotations["role_family_distance"], 0.0)

    def test_cross_family_annotates_penalty_distance(self) -> None:
        state = MatchingState(
            resume_context=_ctx(role_family="data_ml", role_is_technical=True),
            candidates=[
                _cand(
                    1,
                    {
                        "role_family": "research_science",  # bridge pair
                        "role_is_technical": True,
                    },
                ),
                _cand(
                    2,
                    {
                        "role_family": "infrastructure_devops",  # same group
                        "role_is_technical": True,
                    },
                ),
            ],
            diagnostics=MatchingDiagnostics(),
        )
        RoleFamilyGateStage().run(state)
        self.assertEqual(state.candidates[0].annotations["role_family_distance"], 0.5)
        self.assertEqual(state.candidates[1].annotations["role_family_distance"], 0.25)

    def test_unknown_vacancy_classification_falls_through(self) -> None:
        # A legacy vacancy with no role_family/role_is_technical must NOT
        # be hard-dropped — we keep backwards compatibility for rows not
        # yet re-analysed.
        state = MatchingState(
            resume_context=_ctx(role_family="software_engineering", role_is_technical=True),
            candidates=[_cand(1, {})],
            diagnostics=MatchingDiagnostics(),
        )
        RoleFamilyGateStage().run(state)
        self.assertEqual(state.candidates[0].drop_reason, "")
        self.assertEqual(state.candidates[0].annotations["role_family_distance"], 0.0)

    def test_non_technical_resume_is_not_dropped_against_any(self) -> None:
        state = MatchingState(
            resume_context=_ctx(role_family="product_management", role_is_technical=False),
            candidates=[
                _cand(
                    1,
                    {
                        "role_family": "sales_bd",
                        "role_is_technical": False,
                    },
                ),
                _cand(
                    2,
                    {
                        "role_family": "software_engineering",
                        "role_is_technical": True,
                    },
                ),
            ],
            diagnostics=MatchingDiagnostics(),
        )
        RoleFamilyGateStage().run(state)
        for cand in state.candidates:
            self.assertEqual(cand.drop_reason, "")

    def test_already_dropped_candidate_is_skipped(self) -> None:
        pre_drop = _cand(
            1,
            {"role_family": "sales_bd", "role_is_technical": False},
        )
        pre_drop.drop_reason = "some_earlier_stage"
        state = MatchingState(
            resume_context=_ctx(role_family="software_engineering", role_is_technical=True),
            candidates=[pre_drop],
            diagnostics=MatchingDiagnostics(),
        )
        RoleFamilyGateStage().run(state)
        # Earlier drop reason must not be overwritten, counter not bumped.
        self.assertEqual(state.candidates[0].drop_reason, "some_earlier_stage")
        self.assertNotIn("drop_role_family_non_technical", state.diagnostics.custom)


if __name__ == "__main__":
    unittest.main()
