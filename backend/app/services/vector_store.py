from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.core.config import settings

DEFAULT_COLLECTIONS = ("resume_profiles", "vacancy_profiles", "user_preference_profiles")


class VectorStoreUnavailable(RuntimeError):
    pass


class QdrantVectorStore:
    def __init__(self) -> None:
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=5,
        )

    def collection_name(self, base_name: str) -> str:
        prefix = settings.qdrant_collection_prefix.strip("_")
        return f"{prefix}_{base_name}" if prefix else base_name

    def healthcheck(self) -> dict[str, Any]:
        try:
            collections = self.client.get_collections().collections
        except Exception as error:
            return {
                "status": "unavailable",
                "error": str(error),
            }

        return {
            "status": "connected",
            "url": settings.qdrant_url,
            "collections": [collection.name for collection in collections],
        }

    def ensure_collection(self, base_name: str) -> str:
        collection_name = self.collection_name(base_name)
        if self.client.collection_exists(collection_name):
            return collection_name

        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=settings.vector_size,
                distance=models.Distance.COSINE,
            ),
        )
        return collection_name

    def ensure_default_collections(self) -> list[str]:
        return [self.ensure_collection(collection) for collection in DEFAULT_COLLECTIONS]

    def upsert_resume_profile(
        self,
        *,
        resume_id: int,
        user_id: int,
        vector: list[float],
        payload: dict[str, Any],
    ) -> tuple[str, str]:
        collection_name = self.ensure_collection("resume_profiles")
        point_id = resume_id
        self.client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        **payload,
                        "resume_id": resume_id,
                        "user_id": user_id,
                    },
                )
            ],
        )
        return collection_name, str(point_id)

    def delete_resume_profile(self, *, resume_id: int) -> None:
        collection_name = self.collection_name("resume_profiles")
        if not self.client.collection_exists(collection_name):
            return

        self.client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=[resume_id]),
        )

    def upsert_vacancy_profile(
        self,
        *,
        vacancy_id: int,
        vector: list[float],
        payload: dict[str, Any],
    ) -> tuple[str, str]:
        collection_name = self.ensure_collection("vacancy_profiles")
        point_id = vacancy_id
        self.client.upsert(
            collection_name=collection_name,
            points=[models.PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        return collection_name, str(point_id)

    def get_resume_vector(self, *, resume_id: int) -> list[float] | None:
        collection_name = self.collection_name("resume_profiles")
        if not self.client.collection_exists(collection_name):
            return None

        points = self.client.retrieve(
            collection_name=collection_name,
            ids=[resume_id],
            with_vectors=True,
        )
        if not points:
            return None
        vector = points[0].vector
        if isinstance(vector, list):
            return vector
        return None

    def search_vacancy_profiles(
        self, *, query_vector: list[float], limit: int = 20
    ) -> list[tuple[int, float, dict[str, Any]]]:
        collection_name = self.collection_name("vacancy_profiles")
        if not self.client.collection_exists(collection_name):
            return []

        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            with_payload=True,
            limit=limit,
        )

        mapped: list[tuple[int, float, dict[str, Any]]] = []
        for point in results:
            vacancy_id = point.payload.get("vacancy_id") if point.payload else None
            if not isinstance(vacancy_id, int):
                continue
            mapped.append((vacancy_id, float(point.score), point.payload or {}))
        return mapped

    def get_vacancy_vectors(self, *, vacancy_ids: list[int]) -> list[list[float]]:
        collection_name = self.collection_name("vacancy_profiles")
        if not self.client.collection_exists(collection_name):
            return []
        ids = [int(item) for item in vacancy_ids if isinstance(item, int)]
        if not ids:
            return []

        points = self.client.retrieve(
            collection_name=collection_name,
            ids=ids,
            with_vectors=True,
            with_payload=False,
        )
        vectors: list[list[float]] = []
        for point in points:
            vector = point.vector
            if isinstance(vector, list):
                vectors.append([float(value) for value in vector])
        return vectors

    def _user_preference_point_id(self, *, user_id: int, kind: str) -> int:
        normalized = kind.strip().lower()
        if normalized not in {"positive", "negative"}:
            raise ValueError(f"Unsupported preference kind: {kind}")
        # Qdrant point IDs are int or UUID. Keep deterministic compact integer IDs per user.
        base = int(user_id) * 10
        return base + (1 if normalized == "positive" else 2)

    def upsert_user_preference_vector(
        self,
        *,
        user_id: int,
        kind: str,
        vector: list[float],
        payload: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        collection_name = self.ensure_collection("user_preference_profiles")
        point_id = self._user_preference_point_id(user_id=user_id, kind=kind)
        self.client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "type": "user_preference_profile",
                        "user_id": user_id,
                        "kind": kind,
                        **(payload or {}),
                    },
                )
            ],
        )
        return collection_name, point_id

    def delete_user_preference_vector(self, *, user_id: int, kind: str) -> None:
        collection_name = self.collection_name("user_preference_profiles")
        if not self.client.collection_exists(collection_name):
            return
        point_id = self._user_preference_point_id(user_id=user_id, kind=kind)
        self.client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=[point_id]),
        )

    def get_user_preference_vectors(self, *, user_id: int) -> tuple[list[float] | None, list[float] | None]:
        collection_name = self.collection_name("user_preference_profiles")
        if not self.client.collection_exists(collection_name):
            return None, None

        positive_id = self._user_preference_point_id(user_id=user_id, kind="positive")
        negative_id = self._user_preference_point_id(user_id=user_id, kind="negative")
        points = self.client.retrieve(
            collection_name=collection_name,
            ids=[positive_id, negative_id],
            with_vectors=True,
            with_payload=True,
        )

        positive: list[float] | None = None
        negative: list[float] | None = None
        for point in points:
            kind = None
            if isinstance(point.payload, dict):
                maybe_kind = point.payload.get("kind")
                if isinstance(maybe_kind, str):
                    kind = maybe_kind.strip().lower()
            vector = point.vector
            if not isinstance(vector, list):
                continue
            normalized = [float(value) for value in vector]
            if kind == "positive":
                positive = normalized
            elif kind == "negative":
                negative = normalized
        return positive, negative


@lru_cache
def get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore()


def ensure_default_vector_collections() -> list[str]:
    try:
        return get_vector_store().ensure_default_collections()
    except Exception as error:
        raise VectorStoreUnavailable(f"Qdrant vector store is unavailable: {error}") from error
