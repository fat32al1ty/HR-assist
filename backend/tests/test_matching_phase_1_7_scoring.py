import unittest

from app.services.matching_service import (
    SENIORITY_PENALTY,
    TITLE_BOOST,
    TITLE_BOOST_PARTIAL,
    _has_sufficient_skill_overlap,
    _preferred_title_boost_score,
    _seniority_from_value,
    _seniority_mismatch_penalty,
)


class SkillOverlapFloorTests(unittest.TestCase):
    def test_floor_skipped_when_resume_has_fewer_than_three_skills(self) -> None:
        payload = {"must_have_skills": ["python", "kafka", "postgres"]}
        self.assertTrue(
            _has_sufficient_skill_overlap(
                resume_skills={"java"},
                resume_hard_skills=["Java", "Spring"],
                vacancy_payload=payload,
            )
        )

    def test_floor_skipped_when_vacancy_has_fewer_than_three_required_skills(self) -> None:
        payload = {"must_have_skills": ["python", "kafka"]}
        self.assertTrue(
            _has_sufficient_skill_overlap(
                resume_skills={"java", "spring", "oracle"},
                resume_hard_skills=["Java", "Spring", "Oracle"],
                vacancy_payload=payload,
            )
        )

    def test_floor_drops_when_both_sides_rich_but_zero_overlap(self) -> None:
        payload = {"must_have_skills": ["java", "spring", "oracle", "kafka"]}
        self.assertFalse(
            _has_sufficient_skill_overlap(
                resume_skills={"python", "postgres", "django", "redis"},
                resume_hard_skills=["Python", "Postgres", "Django", "Redis"],
                vacancy_payload=payload,
            )
        )

    def test_floor_passes_with_even_one_shared_skill(self) -> None:
        payload = {"must_have_skills": ["java", "spring", "postgres"]}
        self.assertTrue(
            _has_sufficient_skill_overlap(
                resume_skills={"python", "postgres", "django"},
                resume_hard_skills=["Python", "Postgres", "Django"],
                vacancy_payload=payload,
            )
        )


class SeniorityPenaltyTests(unittest.TestCase):
    def test_rank_lookup_normalizes_substrings(self) -> None:
        self.assertEqual(_seniority_from_value("Senior Backend Engineer"), 3)
        self.assertEqual(_seniority_from_value("Team Lead"), 4)
        self.assertEqual(_seniority_from_value("Middle"), 2)
        self.assertEqual(_seniority_from_value("Principal"), 5)

    def test_rank_lookup_returns_none_for_unknown(self) -> None:
        self.assertIsNone(_seniority_from_value("something"))
        self.assertIsNone(_seniority_from_value(None))

    def test_penalty_applies_when_senior_resume_meets_junior_vacancy(self) -> None:
        delta = _seniority_mismatch_penalty(
            {"seniority": "senior"},
            {"seniority": "junior"},
        )
        self.assertAlmostEqual(delta, -SENIORITY_PENALTY)

    def test_penalty_applies_when_junior_resume_meets_lead_vacancy(self) -> None:
        delta = _seniority_mismatch_penalty(
            {"seniority": "junior"},
            {"seniority": "lead"},
        )
        self.assertAlmostEqual(delta, -SENIORITY_PENALTY)

    def test_no_penalty_for_neighbouring_grades(self) -> None:
        self.assertEqual(
            _seniority_mismatch_penalty({"seniority": "senior"}, {"seniority": "lead"}),
            0.0,
        )
        self.assertEqual(
            _seniority_mismatch_penalty({"seniority": "middle"}, {"seniority": "senior"}),
            0.0,
        )

    def test_no_penalty_when_either_side_missing(self) -> None:
        self.assertEqual(
            _seniority_mismatch_penalty({"seniority": "senior"}, {}),
            0.0,
        )
        self.assertEqual(
            _seniority_mismatch_penalty({}, {"seniority": "junior"}),
            0.0,
        )


class TitleBoostTieredTests(unittest.TestCase):
    def test_substring_match_grants_full_boost(self) -> None:
        self.assertAlmostEqual(
            _preferred_title_boost_score(
                "Senior Platform Engineer",
                ["Platform Engineer"],
            ),
            TITLE_BOOST,
        )

    def test_two_token_overlap_grants_full_boost_without_substring(self) -> None:
        # "platform engineering" vs "Senior Platform Engineer" — substring miss,
        # token overlap on {platform, engineer}=1 after stemming-free tokenisation.
        # So use two distinct tokens that survive normalization.
        score = _preferred_title_boost_score(
            "Senior Platform Engineering Lead",
            ["Platform Engineering"],
        )
        self.assertAlmostEqual(score, TITLE_BOOST)

    def test_single_token_overlap_grants_partial_boost(self) -> None:
        score = _preferred_title_boost_score(
            "Staff Engineer",
            ["Kubernetes Engineer"],
        )
        self.assertAlmostEqual(score, TITLE_BOOST_PARTIAL)

    def test_no_overlap_grants_nothing(self) -> None:
        score = _preferred_title_boost_score(
            "Financial Analyst",
            ["Python Backend"],
        )
        self.assertEqual(score, 0.0)

    def test_stopwords_do_not_count_as_overlap(self) -> None:
        # "for" is a stopword — both sides contain it, but it alone
        # shouldn't trigger a partial boost.
        score = _preferred_title_boost_score(
            "Reviewer for Chemistry Labs",
            ["Accountant for Retail"],
        )
        self.assertEqual(score, 0.0)

    def test_empty_preferred_titles_returns_zero(self) -> None:
        self.assertEqual(_preferred_title_boost_score("Senior Engineer", []), 0.0)

    def test_non_string_title_returns_zero(self) -> None:
        self.assertEqual(_preferred_title_boost_score(None, ["backend"]), 0.0)


if __name__ == "__main__":
    unittest.main()
