"""Fixture loader for the Phase 2.2 matching-eval harness.

Loads resumes, vacancies, and pre-computed vector scores from the
sibling ``fixtures/`` directory. No network, no DB, no Qdrant.

The resume / vacancy shapes mirror what the production matcher consumes
(``resume.analysis`` dict + vacancy payload + raw_text + source_url),
minus DB-only fields the offline adapters don't need.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class ResumeFixture:
    id: str
    analysis: dict


@dataclass(frozen=True)
class VacancyFixture:
    id: str
    title: str
    source: str
    source_url: str
    payload: dict
    raw_text: str


def load_resumes() -> dict[str, ResumeFixture]:
    out: dict[str, ResumeFixture] = {}
    for path in sorted((FIXTURES_DIR / "resumes").glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        out[row["id"]] = ResumeFixture(id=row["id"], analysis=row["analysis"])
    return out


def load_vacancies() -> dict[str, VacancyFixture]:
    out: dict[str, VacancyFixture] = {}
    for path in sorted((FIXTURES_DIR / "vacancies").glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        out[row["id"]] = VacancyFixture(
            id=row["id"],
            title=row["title"],
            source=row["source"],
            source_url=row["source_url"],
            payload=row["payload"],
            raw_text=row["raw_text"],
        )
    return out


def load_vector_scores() -> dict[str, dict[str, float]]:
    """Return ``resume_id -> vacancy_id -> simulated cosine score``.

    These are hand-set to reflect what OpenAI text-embedding-3-large
    typically produces on Russian tech corpora. See
    ``fixtures/vector_scores.json`` for the full rationale in the
    top-level ``_comment``.
    """
    raw = json.loads((FIXTURES_DIR / "vector_scores.json").read_text(encoding="utf-8"))
    return {
        resume_id: scores
        for resume_id, scores in raw.items()
        if not resume_id.startswith("_")
    }


def gold_path() -> Path:
    return FIXTURES_DIR / "gold.jsonl"
