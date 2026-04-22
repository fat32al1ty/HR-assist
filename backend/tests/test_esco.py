"""Phase 2.4a — ESCO lookup + role-distance tests.

Real Postgres per the project convention: seed a handful of rows in
setUp, exercise the service, roll back in tearDown. No mocks for the
DB layer — the lookup helpers rely on ``array_to_string`` and ``ILIKE``
and those must behave against actual Postgres.
"""

from __future__ import annotations

import unittest

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.esco import (
    EscoOccupation,
    EscoOccupationSkill,
    EscoSkill,
    EscoSkillRelation,
)
from app.services.esco import (
    EscoOccupationHit,
    lookup_occupation,
    lookup_skill,
    role_distance,
    skills_for_occupation,
)


class EscoLookupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self._wipe()

        self.python_skill = EscoSkill(
            esco_uri="http://test/skill/python",
            preferred_label_en="Python (programming)",
            preferred_label_ru="Python",
            alt_labels=["питон", "python3", "python programming"],
            reuse_level="sector-specific",
            skill_type="skill/competence",
        )
        self.sql_skill = EscoSkill(
            esco_uri="http://test/skill/sql",
            preferred_label_en="SQL",
            preferred_label_ru="SQL",
            alt_labels=["structured query language", "sql dialects"],
            reuse_level="transversal",
            skill_type="skill/competence",
        )
        self.monitoring_business_skill = EscoSkill(
            esco_uri="http://test/skill/business-monitoring",
            preferred_label_en="monitor business performance",
            preferred_label_ru="мониторинг бизнес-показателей",
            alt_labels=["business monitoring"],
            reuse_level="cross-sector",
            skill_type="skill/competence",
        )

        self.sw_dev = EscoOccupation(
            esco_uri="http://test/occ/software-developer",
            preferred_label_en="software developer",
            preferred_label_ru="разработчик программного обеспечения",
            alt_labels_en=["programmer", "software engineer"],
            alt_labels_ru=["программист", "разработчик по"],
            isco_group="2512",
        )
        self.sre = EscoOccupation(
            esco_uri="http://test/occ/sre",
            preferred_label_en="site reliability engineer",
            preferred_label_ru="инженер по надежности",
            alt_labels_en=["sre", "devops engineer"],
            alt_labels_ru=["sre инженер"],
            isco_group="2519",
        )
        self.lawyer = EscoOccupation(
            esco_uri="http://test/occ/lawyer",
            preferred_label_en="lawyer",
            preferred_label_ru="юрист",
            alt_labels_en=["attorney"],
            alt_labels_ru=["адвокат"],
            isco_group="2611",
        )

        self.db.add_all(
            [
                self.python_skill,
                self.sql_skill,
                self.monitoring_business_skill,
                self.sw_dev,
                self.sre,
                self.lawyer,
            ]
        )
        self.db.commit()

        self.db.add_all(
            [
                EscoOccupationSkill(
                    occupation_id=self.sw_dev.id,
                    skill_id=self.python_skill.id,
                    relation="essential",
                ),
                EscoOccupationSkill(
                    occupation_id=self.sw_dev.id,
                    skill_id=self.sql_skill.id,
                    relation="optional",
                ),
            ]
        )
        self.db.commit()

    def tearDown(self) -> None:
        self._wipe()
        self.db.close()

    def _wipe(self) -> None:
        # Only delete rows under the test URI prefix so real ESCO data
        # (if seeded in this DB) is left untouched.
        self.db.execute(
            delete(EscoOccupationSkill).where(
                EscoOccupationSkill.occupation_id.in_(
                    self.db.query(EscoOccupation.id).filter(
                        EscoOccupation.esco_uri.like("http://test/%")
                    )
                )
            )
        )
        self.db.execute(
            delete(EscoSkillRelation).where(
                EscoSkillRelation.from_id.in_(
                    self.db.query(EscoSkill.id).filter(EscoSkill.esco_uri.like("http://test/%"))
                )
            )
        )
        self.db.execute(
            delete(EscoSkill).where(EscoSkill.esco_uri.like("http://test/skill/%"))
        )
        self.db.execute(
            delete(EscoOccupation).where(EscoOccupation.esco_uri.like("http://test/occ/%"))
        )
        self.db.commit()

    def test_lookup_skill_exact_match_scores_1(self) -> None:
        hits = lookup_skill(self.db, "Python", lang="ru")
        self.assertTrue(hits)
        self.assertEqual(hits[0].preferred_label_en, "Python (programming)")
        self.assertAlmostEqual(hits[0].score, 1.0, places=6)

    def test_lookup_skill_alt_label_hit(self) -> None:
        hits = lookup_skill(self.db, "питон", lang="ru")
        self.assertTrue(hits)
        self.assertEqual(hits[0].esco_uri, "http://test/skill/python")

    def test_lookup_skill_distinguishes_business_monitoring(self) -> None:
        # The whole point of ESCO: the Russian query "мониторинг" resolves
        # to the business-monitoring skill, not the infrastructure one
        # (which doesn't exist in this fixture set on purpose).
        hits = lookup_skill(self.db, "мониторинг бизнес", lang="ru")
        self.assertTrue(hits)
        self.assertEqual(hits[0].esco_uri, "http://test/skill/business-monitoring")

    def test_lookup_occupation_alt_label_hit(self) -> None:
        hits = lookup_occupation(self.db, "sre инженер", lang="ru")
        self.assertTrue(hits)
        self.assertEqual(hits[0].esco_uri, "http://test/occ/sre")

    def test_skills_for_occupation_essential_filter(self) -> None:
        essential = skills_for_occupation(self.db, self.sw_dev.id, relation="essential")
        self.assertEqual(len(essential), 1)
        self.assertEqual(essential[0].preferred_label_en, "Python (programming)")

        all_linked = skills_for_occupation(self.db, self.sw_dev.id, relation="any")
        self.assertEqual(len(all_linked), 2)


class EscoRoleDistanceTest(unittest.TestCase):
    def _hit(self, isco: str | None) -> EscoOccupationHit:
        return EscoOccupationHit(
            occupation_id=1,
            esco_uri="http://test/x",
            preferred_label_en="x",
            preferred_label_ru=None,
            isco_group=isco,
            score=1.0,
        )

    def test_same_isco_is_zero(self) -> None:
        self.assertAlmostEqual(role_distance(self._hit("2512"), self._hit("2512")), 0.0)

    def test_three_digit_prefix_is_quarter(self) -> None:
        self.assertAlmostEqual(role_distance(self._hit("2512"), self._hit("2519")), 0.25)

    def test_two_digit_prefix_is_half(self) -> None:
        # "2521" vs "2512" share "25" — two digits out of four.
        self.assertAlmostEqual(role_distance(self._hit("2512"), self._hit("2521")), 0.5)

    def test_one_digit_prefix_is_three_quarters(self) -> None:
        self.assertAlmostEqual(role_distance(self._hit("2512"), self._hit("2611")), 0.75)

    def test_no_shared_prefix_is_one(self) -> None:
        self.assertAlmostEqual(role_distance(self._hit("2512"), self._hit("5412")), 1.0)

    def test_missing_isco_falls_back_to_half(self) -> None:
        self.assertAlmostEqual(role_distance(self._hit(None), self._hit("2512")), 0.5)

    def test_none_occupation_is_max_distance(self) -> None:
        self.assertAlmostEqual(role_distance(None, self._hit("2512")), 1.0)


if __name__ == "__main__":
    unittest.main()
