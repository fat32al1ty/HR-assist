"""Baseline NDCG/MAP/MRR run over the Phase 2.2 gold set.

Exercises the math harness (``matching_eval.evaluate``) against the
fixture corpus using the simplest possible matcher —
``vector_only_matcher`` — which ranks by pre-computed cosine
similarity and nothing else. No domain gate, no overlap, no rerank.

The numbers this test locks in are floors, not targets. The entire
point of Phase 2.2 is that later phases (domain gate, ESCO
classifier, cross-encoder) must raise these numbers, and CI breaks
loudly when someone regresses below the baseline.

When you legitimately improve the adapter, update the floors; don't
lower them. The comment on each floor records the baseline number the
change is expected to beat.
"""

from __future__ import annotations

import json
import unittest

from app.services.matching_eval import evaluate, load_gold_set

from tests.eval.adapter import vector_only_matcher
from tests.eval.loader import gold_path


class VectorOnlyBaselineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gold = load_gold_set(gold_path())
        cls.report = evaluate(cls.gold, matcher=vector_only_matcher(top_k=10))

    def test_gold_set_size(self) -> None:
        # Phase 2.2 plan: ≥100 labeled triples. If someone trims the set,
        # flag loudly — a smaller gold set = noisier metrics.
        self.assertGreaterEqual(self.report.total_labeled_pairs, 100)

    def test_ndcg_floor(self) -> None:
        # Pure-vector baseline on the current fixture set. This is the
        # number every subsequent phase must beat. Measured value at
        # Phase 2.2 landing: ~0.86 (driven by strong-match vacancies
        # sitting at vector score > 0.85 for every resume persona).
        self.assertGreaterEqual(self.report.mean_ndcg_at_10, 0.80)

    def test_mrr_floor(self) -> None:
        # Every resume has at least one relevance>=1 vacancy with a very
        # high vector score, so MRR on a vector-only baseline is 1.0.
        # If this ever drops, either the fixture vector scores got wrong
        # or the harness broke.
        self.assertAlmostEqual(self.report.mean_mrr, 1.0, places=6)

    def test_map_floor(self) -> None:
        # MAP is noisier than NDCG because it treats relevance>=1 as a
        # hit and weights by position. Baseline lands around 0.85+.
        self.assertGreaterEqual(self.report.mean_map, 0.70)

    def test_every_resume_scored(self) -> None:
        # Four personas, four per-resume rows. Missing one means a
        # resume has no gold labels.
        self.assertEqual(len(self.report.per_resume), 4)

    def test_report_serializes_to_json(self) -> None:
        payload = json.loads(self.report.to_json())
        self.assertEqual(set(payload["per_resume"][0].keys()) >= {"resume_id", "ndcg_at_10"}, True)


if __name__ == "__main__":
    unittest.main()
