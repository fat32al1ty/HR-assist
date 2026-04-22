"""Unit tests for the Phase 2.2 evaluation harness math.

Covers NDCG@k, MAP, MRR, and the end-to-end ``evaluate`` runner. Uses
in-memory data only — no DB, no Qdrant, no OpenAI. These tests are the
foundation of the matcher's quality gate: if this math is wrong, every
downstream "we improved NDCG" claim is wrong.
"""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.matching_eval import (
    EvalReport,
    GoldEntry,
    ResumeEvalResult,
    average_precision,
    evaluate,
    load_gold_set,
    ndcg_at_k,
    reciprocal_rank,
    score_resume,
)


class NDCGTest(unittest.TestCase):
    def test_perfect_ranking_returns_one(self) -> None:
        self.assertAlmostEqual(ndcg_at_k([2, 2, 1, 1, 0], k=10), 1.0, places=6)

    def test_worst_ranking_is_strictly_less_than_one(self) -> None:
        self.assertLess(ndcg_at_k([0, 0, 1, 1, 2, 2], k=10), 1.0)

    def test_all_zero_labels_returns_zero(self) -> None:
        # Nothing to rank against → 0.0, not 1.0.
        self.assertEqual(ndcg_at_k([0, 0, 0, 0], k=10), 0.0)

    def test_empty_ranking_returns_zero(self) -> None:
        self.assertEqual(ndcg_at_k([], k=10), 0.0)

    def test_cutoff_respected(self) -> None:
        # Items beyond k are ignored — a relevance-2 at position 11 can't
        # save a bad top-10.
        ranking = [0] * 10 + [2]
        self.assertEqual(ndcg_at_k(ranking, k=10), 0.0)

    def test_gain_is_exponential(self) -> None:
        # rel=2 at top beats rel=1 at top → ideal-DCG also jumps, so the
        # ratio here is 1.0 for both. The real check: rel=2+rel=0 beats
        # rel=1+rel=1 for the same ideal (both sort to the same multiset
        # only when multisets are equal). We compare *raw* DCG proxies via
        # mixed orderings:
        better = ndcg_at_k([2, 1], k=10)  # ideal = [2, 1] → ratio 1.0
        worse = ndcg_at_k([1, 2], k=10)  # ideal = [2, 1] → < 1.0
        self.assertLess(worse, better)

    def test_k_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            ndcg_at_k([1, 1, 1], k=0)


class AveragePrecisionTest(unittest.TestCase):
    def test_all_relevant_at_top(self) -> None:
        self.assertEqual(average_precision([1, 1, 0, 0]), 1.0)

    def test_first_relevant_at_position_2(self) -> None:
        # hit at position 2 → precision 1/2. Mean of one precision = 0.5.
        self.assertAlmostEqual(average_precision([0, 1, 0, 0]), 0.5, places=6)

    def test_two_hits_one_near_top_one_further(self) -> None:
        # [1, 0, 1, 0] → precisions at hits: 1/1 and 2/3. Mean = (1 + 2/3)/2.
        self.assertAlmostEqual(
            average_precision([1, 0, 1, 0]), (1.0 + 2.0 / 3.0) / 2.0, places=6
        )

    def test_relevance_two_counts_as_hit(self) -> None:
        # AP is binarized at >= 1.
        self.assertEqual(average_precision([2, 2]), 1.0)

    def test_no_hits_returns_zero(self) -> None:
        self.assertEqual(average_precision([0, 0, 0]), 0.0)


class ReciprocalRankTest(unittest.TestCase):
    def test_first_hit_at_top(self) -> None:
        self.assertEqual(reciprocal_rank([1, 0, 0]), 1.0)

    def test_first_hit_at_position_3(self) -> None:
        self.assertAlmostEqual(reciprocal_rank([0, 0, 1]), 1.0 / 3.0, places=6)

    def test_no_hit_returns_zero(self) -> None:
        self.assertEqual(reciprocal_rank([0, 0, 0]), 0.0)

    def test_relevance_two_counts(self) -> None:
        self.assertEqual(reciprocal_rank([0, 2]), 0.5)


class ScoreResumeTest(unittest.TestCase):
    def test_unlabeled_items_contribute_zero(self) -> None:
        labels = {"good-1": 2, "good-2": 2, "bad-1": 0}
        # Returned list mixes one unlabeled ID ("mystery") + a bad one + two
        # good ones. Unlabeled counted as 0 toward ranking relevance.
        result = score_resume(
            "r1",
            labels,
            returned_vacancy_ids=["good-1", "mystery", "bad-1", "good-2"],
        )
        self.assertEqual(result.resume_id, "r1")
        self.assertEqual(result.n_labeled, 3)
        self.assertEqual(result.n_returned, 4)
        self.assertEqual(result.n_unlabeled_returned, 1)
        # MRR: first hit at position 0 → 1.0
        self.assertEqual(result.mrr, 1.0)

    def test_all_labeled_and_perfect_order(self) -> None:
        labels = {"a": 2, "b": 2, "c": 1, "d": 1, "e": 0}
        result = score_resume("r1", labels, ["a", "b", "c", "d", "e"])
        self.assertAlmostEqual(result.ndcg_at_10, 1.0, places=6)
        self.assertEqual(result.n_unlabeled_returned, 0)

    def test_empty_matcher_output(self) -> None:
        result = score_resume("r1", {"a": 2}, [])
        self.assertEqual(result.ndcg_at_10, 0.0)
        self.assertEqual(result.map_score, 0.0)
        self.assertEqual(result.mrr, 0.0)
        self.assertEqual(result.n_returned, 0)


class LoadGoldSetTest(unittest.TestCase):
    def _write(self, text: str) -> Path:
        tmp = self._tmpdir.name
        path = Path(tmp) / "gold.jsonl"
        path.write_text(text, encoding="utf-8")
        return path

    def setUp(self) -> None:
        self._tmpdir = TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def test_basic_load(self) -> None:
        path = self._write(
            "\n".join(
                [
                    '{"resume_id": "r1", "vacancy_id": "v1", "relevance": 2}',
                    '{"resume_id": "r1", "vacancy_id": "v2", "relevance": 0}',
                ]
            )
        )
        entries = load_gold_set(path)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0], GoldEntry("r1", "v1", 2))
        self.assertEqual(entries[1], GoldEntry("r1", "v2", 0))

    def test_comments_and_blank_lines_skipped(self) -> None:
        path = self._write(
            "\n".join(
                [
                    "# comment at top",
                    "",
                    '{"resume_id": "r1", "vacancy_id": "v1", "relevance": 1}',
                    "# trailing comment",
                    "",
                ]
            )
        )
        entries = load_gold_set(path)
        self.assertEqual(len(entries), 1)

    def test_rejects_invalid_relevance(self) -> None:
        path = self._write('{"resume_id": "r1", "vacancy_id": "v1", "relevance": 3}')
        with self.assertRaises(ValueError):
            load_gold_set(path)

    def test_rejects_missing_field(self) -> None:
        path = self._write('{"resume_id": "r1", "relevance": 1}')
        with self.assertRaises(ValueError):
            load_gold_set(path)

    def test_rejects_bad_json(self) -> None:
        path = self._write("{not-json")
        with self.assertRaises(ValueError):
            load_gold_set(path)


class EvaluateRunnerTest(unittest.TestCase):
    def test_perfect_matcher_gives_perfect_metrics(self) -> None:
        gold = [
            GoldEntry("r1", "v1", 2),
            GoldEntry("r1", "v2", 1),
            GoldEntry("r1", "v3", 0),
            GoldEntry("r2", "v4", 2),
            GoldEntry("r2", "v5", 0),
        ]

        # Matcher returns all labeled vacancies in perfect descending-relevance order.
        ordering = {
            "r1": ["v1", "v2", "v3"],
            "r2": ["v4", "v5"],
        }
        report = evaluate(gold, matcher=ordering.__getitem__)

        self.assertAlmostEqual(report.mean_ndcg_at_10, 1.0, places=6)
        self.assertAlmostEqual(report.mean_mrr, 1.0, places=6)
        self.assertEqual(report.total_labeled_pairs, 5)
        self.assertEqual(len(report.per_resume), 2)

    def test_worst_matcher_degrades_all_metrics(self) -> None:
        gold = [
            GoldEntry("r1", "v1", 2),
            GoldEntry("r1", "v2", 2),
            GoldEntry("r1", "v3", 0),
            GoldEntry("r1", "v4", 0),
        ]
        # Bad matcher puts the zeros on top.
        report = evaluate(gold, matcher=lambda rid: ["v3", "v4", "v1", "v2"])
        self.assertLess(report.mean_ndcg_at_10, 1.0)
        # First hit at position 3 → MRR = 1/3.
        self.assertAlmostEqual(report.mean_mrr, 1.0 / 3.0, places=6)

    def test_empty_gold_returns_zeros(self) -> None:
        report = evaluate([], matcher=lambda rid: [])
        self.assertEqual(report.mean_ndcg_at_10, 0.0)
        self.assertEqual(report.mean_map, 0.0)
        self.assertEqual(report.mean_mrr, 0.0)
        self.assertEqual(report.per_resume, ())

    def test_to_json_is_valid_json_with_expected_keys(self) -> None:
        report = EvalReport(
            per_resume=(
                ResumeEvalResult("r1", 0.5, 0.6, 0.7, 3, 5, 1),
            ),
            mean_ndcg_at_10=0.5,
            mean_map=0.6,
            mean_mrr=0.7,
            total_labeled_pairs=3,
        )
        payload = json.loads(report.to_json())
        self.assertIn("mean_ndcg_at_10", payload)
        self.assertIn("mean_map", payload)
        self.assertIn("mean_mrr", payload)
        self.assertIn("per_resume", payload)
        self.assertEqual(payload["per_resume"][0]["resume_id"], "r1")

    def test_known_numeric_example(self) -> None:
        # Hand-computed sanity check — if the math drifts, this breaks.
        # One resume, three labels, one returned ordering.
        labels = {"v1": 2, "v2": 0, "v3": 1}
        returned = ["v1", "v3", "v2"]
        # Relevances: [2, 1, 0]
        # DCG = (2^2-1)/log2(2) + (2^1-1)/log2(3) + 0 = 3/1 + 1/1.585 = 3 + 0.6309
        # Ideal DCG = same (already descending) = 3.6309
        # → NDCG = 1.0
        result = score_resume("r1", labels, returned)
        self.assertAlmostEqual(result.ndcg_at_10, 1.0, places=6)

        # MAP on relevances [2, 1, 0]: hits at positions 0 and 1
        #  precisions 1/1 and 2/2 → mean = 1.0
        self.assertAlmostEqual(result.map_score, 1.0, places=6)
        self.assertEqual(result.mrr, 1.0)


if __name__ == "__main__":
    unittest.main()
