from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.repositories.user_vacancy_feedback import list_disliked_vacancy_ids, list_liked_vacancy_ids
from app.services.vector_store import get_vector_store


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


def recompute_user_preference_profile(db: Session, *, user_id: int) -> None:
    store = get_vector_store()
    liked_ids = list_liked_vacancy_ids(db, user_id=user_id)
    disliked_ids = list_disliked_vacancy_ids(db, user_id=user_id)

    liked_vectors = store.get_vacancy_vectors(vacancy_ids=list(liked_ids))
    disliked_vectors = store.get_vacancy_vectors(vacancy_ids=list(disliked_ids))

    positive = _centroid(liked_vectors)
    negative = _centroid(disliked_vectors)
    updated_at = datetime.now(timezone.utc).isoformat()

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
            },
        )
