from __future__ import annotations

import unittest

from app.services.matching.stages.diversify import MMRDiversifyStage, _jaccard

from .conftest import make_candidate, make_context, make_state


class JaccardTest(unittest.TestCase):
    def test_identical_sets_score_one(self) -> None:
        self.assertEqual(_jaccard({"a", "b"}, {"a", "b"}), 1.0)

    def test_disjoint_sets_score_zero(self) -> None:
        self.assertEqual(_jaccard({"a"}, {"b"}), 0.0)

    def test_partial_overlap_scaled_by_union(self) -> None:
        self.assertAlmostEqual(_jaccard({"a", "b", "c"}, {"b", "c", "d"}), 2 / 4)

    def test_empty_side_is_zero(self) -> None:
        self.assertEqual(_jaccard(set(), {"x"}), 0.0)


class MMRDiversifyStageTest(unittest.TestCase):
    def _mk_cand(self, vid: int, score: float, skills: list[str]):
        cand = make_candidate(
            vid,
            title=f"V{vid}",
            payload={"must_have_skills": skills},
            vector_score=score,
        )
        cand.hybrid_score = score
        return cand

    def test_rejects_invalid_lambda(self) -> None:
        with self.assertRaises(ValueError):
            MMRDiversifyStage(lambda_=1.5)

    def test_rejects_non_positive_top_n(self) -> None:
        with self.assertRaises(ValueError):
            MMRDiversifyStage(top_n=0)

    def test_empty_candidate_list_is_no_op(self) -> None:
        state = make_state(make_context(), [])
        MMRDiversifyStage().run(state)
        self.assertEqual(state.candidates, [])

    def test_singleton_candidate_is_returned_unchanged(self) -> None:
        cand = self._mk_cand(1, 0.8, ["python"])
        state = make_state(make_context(), [cand])
        MMRDiversifyStage().run(state)
        self.assertEqual([c.vacancy_id for c in state.candidates], [1])

    def test_diversifies_near_duplicate_at_top(self) -> None:
        # Two near-identical Python roles and one Go role.
        # Scores: A=0.90, B=0.89, C=0.70.
        # With vector-only ordering MMR would pick A, B, C; with diversity
        # it picks A, then prefers C over B because B's Jaccard with A is
        # high (same skill set).
        cand_a = self._mk_cand(1, 0.90, ["python", "django", "postgres"])
        cand_b = self._mk_cand(2, 0.89, ["python", "django", "postgres"])
        cand_c = self._mk_cand(3, 0.70, ["go", "kubernetes", "grpc"])
        state = make_state(make_context(), [cand_a, cand_b, cand_c])
        MMRDiversifyStage(lambda_=0.5, top_n=3).run(state)
        order = [c.vacancy_id for c in state.candidates]
        self.assertEqual(order[0], 1, "top scorer always wins the first slot")
        self.assertEqual(
            order[1],
            3,
            "Go role should jump Python clone because of diversity bonus",
        )
        self.assertEqual(order[2], 2)

    def test_top_n_boundary_leaves_tail_in_place(self) -> None:
        cands = [self._mk_cand(i + 1, 0.9 - 0.1 * i, [f"skill{i}"]) for i in range(5)]
        state = make_state(make_context(), cands)
        MMRDiversifyStage(lambda_=0.7, top_n=3).run(state)
        # Only the first 3 may be reordered; the tail (ids 4,5) stays put.
        tail = [c.vacancy_id for c in state.candidates[3:]]
        self.assertEqual(tail, [4, 5])


if __name__ == "__main__":
    unittest.main()
