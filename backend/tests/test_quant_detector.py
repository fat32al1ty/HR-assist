import unittest

from app.services.matching_service import (
    _detect_quantitative_experience_requirement,
    _resume_total_experience_years,
)


class QuantExperienceDetectorTest(unittest.TestCase):
    """Phase 1.9 PR B1: catch year-threshold requirements so 13-year
    seniors stop seeing 'опыт в IT от 3 лет' in the 'не хватает' list."""

    def test_russian_ot_pattern(self) -> None:
        self.assertEqual(_detect_quantitative_experience_requirement("опыт в IT от 3 лет"), 3)
        self.assertEqual(_detect_quantitative_experience_requirement("от 5 лет опыта"), 5)
        self.assertEqual(_detect_quantitative_experience_requirement("от 1 года работы"), 1)
        self.assertEqual(_detect_quantitative_experience_requirement("от 2 года опыта"), 2)

    def test_russian_plus_pattern(self) -> None:
        self.assertEqual(_detect_quantitative_experience_requirement("7+ лет в разработке"), 7)
        self.assertEqual(_detect_quantitative_experience_requirement("3+ года"), 3)

    def test_russian_minimum_pattern(self) -> None:
        self.assertEqual(_detect_quantitative_experience_requirement("минимум 4 года"), 4)
        self.assertEqual(
            _detect_quantitative_experience_requirement("не менее 10 лет в профессии"), 10
        )

    def test_english_years_pattern(self) -> None:
        self.assertEqual(_detect_quantitative_experience_requirement("3 years of experience"), 3)
        self.assertEqual(_detect_quantitative_experience_requirement("5+ years in backend"), 5)
        self.assertEqual(_detect_quantitative_experience_requirement("2 yrs"), 2)

    def test_no_quantifier_returns_none(self) -> None:
        self.assertIsNone(_detect_quantitative_experience_requirement("опыт с Python"))
        self.assertIsNone(_detect_quantitative_experience_requirement("знание SQL"))
        self.assertIsNone(_detect_quantitative_experience_requirement(""))
        self.assertIsNone(_detect_quantitative_experience_requirement(None))  # type: ignore[arg-type]

    def test_unreasonable_values_rejected(self) -> None:
        # Guard against catching random digits unrelated to years.
        self.assertIsNone(_detect_quantitative_experience_requirement("от 0 лет"))
        self.assertIsNone(_detect_quantitative_experience_requirement("от 100 лет опыта"))

    def test_resume_total_experience_years_extraction(self) -> None:
        self.assertEqual(_resume_total_experience_years({"total_experience_years": 13}), 13.0)
        self.assertEqual(_resume_total_experience_years({"total_experience_years": "7.5"}), 7.5)
        self.assertIsNone(_resume_total_experience_years({"total_experience_years": None}))
        self.assertIsNone(_resume_total_experience_years({}))
        self.assertIsNone(_resume_total_experience_years(None))
        self.assertIsNone(_resume_total_experience_years({"total_experience_years": "n/a"}))
        self.assertIsNone(_resume_total_experience_years({"total_experience_years": -2}))


if __name__ == "__main__":
    unittest.main()
