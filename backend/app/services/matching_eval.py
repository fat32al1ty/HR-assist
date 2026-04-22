"""Offline evaluation harness for the matching pipeline.

Phase 2.2 of the matching-engine roadmap.

The job of this module: given a set of labeled (resume, vacancy, relevance)
triples and a matcher function that returns ordered candidate vacancy IDs for
a given resume, compute standard ranking metrics (NDCG@10, MAP, MRR) and
produce a deterministic report.

Nothing in this module hits OpenAI, Qdrant, or Postgres. That is deliberate:
the evaluation must be free and offline so that it runs on every PR, every
dev machine, and in CI. Fixture resumes / vacancies / pre-computed
embeddings are supplied by the caller (see ``backend/tests/eval/``).

The math follows the standard definitions:

- **NDCG@k** uses the ``(2**rel - 1) / log2(rank + 1)`` gain form, divided by
  the ideal DCG of the same labeled set. Returns a float in ``[0, 1]``.
- **Average Precision** treats relevance ``>= 1`` as "relevant", returns the
  mean of precisions at each hit position. ``0`` when nothing is relevant.
- **MRR** = reciprocal rank of the first relevant hit, ``0`` if none.

The top-level runner (``evaluate``) produces per-resume scores + aggregates.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class GoldEntry:
    """One labeled (resume, vacancy, relevance) triple.

    ``relevance`` is ordinal: 0 = irrelevant, 1 = maybe, 2 = strong match.
    IDs are opaque strings — they point to fixture files, not DB rows, so
    the gold set is stable across dev machines.
    """

    resume_id: str
    vacancy_id: str
    relevance: int


@dataclass(frozen=True)
class ResumeEvalResult:
    resume_id: str
    ndcg_at_10: float
    map_score: float
    mrr: float
    n_labeled: int
    n_returned: int
    n_unlabeled_returned: int


@dataclass(frozen=True)
class EvalReport:
    per_resume: tuple[ResumeEvalResult, ...]
    mean_ndcg_at_10: float
    mean_map: float
    mean_mrr: float
    total_labeled_pairs: int

    def to_json(self) -> str:
        payload = {
            "mean_ndcg_at_10": round(self.mean_ndcg_at_10, 4),
            "mean_map": round(self.mean_map, 4),
            "mean_mrr": round(self.mean_mrr, 4),
            "total_labeled_pairs": self.total_labeled_pairs,
            "per_resume": [asdict(r) for r in self.per_resume],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)


def load_gold_set(path: Path | str) -> list[GoldEntry]:
    """Load a JSONL gold set. Comment lines (``#``) and blank lines skipped."""
    entries: list[GoldEntry] = []
    raw = Path(path).read_text(encoding="utf-8")
    for lineno, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as error:
            raise ValueError(f"gold set {path} line {lineno}: {error}") from error
        required = {"resume_id", "vacancy_id", "relevance"}
        missing = required - row.keys()
        if missing:
            raise ValueError(f"gold set {path} line {lineno}: missing fields {sorted(missing)}")
        relevance = int(row["relevance"])
        if relevance not in (0, 1, 2):
            raise ValueError(
                f"gold set {path} line {lineno}: relevance must be 0/1/2, got {relevance}"
            )
        entries.append(
            GoldEntry(
                resume_id=str(row["resume_id"]),
                vacancy_id=str(row["vacancy_id"]),
                relevance=relevance,
            )
        )
    return entries


def ndcg_at_k(
    ranked_relevances: Iterable[int],
    k: int = 10,
    *,
    ideal_relevances: Iterable[int] | None = None,
) -> float:
    """Normalized DCG at cutoff k.

    Gain is ``2**rel - 1`` so a relevance-2 item contributes 3× more than a
    relevance-1. Returns 0 when the ideal DCG is zero (nothing graded to
    rank against) — avoids a false 1.0 on empty input.

    ``ideal_relevances`` is the multiset used to build the denominator. If
    omitted, falls back to ``sorted(ranked_relevances)`` — which measures
    *ordering quality* of the returned list only (legacy per-query form).
    For **full-corpus NDCG** (recall-aware), pass the top-k relevances
    from the complete gold set for this query — that's what
    ``score_resume`` does.
    """
    if k <= 0:
        raise ValueError("k must be positive")
    ranked = list(ranked_relevances)
    ideal = list(ideal_relevances) if ideal_relevances is not None else sorted(ranked, reverse=True)

    def dcg(rels: list[int]) -> float:
        return sum((2**rel - 1) / math.log2(position + 2) for position, rel in enumerate(rels[:k]))

    ideal_dcg = dcg(ideal)
    if ideal_dcg <= 0.0:
        return 0.0
    return dcg(ranked) / ideal_dcg


def average_precision(
    ranked_relevances: Iterable[int],
    *,
    num_relevant_total: int | None = None,
) -> float:
    """AP treats ``relevance >= 1`` as relevant.

    Returns the mean of precisions at each relevant hit. ``num_relevant_total``
    is the count of relevant items in the **full** labeled set for this
    query — when provided, AP is recall-aware (sum of precisions ÷ total
    relevant, so missing relevant items cost MAP). When omitted (legacy
    form), AP divides by the number of hits in the returned list — a
    precision-only average that ignores what the matcher missed.

    ``score_resume`` uses the recall-aware form; standalone callers who
    want the old behavior can omit the argument.
    """
    hits = 0
    total = 0.0
    for position, relevance in enumerate(ranked_relevances):
        if relevance >= 1:
            hits += 1
            total += hits / (position + 1)
    if num_relevant_total is not None:
        if num_relevant_total <= 0:
            return 0.0
        return total / num_relevant_total
    if hits == 0:
        return 0.0
    return total / hits


def reciprocal_rank(ranked_relevances: Iterable[int]) -> float:
    """Reciprocal rank of the first ``relevance >= 1`` entry, 0 if none."""
    for position, relevance in enumerate(ranked_relevances):
        if relevance >= 1:
            return 1.0 / (position + 1)
    return 0.0


def score_resume(
    resume_id: str,
    labels_for_resume: dict[str, int],
    returned_vacancy_ids: list[str],
    *,
    k: int = 10,
) -> ResumeEvalResult:
    """Score one resume's matcher output against its labels.

    ``returned_vacancy_ids`` is the ordered list produced by the matcher
    (position 0 = top). Unlabeled items in the ranking contribute ``0`` to
    every metric — they are neither penalized nor rewarded. This matches the
    "partial labels, not ground-truth complete" reality of small gold sets.

    NDCG here is **recall-aware**: the ideal DCG is computed from the
    top-k most-relevant items in the *full* labeled set, not from the
    matcher's output. A matcher that misses a relevance-2 vacancy pays
    for it even when its ordering of what it did return is perfect.
    """
    ranked_relevances: list[int] = [labels_for_resume.get(vid, 0) for vid in returned_vacancy_ids]
    n_unlabeled = sum(1 for vid in returned_vacancy_ids if vid not in labels_for_resume)
    ideal_relevances = sorted(labels_for_resume.values(), reverse=True)
    num_relevant_total = sum(1 for rel in labels_for_resume.values() if rel >= 1)
    return ResumeEvalResult(
        resume_id=resume_id,
        ndcg_at_10=ndcg_at_k(ranked_relevances, k=k, ideal_relevances=ideal_relevances),
        map_score=average_precision(ranked_relevances, num_relevant_total=num_relevant_total),
        mrr=reciprocal_rank(ranked_relevances),
        n_labeled=len(labels_for_resume),
        n_returned=len(returned_vacancy_ids),
        n_unlabeled_returned=n_unlabeled,
    )


def evaluate(
    gold: list[GoldEntry],
    matcher: Callable[[str], list[str]],
    *,
    k: int = 10,
) -> EvalReport:
    """Run the matcher against every resume in ``gold`` and aggregate.

    ``matcher`` is ``resume_id -> ordered list of vacancy IDs``. The caller
    wires it up against whatever infrastructure they want — real
    ``match_vacancies_for_resume`` with fixture-backed stubs, a mock, or a
    trivial baseline. The harness itself does not know where the candidates
    come from.
    """
    labels_by_resume: dict[str, dict[str, int]] = {}
    for entry in gold:
        labels_by_resume.setdefault(entry.resume_id, {})[entry.vacancy_id] = entry.relevance

    per_resume: list[ResumeEvalResult] = []
    for resume_id in sorted(labels_by_resume):
        returned = matcher(resume_id)
        per_resume.append(score_resume(resume_id, labels_by_resume[resume_id], returned, k=k))

    if not per_resume:
        return EvalReport(
            per_resume=(),
            mean_ndcg_at_10=0.0,
            mean_map=0.0,
            mean_mrr=0.0,
            total_labeled_pairs=len(gold),
        )

    def _mean(values: list[float]) -> float:
        return sum(values) / len(values)

    return EvalReport(
        per_resume=tuple(per_resume),
        mean_ndcg_at_10=_mean([r.ndcg_at_10 for r in per_resume]),
        mean_map=_mean([r.map_score for r in per_resume]),
        mean_mrr=_mean([r.mrr for r in per_resume]),
        total_labeled_pairs=len(gold),
    )
