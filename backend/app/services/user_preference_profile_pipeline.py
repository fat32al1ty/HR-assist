from __future__ import annotations

import logging
import math
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.user_vacancy_feedback import (
    list_disliked_vacancy_feedback_ages,
    list_disliked_vacancy_ids,
    list_liked_vacancy_feedback_ages,
    list_liked_vacancy_ids,
)
from app.services.vector_store import get_vector_store

logger = logging.getLogger("user_preference")

MIN_EFFECTIVE_WEIGHT = 0.1


def _centroid(vectors: list[list[float]]) -> list[float] | None:
    if not vectors:
        return None
    length = len(vectors[0])
    if length == 0:
        return None

    aggregate = [0.0] * length
    valid_count = 0
    for vector in vectors:
        if len(vector) != length:
            continue
        valid_count += 1
        for index, value in enumerate(vector):
            aggregate[index] += float(value)
    if valid_count == 0:
        return None
    return [value / valid_count for value in aggregate]


def _weighted_centroid(
    vectors: list[list[float]],
    weights: list[float],
) -> tuple[list[float] | None, int]:
    """Weighted mean of `vectors` using `weights`. Returns (centroid, stale_count).

    `stale_count` is the number of contributions whose weight has decayed below
    `MIN_EFFECTIVE_WEIGHT` — surfaced as telemetry for the Phase 2 cleanup UI.
    """
    if not vectors or not weights or len(vectors) != len(weights):
        return None, 0
    length = len(vectors[0])
    if length == 0:
        return None, 0

    aggregate = [0.0] * length
    total_weight = 0.0
    stale = 0
    for vector, weight in zip(vectors, weights, strict=True):
        if len(vector) != length or weight <= 0.0:
            continue
        if weight < MIN_EFFECTIVE_WEIGHT:
            stale += 1
        total_weight += weight
        for index, value in enumerate(vector):
            aggregate[index] += float(value) * weight
    if total_weight <= 0.0:
        return None, stale
    return [value / total_weight for value in aggregate], stale


def _decay_weights(
    feedback_ages: list[tuple[int, datetime]],
    vacancy_ids: list[int],
    *,
    now: datetime,
    half_life_days: float,
) -> list[float]:
    """Compute weights for `vacancy_ids` in the order Qdrant returned them.

    Vacancies without a matching feedback row (shouldn't happen in practice
    because the ids come from the same query) fall back to weight 1.0.
    """
    age_by_id = {vid: ts for vid, ts in feedback_ages}
    weights: list[float] = []
    for vacancy_id in vacancy_ids:
        updated_at = age_by_id.get(vacancy_id)
        if updated_at is None:
            weights.append(1.0)
            continue
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        age_days = max((now - updated_at).total_seconds() / 86400.0, 0.0)
        weights.append(math.exp(-age_days / max(half_life_days, 1e-6)))
    return weights


def _magnitude(vector: list[float] | None) -> float:
    if not vector:
        return 0.0
    return math.sqrt(sum(value * value for value in vector))


def recompute_user_preference_profile(db: Session, *, user_id: int) -> None:
    store = get_vector_store()
    decay_enabled = bool(settings.preference_decay_enabled)
    half_life_days = float(settings.preference_decay_half_life_days)
    now = datetime.now(UTC)

    if decay_enabled:
        liked_rows = list_liked_vacancy_feedback_ages(db, user_id=user_id)
        disliked_rows = list_disliked_vacancy_feedback_ages(db, user_id=user_id)
        liked_ids = [vid for vid, _ in liked_rows]
        disliked_ids = [vid for vid, _ in disliked_rows]
    else:
        liked_ids = list(list_liked_vacancy_ids(db, user_id=user_id))
        disliked_ids = list(list_disliked_vacancy_ids(db, user_id=user_id))
        liked_rows = []
        disliked_rows = []

    liked_vectors = store.get_vacancy_vectors(vacancy_ids=liked_ids)
    disliked_vectors = store.get_vacancy_vectors(vacancy_ids=disliked_ids)

    if decay_enabled:
        liked_weights = _decay_weights(
            liked_rows, liked_ids, now=now, half_life_days=half_life_days
        )
        disliked_weights = _decay_weights(
            disliked_rows, disliked_ids, now=now, half_life_days=half_life_days
        )
        positive, liked_stale = _weighted_centroid(liked_vectors, liked_weights)
        negative, disliked_stale = _weighted_centroid(disliked_vectors, disliked_weights)
        unweighted_positive = _centroid(liked_vectors)
        unweighted_negative = _centroid(disliked_vectors)
        logger.info(
            "preference_decay user_id=%s liked=%d disliked=%d "
            "pos_mag_before=%.4f pos_mag_after=%.4f "
            "neg_mag_before=%.4f neg_mag_after=%.4f "
            "stale_liked=%d stale_disliked=%d half_life_days=%.1f",
            user_id,
            len(liked_ids),
            len(disliked_ids),
            _magnitude(unweighted_positive),
            _magnitude(positive),
            _magnitude(unweighted_negative),
            _magnitude(negative),
            liked_stale,
            disliked_stale,
            half_life_days,
        )
    else:
        positive = _centroid(liked_vectors)
        negative = _centroid(disliked_vectors)

    updated_at = now.isoformat()

    if positive is None:
        store.delete_user_preference_vector(user_id=user_id, kind="positive")
    else:
        store.upsert_user_preference_vector(
            user_id=user_id,
            kind="positive",
            vector=positive,
            payload={
                "feedback_count": len(liked_ids),
                "updated_at": updated_at,
                "decay_enabled": decay_enabled,
            },
        )

    if negative is None:
        store.delete_user_preference_vector(user_id=user_id, kind="negative")
    else:
        store.upsert_user_preference_vector(
            user_id=user_id,
            kind="negative",
            vector=negative,
            payload={
                "feedback_count": len(disliked_ids),
                "updated_at": updated_at,
                "decay_enabled": decay_enabled,
            },
        )
