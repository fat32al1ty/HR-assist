"""ESCO lookup + role-distance helpers.

Thin query layer over the ``esco_*`` reference tables. Used by:

- ``skill_taxonomy`` / ``matching_service`` for alias expansion that
  scales past hand-curated groups.
- ``RoleFamilyGateStage`` for penalising cross-family matches
  proportionally to ISCO-group distance.

All lookups are case-insensitive and normalise unicode NFKC. Scores
are deterministic and cheap — no fuzzy library dependency, just
substring + token-Jaccard with tight tie-breaking so the first hit
is reproducible across Postgres versions.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.esco import (
    EscoOccupation,
    EscoOccupationSkill,
    EscoSkill,
)

_TOKEN_SPLIT = re.compile(r"[^\w]+", re.UNICODE)


@dataclass(frozen=True)
class EscoSkillHit:
    skill_id: int
    esco_uri: str
    preferred_label_en: str
    preferred_label_ru: str | None
    score: float


@dataclass(frozen=True)
class EscoOccupationHit:
    occupation_id: int
    esco_uri: str
    preferred_label_en: str
    preferred_label_ru: str | None
    isco_group: str | None
    score: float


def _normalise(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").strip().lower()


def _tokenise(text: str) -> set[str]:
    norm = _normalise(text)
    # Split on any non-alphanumeric separator; keep digits because ESCO
    # labels include things like "Java 8" or "Python 3".
    return {tok for tok in _TOKEN_SPLIT.split(norm) if tok}


def _label_score(query: str, candidate: str) -> float:
    """0..1 score: 1.0 on exact normalised match, token-Jaccard otherwise."""
    q_norm = _normalise(query)
    c_norm = _normalise(candidate)
    if not q_norm or not c_norm:
        return 0.0
    if q_norm == c_norm:
        return 1.0
    q_tokens = _tokenise(query)
    c_tokens = _tokenise(candidate)
    if not q_tokens or not c_tokens:
        return 0.0
    inter = len(q_tokens & c_tokens)
    if inter == 0:
        return 0.0
    union = len(q_tokens | c_tokens)
    # Cap at 0.95 so exact-match always outranks token overlap; this
    # prevents a near-duplicate alt_label from ever tying with the
    # preferred label on an exact query.
    return min(0.95, inter / union)


def _best_label_score(query: str, labels: list[str] | None) -> float:
    if not labels:
        return 0.0
    best = 0.0
    for label in labels:
        s = _label_score(query, label)
        if s > best:
            best = s
            if best >= 1.0:
                break
    return best


def lookup_skill(
    db: Session, text: str, *, lang: Literal["ru", "en"] = "ru", top_k: int = 3
) -> list[EscoSkillHit]:
    """Return the top ``top_k`` ESCO skills by label-match score.

    Applies a cheap SQL prefilter (trigram-less) to keep the candidate
    set small, then scores in Python. For production-scale corpora
    this should be replaced with a pg_trgm index; current scale
    (~13k skills) is fine with a LIKE-based prefilter.
    """
    if not text or not text.strip():
        return []
    norm = _normalise(text)
    like = f"%{norm}%"

    filters = [
        func.lower(EscoSkill.preferred_label_en).like(like),
        func.lower(func.array_to_string(EscoSkill.alt_labels, "|")).like(like),
    ]
    if lang == "ru":
        filters.append(func.lower(EscoSkill.preferred_label_ru).like(like))

    rows = db.query(EscoSkill).filter(or_(*filters)).limit(200).all()

    scored: list[EscoSkillHit] = []
    for row in rows:
        label_primary = row.preferred_label_ru if lang == "ru" else row.preferred_label_en
        score = max(
            _label_score(text, label_primary or ""),
            _label_score(text, row.preferred_label_en),
            _best_label_score(text, row.alt_labels),
        )
        if score <= 0:
            continue
        scored.append(
            EscoSkillHit(
                skill_id=row.id,
                esco_uri=row.esco_uri,
                preferred_label_en=row.preferred_label_en,
                preferred_label_ru=row.preferred_label_ru,
                score=score,
            )
        )
    scored.sort(key=lambda h: (-h.score, h.preferred_label_en))
    return scored[:top_k]


def lookup_occupation(
    db: Session, text: str, *, lang: Literal["ru", "en"] = "ru", top_k: int = 3
) -> list[EscoOccupationHit]:
    if not text or not text.strip():
        return []
    norm = _normalise(text)
    like = f"%{norm}%"

    alt_col = EscoOccupation.alt_labels_ru if lang == "ru" else EscoOccupation.alt_labels_en

    filters = [
        func.lower(EscoOccupation.preferred_label_en).like(like),
        func.lower(func.array_to_string(alt_col, "|")).like(like),
    ]
    if lang == "ru":
        filters.append(func.lower(EscoOccupation.preferred_label_ru).like(like))

    rows = db.query(EscoOccupation).filter(or_(*filters)).limit(200).all()

    scored: list[EscoOccupationHit] = []
    for row in rows:
        label_primary = row.preferred_label_ru if lang == "ru" else row.preferred_label_en
        alt_labels = row.alt_labels_ru if lang == "ru" else row.alt_labels_en
        score = max(
            _label_score(text, label_primary or ""),
            _label_score(text, row.preferred_label_en),
            _best_label_score(text, alt_labels),
        )
        if score <= 0:
            continue
        scored.append(
            EscoOccupationHit(
                occupation_id=row.id,
                esco_uri=row.esco_uri,
                preferred_label_en=row.preferred_label_en,
                preferred_label_ru=row.preferred_label_ru,
                isco_group=row.isco_group,
                score=score,
            )
        )
    scored.sort(key=lambda h: (-h.score, h.preferred_label_en))
    return scored[:top_k]


def skills_for_occupation(
    db: Session,
    occupation_id: int,
    *,
    relation: Literal["essential", "optional", "any"] = "any",
) -> list[EscoSkill]:
    q = (
        db.query(EscoSkill)
        .join(EscoOccupationSkill, EscoOccupationSkill.skill_id == EscoSkill.id)
        .filter(EscoOccupationSkill.occupation_id == occupation_id)
    )
    if relation != "any":
        q = q.filter(EscoOccupationSkill.relation == relation)
    return q.all()


def role_distance(
    occ_a: EscoOccupation | EscoOccupationHit | None,
    occ_b: EscoOccupation | EscoOccupationHit | None,
) -> float:
    """Return a ``[0, 1]`` distance between two occupations.

    The score is driven by ISCO-group prefix overlap — ISCO codes are
    hierarchical (4-digit, e.g. ``2512`` for software developers),
    so shared prefixes mean closer roles.

    Missing ISCO on either side falls back to 0.5 (unknown neighbour)
    so the caller can still apply a dampened penalty. Returns 1.0 when
    either side is ``None``: caller should treat this as "maximally
    distant" and make its own decision (hard-drop vs. penalise).
    """
    if occ_a is None or occ_b is None:
        return 1.0
    a = occ_a.isco_group or ""
    b = occ_b.isco_group or ""
    if not a or not b:
        return 0.5
    if a == b:
        return 0.0
    # Shared-prefix length; ISCO codes are always 4 digits, so distance
    # buckets are 0.0 (exact), 0.25 (3-digit match), 0.5 (2-digit),
    # 0.75 (1-digit), 1.0 (no shared prefix).
    max_len = max(len(a), len(b))
    shared = 0
    for ch_a, ch_b in zip(a, b, strict=False):
        if ch_a == ch_b:
            shared += 1
        else:
            break
    return 1.0 - (shared / max_len)
