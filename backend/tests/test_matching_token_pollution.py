"""Hard/soft token separation tests (Phase 1.8 PR #2).

Guards the regression path: generic Russian words from soft_skills/strengths
must not leak into the bag-of-words bag used for requirement-matching.
"""

from __future__ import annotations

import unittest

from app.services.matching_service import (
    _build_resume_skill_set,
    _phrase_aliases,
    _requirement_matches_resume,
)


class BuildResumeSkillSetTest(unittest.TestCase):
    def test_soft_skills_do_not_pollute_bag(self) -> None:
        analysis = {
            "hard_skills": ["Kubernetes", "Prometheus"],
            "soft_skills": ["Лидерство", "Планирование", "Коммуникация"],
        }
        tokens = _build_resume_skill_set(analysis)
        self.assertIn("kubernetes", tokens)
        self.assertIn("prometheus", tokens)
        self.assertNotIn("лидерство", tokens)
        self.assertNotIn("планирование", tokens)
        self.assertNotIn("коммуникация", tokens)

    def test_strengths_do_not_leak_generic_russian_words(self) -> None:
        analysis = {
            "hard_skills": ["Platform Engineering"],
            "strengths": [
                "Сильный профиль в мониторинге и observability",
                "Опыт управления большими командами и подрядчиками",
                "Знание современного стека мониторинга и APM",
            ],
        }
        tokens = _build_resume_skill_set(analysis)
        # Full-phrase hard skills land in the bag via _as_string_set.
        self.assertIn("platform engineering", tokens)
        for generic in ("опыт", "знание", "управления", "сильный", "командами"):
            self.assertNotIn(generic, tokens)

    def test_target_role_and_matching_keywords_still_contribute(self) -> None:
        analysis = {
            "hard_skills": ["Prometheus"],
            "matching_keywords": ["Observability", "SRE"],
            "target_role": "Senior Platform Engineer",
        }
        tokens = _build_resume_skill_set(analysis)
        self.assertIn("prometheus", tokens)
        self.assertIn("observability", tokens)
        self.assertIn("sre", tokens)
        self.assertIn("senior", tokens)
        self.assertIn("platform", tokens)
        self.assertIn("engineer", tokens)


class RequirementMatchesResumeTest(unittest.TestCase):
    """Requirement matching must not bridge on generic Russian words."""

    def _call(self, requirement: str, *, resume_skill_tokens: set[str], phrases: list[str]):
        aliases: set[str] = set()
        for phrase in phrases:
            aliases.update(_phrase_aliases(phrase))
        return _requirement_matches_resume(
            requirement,
            resume_skill_tokens=resume_skill_tokens,
            resume_skill_phrases=phrases,
            resume_phrase_aliases=aliases,
            resume_phrase_vectors={},
            embedding_cache={},
            embedding_budget={"calls_left": 0},
        )

    def test_construction_requirement_does_not_match_it_resume(self) -> None:
        # Senior-IT hard token bag — no "опыт"/"знание" leaked in from strengths.
        tokens = {
            "kubernetes",
            "prometheus",
            "grafana",
            "observability",
            "platform",
            "sre",
            "monitoring",
        }
        phrases = ["Prometheus", "Grafana", "Platform Engineering", "Observability"]
        # Construction vacancy requirements from prod complaint (vacancy 90).
        self.assertFalse(
            self._call(
                "Опыт работы в ремонте или строительстве",
                resume_skill_tokens=tokens,
                phrases=phrases,
            )
        )
        self.assertFalse(
            self._call(
                "Опыт работы с коммерческими сметами",
                resume_skill_tokens=tokens,
                phrases=phrases,
            )
        )
        self.assertFalse(
            self._call(
                "Умение читать дизайн-проекты",
                resume_skill_tokens=tokens,
                phrases=phrases,
            )
        )

    def test_automotive_requirement_does_not_match_it_resume(self) -> None:
        tokens = {
            "kubernetes",
            "prometheus",
            "grafana",
            "observability",
            "platform",
            "sre",
        }
        phrases = ["Prometheus", "Grafana", "Platform Engineering"]
        # Vacancy 17 requirements.
        self.assertFalse(
            self._call(
                "Знание электронных систем автомобиля",
                resume_skill_tokens=tokens,
                phrases=phrases,
            )
        )
        self.assertFalse(
            self._call(
                "Знание устройства автомобиля",
                resume_skill_tokens=tokens,
                phrases=phrases,
            )
        )

    def test_legit_requirement_still_matches_via_hard_tokens(self) -> None:
        tokens = {"prometheus", "grafana", "kubernetes", "observability"}
        phrases = ["Prometheus", "Grafana", "Kubernetes"]
        self.assertTrue(
            self._call(
                "Prometheus, Grafana",
                resume_skill_tokens=tokens,
                phrases=phrases,
            )
        )
        self.assertTrue(
            self._call(
                "Observability stack",
                resume_skill_tokens=tokens,
                phrases=phrases,
            )
        )

    def test_leadership_requirement_still_matches_via_hint_tokens(self) -> None:
        # Team Lead-style requirements match via the LEADERSHIP_HINT_TOKENS path,
        # independent of soft_skills — so leadership detection still works even
        # after we strip soft tokens.
        tokens = {"head", "monitoring"}
        self.assertTrue(
            self._call(
                "team lead experience",
                resume_skill_tokens=tokens,
                phrases=["Head of Monitoring"],
            )
        )


if __name__ == "__main__":
    unittest.main()
