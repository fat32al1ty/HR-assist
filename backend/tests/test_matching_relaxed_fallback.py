import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.matching_service import match_vacancies_for_resume


class MatchingRelaxedFallbackTest(unittest.TestCase):
    def test_relaxed_fallback_returns_candidates_when_strict_empty(self) -> None:
        resume = SimpleNamespace(
            analysis={
                "target_role": "Observability Platform Lead",
                "specialization": "Monitoring platform services",
                "hard_skills": ["zabbix", "prometheus", "grafana"],
                "matching_keywords": ["observability", "monitoring", "platform"],
            }
        )
        vector_store = MagicMock()
        vector_store.get_resume_vector.return_value = [0.1, 0.2, 0.3]
        vector_store.get_user_preference_vectors.return_value = (None, None)
        # Semantic score must drop below MAYBE_MATCH_THRESHOLD (0.45) for
        # the relaxed-fallback path to fire; at 0.46 the item would now be
        # classified as a "maybe" match and skip relaxed fallback entirely.
        vector_store.search_vacancy_profiles.return_value = [
            (
                101,
                0.42,
                {
                    "vacancy_id": 101,
                    "is_vacancy": True,
                    "title": "Platform reliability engineer",
                    "matching_keywords": ["platform", "monitoring"],
                    "must_have_skills": ["prometheus"],
                    "summary": "monitoring platform observability",
                },
            )
        ]
        vacancy = SimpleNamespace(
            id=101,
            status="indexed",
            source="hh_api",
            source_url="https://hh.ru/vacancy/101",
            title="Platform reliability engineer",
            company="Acme",
            location="Moscow",
            raw_text="monitoring platform observability",
        )

        with (
            patch("app.services.matching_service.get_resume_for_user", return_value=resume),
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
            patch("app.services.matching_service.get_vacancy_by_id", return_value=vacancy),
            patch("app.services.matching_service._host_allowed_for_matching", return_value=True),
            patch("app.services.matching_service._looks_non_vacancy_page", return_value=False),
            patch(
                "app.services.matching_service._looks_archived_vacancy_strict", return_value=False
            ),
            patch("app.services.matching_service._looks_like_listing_page", return_value=False),
            patch("app.services.matching_service._looks_unlikely_stack", return_value=False),
            patch("app.services.matching_service._lexical_fallback_matches", return_value=[]),
        ):
            matches = match_vacancies_for_resume(
                SimpleNamespace(), resume_id=13, user_id=3, limit=10
            )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["vacancy_id"], 101)
        self.assertEqual(matches[0]["profile"].get("fallback_tier"), "relaxed")


if __name__ == "__main__":
    unittest.main()
