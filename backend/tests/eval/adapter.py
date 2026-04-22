"""Offline matcher adapters for the Phase 2.2 eval harness.

The harness (``matching_eval.evaluate``) consumes a
``resume_id -> list[vacancy_id]`` callable. Adapters in this module
build such callables from fixtures WITHOUT touching Postgres, Qdrant,
or OpenAI.

Phase 2.2 ships the first adapter: ``vector_only_matcher``. It ranks
every fixture vacancy by the pre-computed cosine similarity in
``vector_scores.json`` — no tokens, no gate. This is the nude baseline
the rest of the pipeline must beat.

Later phases (2.3 stage split, 2.4 role classifier, 2.5 rerank) will
layer thicker adapters on top without touching the fixture format or
``matching_eval`` itself.
"""

from __future__ import annotations

from collections.abc import Callable

from app.services.matching_service import (
    _build_resume_skill_set,
    _build_vacancy_skill_set,
    _hybrid_score,
    _overlap_score,
)

from .loader import load_resumes, load_vacancies, load_vector_scores


def vector_only_matcher(
    *,
    top_k: int = 10,
    min_score: float = 0.0,
) -> Callable[[str], list[str]]:
    """Return a matcher that ranks fixture vacancies by cosine score.

    Ties broken by vacancy ID (lexicographic) for determinism. Vacancies
    without a recorded score are skipped — they'd be out-of-corpus for
    that resume.
    """
    vector_scores = load_vector_scores()
    # Resolve the full vacancy universe once so matchers agree on the
    # candidate pool; an adapter that silently ignores fixtures would
    # make metric deltas misleading.
    all_vacancy_ids = set(load_vacancies().keys())

    def _match(resume_id: str) -> list[str]:
        per_resume = vector_scores.get(resume_id, {})
        candidates = [
            (score, vacancy_id)
            for vacancy_id, score in per_resume.items()
            if vacancy_id in all_vacancy_ids and score >= min_score
        ]
        candidates.sort(key=lambda pair: (-pair[0], pair[1]))
        return [vacancy_id for _score, vacancy_id in candidates[:top_k]]

    return _match


def hybrid_matcher(*, top_k: int = 10) -> Callable[[str], list[str]]:
    """Return a matcher that ranks by hybrid (vector × token-overlap) score.

    Reuses the production helpers from ``matching_service``:
    ``_build_resume_skill_set``, ``_build_vacancy_skill_set``,
    ``_overlap_score``, ``_hybrid_score``. Same formula as
    ``match_vacancies_for_resume`` — without the DB/Qdrant/OpenAI
    dependencies. If those helpers drift, this adapter drifts with them
    and the baseline test flags it.
    """
    resumes = load_resumes()
    vacancies = load_vacancies()
    vector_scores = load_vector_scores()

    resume_skills: dict[str, set[str]] = {
        rid: _build_resume_skill_set(r.analysis) for rid, r in resumes.items()
    }
    vacancy_skills: dict[str, set[str]] = {
        vid: _build_vacancy_skill_set(v.payload) for vid, v in vacancies.items()
    }

    def _match(resume_id: str) -> list[str]:
        rskills = resume_skills.get(resume_id, set())
        per_resume = vector_scores.get(resume_id, {})
        candidates: list[tuple[float, str]] = []
        for vacancy_id, vector_score in per_resume.items():
            vskills = vacancy_skills.get(vacancy_id)
            if vskills is None:
                continue
            overlap = _overlap_score(rskills, vskills)
            hybrid = _hybrid_score(vector_score, overlap)
            candidates.append((hybrid, vacancy_id))
        candidates.sort(key=lambda pair: (-pair[0], pair[1]))
        return [vacancy_id for _score, vacancy_id in candidates[:top_k]]

    return _match
