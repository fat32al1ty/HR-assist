import unittest

from app.services import skill_taxonomy
from app.services.skill_taxonomy import expand_concept, taxonomy_cluster_count


class SkillTaxonomyTest(unittest.TestCase):
    """Phase 1.9 PR B2: taxonomy bridges RU↔EN concept aliases so the
    matcher stops flagging 'планирование' as missing when the resume
    says 'project management'."""

    def setUp(self) -> None:
        skill_taxonomy.reload_taxonomy()

    def test_taxonomy_loads_expected_cluster_count(self) -> None:
        # Plan target: 50-80 clusters. If this drops to zero, YAML is
        # missing or malformed — catch that loudly.
        count = taxonomy_cluster_count()
        self.assertGreaterEqual(count, 40)
        self.assertLessEqual(count, 120)

    def test_expand_returns_symmetric_forms(self) -> None:
        via_ru = expand_concept("планирование")
        via_en = expand_concept("project management")
        self.assertIn("project management", via_ru)
        self.assertIn("планирование", via_en)
        # Forms from both sides collapse to the same cluster.
        self.assertEqual(via_ru, via_en)

    def test_expand_business_process_optimization(self) -> None:
        forms = expand_concept("оптимизация бизнес-процессов")
        self.assertIn("process optimization", forms)
        self.assertIn("process improvement", forms)

    def test_expand_k8s_bridges_kubernetes(self) -> None:
        forms = expand_concept("k8s")
        self.assertIn("kubernetes", forms)
        self.assertIn("кубернетес", forms)

    def test_expand_unknown_phrase_returns_self(self) -> None:
        forms = expand_concept("совершенно уникальный навык 42")
        self.assertEqual(forms, {"совершенно уникальный навык 42"})

    def test_expand_case_and_whitespace_insensitive(self) -> None:
        lower = expand_concept("kubernetes")
        mixed = expand_concept("  Kubernetes  ")
        upper = expand_concept("KUBERNETES")
        self.assertEqual(lower, mixed)
        self.assertEqual(lower, upper)

    def test_expand_empty_input_safe(self) -> None:
        self.assertEqual(expand_concept(""), set())
        self.assertEqual(expand_concept("   "), set())
        self.assertEqual(expand_concept(None), set())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
