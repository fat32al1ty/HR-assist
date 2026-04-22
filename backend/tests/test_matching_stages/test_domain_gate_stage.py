from __future__ import annotations

import unittest

from app.services.matching import run_pipeline
from app.services.matching.stages.domain_gate import DomainGateStage

from .conftest import make_candidate, make_context, make_state


class DomainGateStageTest(unittest.TestCase):
    def _mk(self, *, resume_domains: list[str], vacancy_domains: list[str], vector_score: float):
        # _has_domain_compatibility reads resume_analysis["domains"] — match
        # that contract rather than inventing a target_role shape.
        ctx = make_context(analysis={"domains": resume_domains})
        cand = make_candidate(
            1,
            title="Role",
            payload={"domains": vacancy_domains},
            vector_score=vector_score,
        )
        return make_state(ctx, [cand])

    def test_compatible_keeps_candidate_and_annotates_true(self) -> None:
        # IT-flagged on both sides — step 3 of _has_domain_compatibility returns True.
        state = self._mk(
            resume_domains=["software"], vacancy_domains=["software"], vector_score=0.5
        )
        DomainGateStage().run(state)
        self.assertFalse(state.candidates[0].drop_reason)
        self.assertIs(state.candidates[0].annotations["domain_compatible"], True)

    def test_incompatible_low_vector_score_is_hard_dropped(self) -> None:
        # Resume = software (IT), vacancy = строительство (NON_IT) — step 4 returns False.
        state = self._mk(
            resume_domains=["software"],
            vacancy_domains=["строительство"],
            vector_score=0.60,
        )
        run_pipeline(state, [DomainGateStage()])
        # Pipeline prunes dropped candidates between stages.
        self.assertEqual(state.candidates, [])

    def test_incompatible_but_high_vector_score_survives_with_soft_flag(self) -> None:
        state = self._mk(
            resume_domains=["software"],
            vacancy_domains=["строительство"],
            vector_score=0.95,
        )
        DomainGateStage().run(state)
        surviving = state.candidates[0]
        self.assertFalse(surviving.drop_reason)
        self.assertIs(surviving.annotations["domain_compatible"], False)
        # Diagnostics counts the mismatch even when the soft path keeps it.
        self.assertEqual(state.diagnostics.drop_domain_mismatch, 1)


if __name__ == "__main__":
    unittest.main()
