import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.vacancy_pipeline import VacancyDiscoveryMetrics
from app.services.vacancy_recommendation import INTERACTIVE_MAX_DEEP_QUERIES, recommend_vacancies_for_resume


class RecommendationInteractiveLimitsTest(unittest.TestCase):
    @patch("app.services.vacancy_recommendation.get_resume_for_user")
    @patch("app.services.vacancy_recommendation.match_vacancies_for_resume")
    @patch("app.services.vacancy_recommendation.discover_and_index_vacancies")
    def test_interactive_mode_limits_deep_scan_queries(
        self,
        mock_discover,
        mock_match,
        mock_get_resume,
    ) -> None:
        mock_get_resume.return_value = SimpleNamespace(
            analysis={
                "target_role": "DevOps Engineer",
                "specialization": "Observability Platform",
                "matching_keywords": ["observability", "monitoring", "platform", "sre"],
                "hard_skills": ["Prometheus", "Grafana", "Kubernetes", "Zabbix"],
            }
        )
        mock_match.return_value = []
        mock_discover.return_value = SimpleNamespace(metrics=VacancyDiscoveryMetrics())

        query, metrics, matches = recommend_vacancies_for_resume(
            db=SimpleNamespace(),
            resume_id=1,
            user_id=1,
            discover_count=80,
            match_limit=20,
            deep_scan=True,
            rf_only=True,
            use_brave_fallback=False,
            use_prefetched_index=True,
            discover_if_few_matches=True,
            min_prefetched_matches=5,
            max_runtime_seconds=300,
        )

        self.assertIsInstance(query, str)
        self.assertIsNotNone(metrics)
        self.assertIsInstance(matches, list)
        self.assertLessEqual(mock_discover.call_count, INTERACTIVE_MAX_DEEP_QUERIES)


if __name__ == "__main__":
    unittest.main()
