import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.matching_service import match_vacancies_for_resume


class MatchingSourceAndResumeHealTest(unittest.TestCase):
    def _resume(self) -> SimpleNamespace:
        return SimpleNamespace(
            analysis={
                "target_role": "DevOps engineer",
                "specialization": "Observability platform",
                "hard_skills": ["prometheus", "grafana", "kubernetes"],
                "matching_keywords": ["observability", "monitoring", "platform"],
            }
        )

    def _payload(self) -> dict:
        return {
            "is_vacancy": True,
            "title": "DevOps engineer",
            "must_have_skills": ["prometheus", "grafana"],
            "matching_keywords": ["observability", "monitoring"],
            "summary": "observability platform monitoring",
        }

    @patch("app.services.matching_service._lexical_fallback_matches", return_value=[])
    @patch("app.services.matching_service._looks_unlikely_stack", return_value=False)
    @patch("app.services.matching_service._looks_like_listing_page", return_value=False)
    @patch("app.services.matching_service._looks_archived_vacancy_strict", return_value=False)
    @patch("app.services.matching_service._looks_non_vacancy_page", return_value=False)
    @patch("app.services.matching_service._host_allowed_for_matching", return_value=True)
    def test_matching_filters_non_hh_sources(
        self,
        _host_allowed,
        _non_vacancy,
        _archived,
        _listing,
        _unlikely,
        _lexical,
    ) -> None:
        vector_store = MagicMock()
        vector_store.get_resume_vector.return_value = [0.1, 0.2, 0.3]
        vector_store.get_user_preference_vectors.return_value = (None, None)
        vector_store.search_vacancy_profiles.return_value = [
            (1, 0.9, {"vacancy_id": 1, **self._payload()}),
            (2, 0.9, {"vacancy_id": 2, **self._payload()}),
        ]
        vacancy_non_hh = SimpleNamespace(
            id=1,
            status="indexed",
            source="brave",
            source_url="https://hh.ru/vacancy/1",
            title="DevOps engineer",
            company="A",
            location="Moscow",
            raw_text="observability platform monitoring",
        )
        vacancy_hh = SimpleNamespace(
            id=2,
            status="indexed",
            source="hh_api",
            source_url="https://hh.ru/vacancy/2",
            title="DevOps engineer",
            company="B",
            location="Moscow",
            raw_text="observability platform monitoring",
        )

        with (
            patch("app.services.matching_service.get_resume_for_user", return_value=self._resume()),
            patch("app.services.matching_service.get_vector_store", return_value=vector_store),
            patch(
                "app.services.matching_service.recompute_user_preference_profile", return_value=None
            ),
            patch(
                "app.services.matching_service.list_applied_vacancy_ids_for_user", return_value=[]
            ),
            patch("app.services.matching_service.list_disliked_vacancy_ids", return_value=[]),
            patch("app.services.matching_service.list_liked_vacancy_ids", return_value=[]),
            patch("app.services.matching_service.list_seen_vacancy_ids", return_value=set()),
            patch("app.services.matching_service.list_added_skill_texts", return_value=[]),
            patch("app.services.matching_service.list_rejected_skill_texts", return_value=[]),
            patch(
                "app.services.matching_service.get_vacancy_by_id",
                side_effect=lambda db, vacancy_id: (
                    vacancy_non_hh if vacancy_id == 1 else vacancy_hh
                ),
            ),
        ):
            matches = match_vacancies_for_resume(
                SimpleNamespace(), resume_id=13, user_id=3, limit=10
            )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["vacancy_id"], 2)

    @patch("app.services.matching_service._lexical_fallback_matches", return_value=[])
    @patch("app.services.matching_service._looks_unlikely_stack", return_value=False)
    @patch("app.services.matching_service._looks_like_listing_page", return_value=False)
    @patch("app.services.matching_service._looks_archived_vacancy_strict", return_value=False)
    @patch("app.services.matching_service._looks_non_vacancy_page", return_value=False)
    @patch("app.services.matching_service._host_allowed_for_matching", return_value=True)
    def test_matching_rebuilds_resume_profile_when_vector_missing(
        self,
        _host_allowed,
        _non_vacancy,
        _archived,
        _listing,
        _unlikely,
        _lexical,
    ) -> None:
        vector_store = MagicMock()
        vector_store.get_resume_vector.side_effect = [None, [0.1, 0.2, 0.3]]
        vector_store.get_user_preference_vectors.return_value = (None, None)
        vector_store.search_vacancy_profiles.return_value = [
            (2, 0.9, {"vacancy_id": 2, **self._payload()}),
        ]
        vacancy_hh = SimpleNamespace(
            id=2,
            status="indexed",
            source="hh_api",
            source_url="https://hh.ru/vacancy/2",
            title="DevOps engineer",
            company="B",
            location="Moscow",
            raw_text="observability platform monitoring",
        )

        with (
            patch("app.services.matching_service.get_resume_for_user", return_value=self._resume()),
            patch("app.services.matching_service.get_vector_store", return_value=vector_store),
            patch(
                "app.services.matching_service.recompute_user_preference_profile", return_value=None
            ),
            patch(
                "app.services.matching_service.list_applied_vacancy_ids_for_user", return_value=[]
            ),
            patch("app.services.matching_service.list_disliked_vacancy_ids", return_value=[]),
            patch("app.services.matching_service.list_liked_vacancy_ids", return_value=[]),
            patch("app.services.matching_service.list_seen_vacancy_ids", return_value=set()),
            patch("app.services.matching_service.list_added_skill_texts", return_value=[]),
            patch("app.services.matching_service.list_rejected_skill_texts", return_value=[]),
            patch("app.services.matching_service.get_vacancy_by_id", return_value=vacancy_hh),
            patch("app.services.matching_service.persist_resume_profile") as mock_persist,
        ):
            matches = match_vacancies_for_resume(
                SimpleNamespace(), resume_id=13, user_id=3, limit=10
            )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["vacancy_id"], 2)
        mock_persist.assert_called_once()


if __name__ == "__main__":
    unittest.main()
