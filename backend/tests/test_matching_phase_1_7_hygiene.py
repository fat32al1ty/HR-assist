"""Phase 1.7 PR #2 — archived-at-match-time + Qdrant is_vacancy pre-filter tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.matching_service import match_vacancies_for_resume


class ArchivedAtMatchTimeTest(unittest.TestCase):
    """When the matcher sees an archived vacancy, it should flip the row and evict the Qdrant point."""

    def _build_context(self, vacancy, payload, *, is_archived: bool):
        resume = SimpleNamespace(
            analysis={
                "target_role": "Senior Backend Engineer",
                "hard_skills": ["python", "postgres", "docker"],
                "matching_keywords": ["backend", "python"],
            }
        )
        vector_store = MagicMock()
        vector_store.get_resume_vector.return_value = [0.1] * 8
        vector_store.get_user_preference_vectors.return_value = (None, None)
        vector_store.search_vacancy_profiles.return_value = [(vacancy.id, 0.8, payload)]
        vector_store.delete_vacancy_profile = MagicMock()

        user = SimpleNamespace(
            preferred_work_format="any",
            relocation_mode="any_city",
            home_city=None,
            preferred_titles=[],
        )

        db = MagicMock()
        db.get.return_value = user

        patchers = [
            patch("app.services.matching_service.get_resume_for_user", return_value=resume),
            patch("app.services.matching_service.get_vector_store", return_value=vector_store),
            patch(
                "app.services.matching_service.recompute_user_preference_profile",
                return_value=None,
            ),
            patch("app.services.matching_service.list_disliked_vacancy_ids", return_value=[]),
            patch("app.services.matching_service.list_liked_vacancy_ids", return_value=[]),
            patch(
                "app.services.matching_service.get_vacancy_by_id",
                side_effect=lambda _db, vacancy_id: vacancy,
            ),
            patch("app.services.matching_service._host_allowed_for_matching", return_value=True),
            patch("app.services.matching_service._looks_non_vacancy_page", return_value=False),
            patch(
                "app.services.matching_service._looks_archived_vacancy_strict",
                return_value=is_archived,
            ),
            patch("app.services.matching_service._looks_like_listing_page", return_value=False),
            patch("app.services.matching_service._looks_unlikely_stack", return_value=False),
            patch(
                "app.services.matching_service._looks_business_monitoring_role",
                return_value=False,
            ),
            patch("app.services.matching_service._looks_hard_non_it_role", return_value=False),
            patch("app.services.matching_service._lexical_fallback_matches", return_value=[]),
        ]
        return db, vector_store, patchers

    def _vacancy(self):
        return SimpleNamespace(
            id=42,
            status="indexed",
            source="hh_api",
            source_url="https://hh.ru/vacancy/42",
            title="Senior Backend Engineer",
            company="CoArchived",
            location="Москва",
            raw_text="Вакансия в архиве c 2026-01-15",
        )

    def _payload(self, vacancy_id: int):
        return {
            "vacancy_id": vacancy_id,
            "is_vacancy": True,
            "title": "Senior Backend Engineer",
            "remote_policy": "remote",
            "location": "Москва",
            "must_have_skills": ["python", "postgres", "docker"],
            "matching_keywords": ["backend"],
            "summary": "Python backend role",
        }

    def test_archive_detection_flips_status_and_evicts_qdrant(self) -> None:
        vacancy = self._vacancy()
        payload = self._payload(vacancy.id)
        db, vector_store, patchers = self._build_context(vacancy, payload, is_archived=True)

        metrics: dict = {}
        with (
            patchers[0],
            patchers[1],
            patchers[2],
            patchers[3],
            patchers[4],
            patchers[5],
            patchers[6],
            patchers[7],
            patchers[8],
            patchers[9],
            patchers[10],
            patchers[11],
            patchers[12],
            patchers[13],
        ):
            matches = match_vacancies_for_resume(
                db, resume_id=1, user_id=7, limit=20, metrics=metrics
            )

        self.assertEqual(matches, [])
        self.assertEqual(vacancy.status, "filtered")
        self.assertEqual(vacancy.error_message, "archived detected at match time")
        vector_store.delete_vacancy_profile.assert_called_once_with(vacancy_id=42)
        self.assertEqual(metrics["archived_at_match_time"], 1)

    def test_healthy_vacancy_does_not_flip_status(self) -> None:
        vacancy = self._vacancy()
        vacancy.raw_text = "Ищем Python-бэкендера со знанием PostgreSQL"
        payload = self._payload(vacancy.id)
        db, vector_store, patchers = self._build_context(vacancy, payload, is_archived=False)

        metrics: dict = {}
        with (
            patchers[0],
            patchers[1],
            patchers[2],
            patchers[3],
            patchers[4],
            patchers[5],
            patchers[6],
            patchers[7],
            patchers[8],
            patchers[9],
            patchers[10],
            patchers[11],
            patchers[12],
            patchers[13],
        ):
            matches = match_vacancies_for_resume(
                db, resume_id=1, user_id=7, limit=20, metrics=metrics
            )

        self.assertEqual(vacancy.status, "indexed")
        vector_store.delete_vacancy_profile.assert_not_called()
        self.assertEqual(metrics["archived_at_match_time"], 0)
        self.assertEqual(len(matches), 1)


class QdrantIsVacancyFilterTest(unittest.TestCase):
    """search_vacancy_profiles should default to filtering on is_vacancy=True."""

    def test_filter_passed_when_only_vacancies_is_default(self) -> None:
        from app.services.vector_store import QdrantVectorStore

        store = QdrantVectorStore.__new__(QdrantVectorStore)
        store.client = MagicMock()
        store.client.collection_exists.return_value = True
        store.client.search.return_value = []

        with patch("app.services.vector_store.settings") as settings:
            settings.qdrant_collection_prefix = "hr_assistant"
            store.search_vacancy_profiles(query_vector=[0.1] * 4, limit=5)

        call_args = store.client.search.call_args
        query_filter = call_args.kwargs["query_filter"]
        self.assertIsNotNone(query_filter)

    def test_filter_skipped_when_only_vacancies_is_false(self) -> None:
        from app.services.vector_store import QdrantVectorStore

        store = QdrantVectorStore.__new__(QdrantVectorStore)
        store.client = MagicMock()
        store.client.collection_exists.return_value = True
        store.client.search.return_value = []

        with patch("app.services.vector_store.settings") as settings:
            settings.qdrant_collection_prefix = "hr_assistant"
            store.search_vacancy_profiles(
                query_vector=[0.1] * 4, limit=5, only_vacancies=False
            )

        call_args = store.client.search.call_args
        self.assertIsNone(call_args.kwargs["query_filter"])


if __name__ == "__main__":
    unittest.main()
