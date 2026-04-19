import unittest

from app.services.vacancy_recommendation import _build_deep_scan_queries, _build_discovery_query


class VacancyRecommendationQueryTests(unittest.TestCase):
    def test_build_discovery_query_compacts_role_and_skills(self) -> None:
        analysis = {
            "target_role": "Руководитель мониторинга / Observability / Платформенные сервисы",
            "specialization": "Мониторинг, observability, платформенные и инфраструктурные сервисы",
            "matching_keywords": ["monitoring", "observability", "platform engineering", "zabbix"],
            "hard_skills": ["Prometheus", "VictoriaMetrics", "Grafana"],
        }

        query = _build_discovery_query(analysis)
        self.assertNotIn("/", query)
        self.assertGreater(len(query), 10)
        self.assertLessEqual(len(query.split()), 7)

    def test_deep_scan_queries_include_skill_focus(self) -> None:
        analysis = {
            "target_role": "DevOps Engineer",
            "specialization": "Platform services",
            "matching_keywords": ["observability", "monitoring", "sre", "zabbix"],
            "hard_skills": ["Prometheus", "Grafana", "Kubernetes"],
        }
        base = _build_discovery_query(analysis)
        queries = _build_deep_scan_queries(base, rf_only=True, analysis=analysis)

        self.assertTrue(any("prometheus" in item.lower() for item in queries))
        self.assertTrue(any(item.endswith("Russia") for item in queries))
        self.assertEqual(len(queries), len({item.lower() for item in queries}))


if __name__ == "__main__":
    unittest.main()
