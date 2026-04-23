"""Phase 1.7 PR #3 — preference time decay tests."""

from __future__ import annotations

import math
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from app.services.user_preference_profile_pipeline import (
    MIN_EFFECTIVE_WEIGHT,
    _decay_weights,
    _weighted_centroid,
    recompute_user_preference_profile,
)


class DecayWeightUnitTests(unittest.TestCase):
    def test_recent_feedback_keeps_full_weight(self) -> None:
        now = datetime(2026, 4, 21, tzinfo=UTC)
        weights = _decay_weights([(1, now)], [1], now=now, half_life_days=30.0)
        self.assertAlmostEqual(weights[0], 1.0, places=6)

    def test_half_life_gives_half_weight(self) -> None:
        now = datetime(2026, 4, 21, tzinfo=UTC)
        thirty_days_ago = now - timedelta(days=30)
        weights = _decay_weights([(1, thirty_days_ago)], [1], now=now, half_life_days=30.0)
        self.assertAlmostEqual(weights[0], math.exp(-1.0), places=5)

    def test_ninety_day_gap_decays_below_stale_threshold(self) -> None:
        now = datetime(2026, 4, 21, tzinfo=UTC)
        ninety_days_ago = now - timedelta(days=90)
        weights = _decay_weights([(1, ninety_days_ago)], [1], now=now, half_life_days=30.0)
        self.assertLess(weights[0], MIN_EFFECTIVE_WEIGHT)

    def test_naive_timestamp_treated_as_utc(self) -> None:
        now = datetime(2026, 4, 21, tzinfo=UTC)
        naive_recent = datetime(2026, 4, 21)
        weights = _decay_weights([(5, naive_recent)], [5], now=now, half_life_days=30.0)
        self.assertAlmostEqual(weights[0], 1.0, places=5)


class WeightedCentroidTests(unittest.TestCase):
    def test_unit_weights_equal_plain_mean(self) -> None:
        vectors = [[1.0, 0.0], [0.0, 1.0]]
        weights = [1.0, 1.0]
        centroid, stale = _weighted_centroid(vectors, weights)
        self.assertEqual(centroid, [0.5, 0.5])
        self.assertEqual(stale, 0)

    def test_large_weight_dominates(self) -> None:
        vectors = [[1.0, 0.0], [0.0, 1.0]]
        weights = [0.01, 1.0]
        centroid, _ = _weighted_centroid(vectors, weights)
        assert centroid is not None
        # Dominated by the second vector
        self.assertLess(centroid[0], 0.1)
        self.assertGreater(centroid[1], 0.9)

    def test_counts_stale_contributions(self) -> None:
        vectors = [[1.0], [1.0], [1.0]]
        weights = [1.0, 0.05, 0.02]
        _, stale = _weighted_centroid(vectors, weights)
        self.assertEqual(stale, 2)


class RecomputePipelineDecayTests(unittest.TestCase):
    """Exercise recompute_user_preference_profile end-to-end with mocks."""

    def _run(self, *, decay_enabled: bool, feedback_ages: list[tuple[int, datetime]]):
        store = MagicMock()
        store.get_vacancy_vectors.return_value = [[1.0, 0.0, 0.0]] * len(feedback_ages)
        db = MagicMock()

        with (
            patch(
                "app.services.user_preference_profile_pipeline.get_vector_store",
                return_value=store,
            ),
            patch(
                "app.services.user_preference_profile_pipeline.list_liked_vacancy_ids",
                return_value={vid for vid, _ in feedback_ages},
            ),
            patch(
                "app.services.user_preference_profile_pipeline.list_disliked_vacancy_ids",
                return_value=set(),
            ),
            patch(
                "app.services.user_preference_profile_pipeline.list_liked_vacancy_feedback_ages",
                return_value=feedback_ages,
            ),
            patch(
                "app.services.user_preference_profile_pipeline.list_disliked_vacancy_feedback_ages",
                return_value=[],
            ),
            patch("app.services.user_preference_profile_pipeline.settings") as settings_mock,
        ):
            settings_mock.preference_decay_enabled = decay_enabled
            settings_mock.preference_decay_half_life_days = 30.0
            recompute_user_preference_profile(db, user_id=7, resume_id=11)

        return store

    def test_flag_off_uses_plain_centroid(self) -> None:
        now = datetime.now(UTC)
        feedback = [(i, now - timedelta(days=i * 30)) for i in range(3)]
        store = self._run(decay_enabled=False, feedback_ages=feedback)

        call = store.upsert_user_preference_vector.call_args_list[0]
        payload = call.kwargs["payload"]
        self.assertFalse(payload["decay_enabled"])
        self.assertEqual(payload["feedback_count"], 3)

    def test_flag_on_writes_decay_payload(self) -> None:
        now = datetime.now(UTC)
        feedback = [(i, now - timedelta(days=i * 15)) for i in range(4)]
        store = self._run(decay_enabled=True, feedback_ages=feedback)

        positive_call = next(
            c
            for c in store.upsert_user_preference_vector.call_args_list
            if c.kwargs.get("kind") == "positive"
        )
        payload = positive_call.kwargs["payload"]
        self.assertTrue(payload["decay_enabled"])

    def test_empty_feedback_deletes_preference(self) -> None:
        store = self._run(decay_enabled=True, feedback_ages=[])
        store.delete_user_preference_vector.assert_any_call(
            user_id=7, resume_id=11, kind="positive"
        )
        store.delete_user_preference_vector.assert_any_call(
            user_id=7, resume_id=11, kind="negative"
        )
        store.upsert_user_preference_vector.assert_not_called()


if __name__ == "__main__":
    unittest.main()
