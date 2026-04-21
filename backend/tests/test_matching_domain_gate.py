"""Domain compatibility gate tests (Phase 1.8 PR #1)."""

from __future__ import annotations

import unittest

from app.services.matching_service import _has_domain_compatibility


class DomainCompatibilityTest(unittest.TestCase):
    def test_empty_domains_on_either_side_passes(self) -> None:
        self.assertTrue(_has_domain_compatibility({}, {}))
        self.assertTrue(_has_domain_compatibility({"domains": []}, {"domains": []}))
        self.assertTrue(_has_domain_compatibility({"domains": ["IT"]}, {"domains": []}))
        self.assertTrue(_has_domain_compatibility({"domains": []}, {"domains": ["Ремонт"]}))

    def test_none_analysis_passes(self) -> None:
        self.assertTrue(_has_domain_compatibility(None, {"domains": ["Ремонт"]}))
        self.assertTrue(_has_domain_compatibility({"domains": ["SRE"]}, None))

    def test_direct_token_overlap_passes(self) -> None:
        # Banks ↔ Banks → direct overlap passes even though bank is non-IT marker-free.
        self.assertTrue(
            _has_domain_compatibility(
                {"domains": ["Финансовый сектор", "Банки"]},
                {"domains": ["Банки", "Финтех"]},
            )
        )

    def test_resume_it_vs_vacancy_it_passes_without_overlap(self) -> None:
        # No direct token overlap, but both are IT → pass.
        self.assertTrue(
            _has_domain_compatibility(
                {"domains": ["Platform Services", "Observability"]},
                {"domains": ["SRE", "DevOps", "Cloud"]},
            )
        )

    def test_senior_it_vs_construction_drops(self) -> None:
        # Matches prod complaint: senior IT resume ↔ construction/estimator vacancy.
        self.assertFalse(
            _has_domain_compatibility(
                {
                    "domains": [
                        "IT Infrastructure Monitoring",
                        "Platform Services",
                        "Финансовый сектор",
                    ]
                },
                {"domains": ["Ремонт", "Строительство", "Сметное дело"]},
            )
        )

    def test_senior_it_vs_automotive_drops(self) -> None:
        self.assertFalse(
            _has_domain_compatibility(
                {"domains": ["Platform Services", "Observability", "Банки"]},
                {"domains": ["Автомобилестроение", "Электронные системы автомобиля"]},
            )
        )

    def test_legal_vacancy_drops_for_it_resume(self) -> None:
        self.assertFalse(
            _has_domain_compatibility(
                {"domains": ["SRE", "DevOps"]},
                {"domains": ["Юридическая практика", "Адвокатура"]},
            )
        )

    def test_non_it_resume_vs_non_it_vacancy_passes(self) -> None:
        # Construction resume onto construction vacancy — resume isn't IT, so the gate
        # has nothing to enforce and passes.
        self.assertTrue(
            _has_domain_compatibility(
                {"domains": ["Строительство", "Отделка"]},
                {"domains": ["Ремонт", "Дизайн-проекты"]},
            )
        )

    def test_ambiguous_resume_passes(self) -> None:
        # Resume with no IT markers at all → no evidence to enforce mismatch.
        self.assertTrue(
            _has_domain_compatibility(
                {"domains": ["Консалтинг", "Управление проектами"]},
                {"domains": ["Автомобилестроение"]},
            )
        )

    def test_domains_not_list_is_safe(self) -> None:
        self.assertTrue(_has_domain_compatibility({"domains": "SRE"}, {"domains": ["SRE"]}))
        self.assertTrue(_has_domain_compatibility({"domains": ["SRE"]}, {"domains": "Ремонт"}))


if __name__ == "__main__":
    unittest.main()
