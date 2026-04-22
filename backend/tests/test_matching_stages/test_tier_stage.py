from __future__ import annotations

import unittest

from app.services.matching.stages.tier import TierStage

from .conftest import make_candidate, make_context, make_state


class TierStageTest(unittest.TestCase):
    def _stage_with_scores(self, scores: list[float]):
        ctx = make_context()
        cands = [make_candidate(i + 1) for i in range(len(scores))]
        for cand, score in zip(cands, scores, strict=True):
            cand.hybrid_score = score
        state = make_state(ctx, cands)
        TierStage().run(state)
        return [c.tier for c in state.candidates]

    def test_score_above_strong_threshold_is_strong(self) -> None:
        from app.services.matching_service import STRONG_MATCH_THRESHOLD

        tiers = self._stage_with_scores([STRONG_MATCH_THRESHOLD + 0.10])
        self.assertEqual(tiers, ["strong"])

    def test_score_between_maybe_and_strong_is_maybe(self) -> None:
        from app.services.matching_service import MAYBE_MATCH_THRESHOLD, STRONG_MATCH_THRESHOLD

        midpoint = (MAYBE_MATCH_THRESHOLD + STRONG_MATCH_THRESHOLD) / 2
        tiers = self._stage_with_scores([midpoint])
        self.assertEqual(tiers, ["maybe"])

    def test_score_below_all_thresholds_is_below(self) -> None:
        tiers = self._stage_with_scores([0.10])
        self.assertEqual(tiers, ["below"])

    def test_relaxed_bucket_sits_between_maybe_and_below(self) -> None:
        from app.services.matching_service import MAYBE_MATCH_THRESHOLD, RELAXED_MIN_RELEVANCE_SCORE

        midpoint = (RELAXED_MIN_RELEVANCE_SCORE + MAYBE_MATCH_THRESHOLD) / 2
        tiers = self._stage_with_scores([midpoint])
        self.assertEqual(tiers, ["relaxed"])


if __name__ == "__main__":
    unittest.main()
