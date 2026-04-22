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

from tests.eval.adapter import hybrid_matcher, vector_only_matcher
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
        # Phase 2.2 landing: mean NDCG@10 ≈ 0.93 with recall-aware
        # IDCG (full gold). Floor set 0.10 below actual to absorb
        # fixture tweaks without flapping.
        self.assertGreaterEqual(self.report.mean_ndcg_at_10, 0.80)

    def test_mrr_floor(self) -> None:
        # Every resume has at least one relevance>=1 vacancy with a very
        # high vector score, so MRR on a vector-only baseline is 1.0.
        # If this ever drops, either the fixture vector scores got wrong
        # or the harness broke.
        self.assertAlmostEqual(self.report.mean_mrr, 1.0, places=6)

    def test_map_floor(self) -> None:
        # Recall-aware MAP divides by the number of relevant items in the
        # full gold for each resume, so missing a rel>=1 item costs
        # score. Baseline lands around 0.74. Floor set 0.04 below.
        self.assertGreaterEqual(self.report.mean_map, 0.70)

    def test_every_resume_scored(self) -> None:
        # Four personas, four per-resume rows. Missing one means a
        # resume has no gold labels.
        self.assertEqual(len(self.report.per_resume), 4)

    def test_report_serializes_to_json(self) -> None:
        payload = json.loads(self.report.to_json())
        self.assertEqual(set(payload["per_resume"][0].keys()) >= {"resume_id", "ndcg_at_10"}, True)


class HybridMatcherTest(unittest.TestCase):
    """Hybrid (vector × token overlap) must not regress below vector-only.

    Using the production ``_hybrid_score`` helper on the same fixture
    corpus, we expect the token-overlap signal to either preserve or
    gently improve ordering — it should never *degrade* the vector-only
    baseline. If someone changes ``_hybrid_score`` or the token bag and
    the hybrid matcher drops below vector-only, this test flags it.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.gold = load_gold_set(gold_path())
        cls.vector_report = evaluate(cls.gold, matcher=vector_only_matcher(top_k=10))
        cls.hybrid_report = evaluate(cls.gold, matcher=hybrid_matcher(top_k=10))

    def test_hybrid_ndcg_not_worse_than_vector_only(self) -> None:
        # Tolerance: 1e-6 — permit numeric tie, forbid regression.
        self.assertGreaterEqual(
            self.hybrid_report.mean_ndcg_at_10,
            self.vector_report.mean_ndcg_at_10 - 1e-6,
            msg=(
                f"hybrid NDCG {self.hybrid_report.mean_ndcg_at_10:.4f} regressed below "
                f"vector-only {self.vector_report.mean_ndcg_at_10:.4f}"
            ),
        )

    def test_hybrid_map_not_worse_than_vector_only(self) -> None:
        self.assertGreaterEqual(
            self.hybrid_report.mean_map,
            self.vector_report.mean_map - 1e-6,
            msg=(
                f"hybrid MAP {self.hybrid_report.mean_map:.4f} regressed below "
                f"vector-only {self.vector_report.mean_map:.4f}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
