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


def mmr_matcher(
    *,
    top_k: int = 10,
    lambda_: float = 0.7,
    top_n: int = 30,
) -> Callable[[str], list[str]]:
    """Hybrid matcher followed by MMR reordering over the top-N window.

    Mirrors the production pipeline contract: score first, then let MMR
    swap a redundant high-scorer for a diverse lower-scorer. Offline-only
    — reuses the same fixture skill sets as ``hybrid_matcher`` so the
    Jaccard similarity is computed against the same data the production
    ``MMRDiversifyStage`` would see.
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

    def _jaccard(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        inter = len(left & right)
        if inter == 0:
            return 0.0
        return inter / len(left | right)

    def _match(resume_id: str) -> list[str]:
        rskills = resume_skills.get(resume_id, set())
        per_resume = vector_scores.get(resume_id, {})
        scored: list[tuple[float, str]] = []
        for vacancy_id, vector_score in per_resume.items():
            vskills = vacancy_skills.get(vacancy_id)
            if vskills is None:
                continue
            overlap = _overlap_score(rskills, vskills)
            hybrid = _hybrid_score(vector_score, overlap)
            scored.append((hybrid, vacancy_id))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))

        window = scored[:top_n]
        tail = scored[top_n:]
        remaining = list(window)
        selected: list[tuple[float, str]] = []
        if remaining:
            selected.append(remaining.pop(0))
        while remaining:
            best_idx = 0
            best_val = -float("inf")
            for idx, (score, vid) in enumerate(remaining):
                vskills = vacancy_skills.get(vid, set())
                max_sim = 0.0
                for _pscore, pvid in selected:
                    sim = _jaccard(vskills, vacancy_skills.get(pvid, set()))
                    if sim > max_sim:
                        max_sim = sim
                mmr = lambda_ * score - (1.0 - lambda_) * max_sim
                if mmr > best_val:
                    best_val = mmr
                    best_idx = idx
            selected.append(remaining.pop(best_idx))

        merged = selected + tail
        return [vid for _s, vid in merged[:top_k]]

    return _match
