"""Phase 2.1 regression tests — stop bag-of-words bridging across domains
via shared Russian filler words.

User dogfood report (2026-04-22): a senior-IT resume surfaced vacancies in
энергосбыт, ценообразование электроэнергии, мониторинг конкурентов,
строительство (контроль работ), digital-агентства, медиа, мониторинг НПА РФ,
и сопровождение процессов ИБ. All passed the bag-of-words requirement matcher
on one shared word (опыт / работы / анализ / мониторинг / контроль / сопровождение /
процессов / организациях). Phase 2.1 adds ``GENERIC_NOISE_TOKENS`` +
``_tokens_meaningfully_overlap`` to require ≥2 content tokens or 1 distinctive
(len ≥ 7) content token before an intersection counts.

These tests lock the fix in at the unit level — if they go green it means
none of the reported garbage requirements bridge to a senior-IT token bag
on filler alone, and the UI will no longer claim the user "has" those skills.
"""

from __future__ import annotations

import unittest

from app.services.matching_service import (
    _matched_resume_skills_for_vacancy,
    _phrase_aliases,
    _requirement_matches_resume,
    _tokenize_rich_text,
)


SENIOR_IT_TOKENS: set[str] = {
    "kubernetes",
    "prometheus",
    "grafana",
    "observability",
    "platform",
    "sre",
    "devops",
    "python",
    "postgresql",
    "terraform",
    "linux",
    "docker",
    "incident",
    "reliability",
    "monitoring",
}
SENIOR_IT_PHRASES: list[str] = [
    "Kubernetes",
    "Prometheus",
    "Grafana",
    "Platform Engineering",
    "Observability",
    "SRE",
    "DevOps",
    "Python",
    "PostgreSQL",
    "Terraform",
    "Incident response",
    "Reliability",
]
SENIOR_IT_HARD_SKILLS: list[str] = [
    "Kubernetes",
    "Prometheus",
    "Grafana",
    "Platform Engineering",
    "Observability",
    "SRE",
    "DevOps",
    "Python",
    "PostgreSQL",
    "Terraform",
    "Incident response",
    "Анализ инцидентов",
    "Мониторинг инфраструктуры",
    "Сопровождение production",
]


def _call_req(requirement: str) -> bool:
    aliases: set[str] = set()
    for phrase in SENIOR_IT_PHRASES:
        aliases.update(_phrase_aliases(phrase))
    return _requirement_matches_resume(
        requirement,
        resume_skill_tokens=SENIOR_IT_TOKENS,
        resume_skill_phrases=SENIOR_IT_PHRASES,
        resume_phrase_aliases=aliases,
        resume_phrase_vectors={},
        embedding_cache={},
        embedding_budget={"calls_left": 0},
    )


class GarbageRequirementsDoNotMatchSeniorITResumeTest(unittest.TestCase):
    """Each of these is copied verbatim from the user's dogfood complaint."""

    def test_energy_retail_does_not_bridge(self) -> None:
        # bridged on "опыт" / "работы" / "организациях" before the fix.
        self.assertFalse(_call_req("Опыт работы в энергосбытовых организациях от 3 лет"))
        self.assertFalse(_call_req("Работа с потребителями на розничном рынке электроэнергии"))

    def test_electricity_pricing_does_not_bridge(self) -> None:
        self.assertFalse(
            _call_req("Понимание процессов ценообразования на оптовом рынке электроэнергии")
        )
        self.assertFalse(_call_req("Знание регулирования тарифов на электроэнергию"))

    def test_competitor_and_customer_analysis_do_not_bridge(self) -> None:
        # bridged on "анализ" / "мониторинг" before the fix.
        self.assertFalse(_call_req("Мониторинг конкурентов"))
        self.assertFalse(_call_req("Анализ поведения клиентов"))
        self.assertFalse(_call_req("Анализ эффективности маркетинговых кампаний"))

    def test_construction_work_does_not_bridge(self) -> None:
        # bridged on "контроль" / "мониторинг" / "работ" before the fix.
        self.assertFalse(_call_req("Контроль строительных работ на объекте"))
        self.assertFalse(_call_req("Мониторинг хода строительных работ"))
        self.assertFalse(_call_req("Опыт работы на строительных объектах"))

    def test_media_and_digital_agency_do_not_bridge(self) -> None:
        self.assertFalse(_call_req("Опыт работы в digital-агентстве"))
        self.assertFalse(_call_req("Опыт работы в медиа"))
        self.assertFalse(_call_req("Опыт ведения рекламных кампаний"))

    def test_npa_monitoring_does_not_bridge(self) -> None:
        # bridged on "мониторинг" before the fix.
        self.assertFalse(_call_req("Мониторинг изменений нормативно-правовых актов РФ"))
        self.assertFalse(_call_req("Отслеживание изменений НПА РФ"))

    def test_infosec_compliance_accompaniment_does_not_bridge(self) -> None:
        # "сопровождение процессов" was THE canonical false-positive — both are
        # filler words. "ИБ"/"информационной безопасности" is the content, and
        # the resume has neither.
        self.assertFalse(_call_req("Сопровождение процессов информационной безопасности"))
        self.assertFalse(_call_req("Сопровождение клиентов на всех этапах сделки"))


class LegitRequirementsStillMatchTest(unittest.TestCase):
    """Regression backstop — the noise filter must not silence real signals."""

    def test_distinctive_single_token_still_matches(self) -> None:
        # "kubernetes" alone is ≥ 7 chars → a single content match is enough.
        self.assertTrue(_call_req("Работа с кластерами Kubernetes в проде"))
        self.assertTrue(_call_req("Observability стек"))

    def test_two_short_content_tokens_still_match(self) -> None:
        # Two short content tokens both present → also passes.
        self.assertTrue(_call_req("SRE + DevOps практики"))

    def test_quantitative_years_still_match(self) -> None:
        # "от N лет" path is answered by total_experience_years at a higher
        # layer; it cannot slip through here because the years context is
        # not provided, but the literal 'python' token is distinctive enough.
        self.assertTrue(_call_req("Python разработка, от 3 лет опыта"))


class MatchedSkillsUIDoesNotLieTest(unittest.TestCase):
    """`_matched_resume_skills_for_vacancy` feeds the 'у вас есть' UI card.
    It used to show 'Анализ инцидентов' as a match for 'Анализ поведения
    клиентов' because both tokenize to include 'анализ'. That was the UI
    lying to the user. Phase 2.1 routes this through the same meaningful-
    overlap filter.
    """

    def _vacancy_tokens(self, *phrases: str) -> set[str]:
        tokens: set[str] = set()
        for phrase in phrases:
            tokens.update(_tokenize_rich_text(phrase))
        return tokens

    def test_ui_does_not_claim_analiz_match_for_customer_behavior(self) -> None:
        vac_tokens = self._vacancy_tokens(
            "Анализ поведения клиентов",
            "Мониторинг конкурентов",
            "Отчеты по маркетинговой эффективности",
        )
        matched = _matched_resume_skills_for_vacancy(SENIOR_IT_HARD_SKILLS, vac_tokens)
        # Garbage matches like "Анализ инцидентов" / "Мониторинг инфраструктуры"
        # / "Сопровождение production" must not appear — they bridged on noise.
        self.assertEqual(matched, [])

    def test_ui_does_not_claim_monitoring_match_for_construction(self) -> None:
        vac_tokens = self._vacancy_tokens(
            "Контроль строительных работ",
            "Мониторинг хода строительных работ",
            "Опыт работы на объектах",
        )
        matched = _matched_resume_skills_for_vacancy(SENIOR_IT_HARD_SKILLS, vac_tokens)
        self.assertEqual(matched, [])

    def test_ui_does_not_claim_accompaniment_match_for_infosec(self) -> None:
        vac_tokens = self._vacancy_tokens(
            "Сопровождение процессов информационной безопасности",
            "Внедрение политик ИБ",
        )
        matched = _matched_resume_skills_for_vacancy(SENIOR_IT_HARD_SKILLS, vac_tokens)
        # Resume has "Сопровождение production" — shares only "сопровождение"
        # (filler). Must not be surfaced as a match.
        self.assertEqual(matched, [])

    def test_ui_does_surface_real_matches(self) -> None:
        # Control: a vacancy that genuinely asks for what the user has.
        vac_tokens = self._vacancy_tokens(
            "Опыт работы с Kubernetes и Prometheus",
            "Observability стек, Grafana",
        )
        matched = _matched_resume_skills_for_vacancy(SENIOR_IT_HARD_SKILLS, vac_tokens)
        lowered = {m.lower() for m in matched}
        self.assertIn("kubernetes", lowered)
        self.assertIn("prometheus", lowered)
        self.assertIn("grafana", lowered)
        self.assertIn("observability", lowered)


if __name__ == "__main__":
    unittest.main()
