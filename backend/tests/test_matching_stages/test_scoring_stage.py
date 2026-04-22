from __future__ import annotations

import unittest

from app.services.matching.stages.scoring import ScoringStage

from .conftest import make_candidate, make_context, make_state


class ScoringStageTest(unittest.TestCase):
    def test_hybrid_score_blends_vector_and_overlap(self) -> None:
        from app.services.matching_service import _hybrid_score, _overlap_score

        ctx = make_context(resume_skills={"python", "django", "postgres"})
        cand = make_candidate(
            1,
            title="Python developer",
            payload={
                "must_have_skills": ["Python", "Django"],
                "tools": [],
                "matching_keywords": [],
            },
            vector_score=0.8,
        )
        cand.annotations["domain_compatible"] = True
        state = make_state(ctx, [cand])
        ScoringStage().run(state)

        expected_overlap = _overlap_score(
            ctx.resume_skills,
            {"python", "django"},  # _build_vacancy_skill_set output
        )
        expected_hybrid = _hybrid_score(0.8, expected_overlap)
        self.assertAlmostEqual(state.candidates[0].hybrid_score, expected_hybrid, places=5)
        self.assertAlmostEqual(state.candidates[0].lexical_score, expected_overlap, places=5)

    def test_domain_mismatch_penalty_applied_when_flagged(self) -> None:
        from app.services.matching_service import DOMAIN_MISMATCH_PENALTY

        ctx = make_context(resume_skills={"python"})
        cand_no_penalty = make_candidate(
            1, title="Python", payload={"must_have_skills": ["python"]}, vector_score=0.8
        )
        cand_no_penalty.annotations["domain_compatible"] = True
        cand_penalty = make_candidate(
            2, title="Python", payload={"must_have_skills": ["python"]}, vector_score=0.8
        )
        cand_penalty.annotations["domain_compatible"] = False
        state = make_state(ctx, [cand_no_penalty, cand_penalty])
        ScoringStage().run(state)
        # After sorting, no-penalty candidate is first.
        self.assertAlmostEqual(
            state.candidates[0].hybrid_score - state.candidates[1].hybrid_score,
            DOMAIN_MISMATCH_PENALTY,
            places=5,
        )

    def test_title_boost_counter_increments_for_full_boost(self) -> None:
        ctx = make_context(
            resume_skills={"python"},
            preferred_titles=["Senior Backend Engineer"],
        )
        cand = make_candidate(
            1,
            title="Senior Backend Engineer",
            payload={"must_have_skills": ["python"]},
            vector_score=0.7,
        )
        cand.annotations["domain_compatible"] = True
        state = make_state(ctx, [cand])
        ScoringStage().run(state)
        self.assertEqual(state.diagnostics.title_boost_applied, 1)

    def test_sorts_candidates_by_hybrid_desc(self) -> None:
        ctx = make_context(resume_skills={"python"})
        low = make_candidate(
            1, title="Analyst", payload={"must_have_skills": ["python"]}, vector_score=0.3
        )
        high = make_candidate(
            2, title="Analyst", payload={"must_have_skills": ["python"]}, vector_score=0.9
        )
        for c in (low, high):
            c.annotations["domain_compatible"] = True
        state = make_state(ctx, [low, high])
        ScoringStage().run(state)
        self.assertEqual([c.vacancy_id for c in state.candidates], [2, 1])


if __name__ == "__main__":
    unittest.main()
