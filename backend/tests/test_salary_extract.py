"""Phase 2.7 — salary extractor + fit classifier tests."""

from __future__ import annotations

import unittest

from app.services.salary_extract import (
    classify_fit,
    extract_for_vacancy,
    extract_from_hh_payload,
    extract_from_text,
)


class SalaryExtractTest(unittest.TestCase):
    def test_hh_payload_reads_salary_range_first(self) -> None:
        payload = {
            "salary": {"from": 100_000, "to": 100_000, "currency": "RUR", "gross": True},
            "salary_range": {
                "from": 180_000,
                "to": 260_000,
                "currency": "RUR",
                "gross": False,
            },
        }
        extracted = extract_from_hh_payload(payload)
        self.assertEqual(extracted.salary_min, 180_000)
        self.assertEqual(extracted.salary_max, 260_000)
        self.assertEqual(extracted.currency, "RUB")
        self.assertFalse(extracted.gross)

    def test_hh_payload_falls_back_to_salary_when_range_missing(self) -> None:
        extracted = extract_from_hh_payload(
            {"salary": {"from": 140_000, "to": None, "currency": "RUR", "gross": True}}
        )
        self.assertEqual(extracted.salary_min, 140_000)
        self.assertIsNone(extracted.salary_max)
        self.assertEqual(extracted.currency, "RUB")
        self.assertTrue(extracted.gross)

    def test_hh_payload_empty_returns_blank(self) -> None:
        extracted = extract_from_hh_payload({})
        self.assertFalse(extracted.is_present())

    def test_text_parser_reads_ruble_band(self) -> None:
        extracted = extract_from_text("Зарплата: от 180 000 до 260 000 ₽ на руки")
        self.assertEqual(extracted.salary_min, 180_000)
        self.assertEqual(extracted.salary_max, 260_000)
        self.assertEqual(extracted.currency, "RUB")

    def test_text_parser_rejects_implausible_values(self) -> None:
        self.assertFalse(extract_from_text("1 ₽ компенсация").is_present())
        self.assertFalse(extract_from_text("Оборот 50 000 000 000 руб").is_present())

    def test_text_parser_ignores_strings_without_currency(self) -> None:
        self.assertFalse(extract_from_text("ID 180000 — не зарплата").is_present())

    def test_extract_for_vacancy_dispatches_on_source(self) -> None:
        payload = {"salary": {"from": 200_000, "to": 300_000, "currency": "RUR"}}
        extracted = extract_for_vacancy("hh_api", payload, raw_text=None)
        self.assertEqual(extracted.salary_min, 200_000)

        extracted = extract_for_vacancy(
            "superjob_public",
            {"page": 1},
            raw_text="зарплата 90 000 ₽",
        )
        self.assertEqual(extracted.salary_min, 90_000)


class ClassifyFitTest(unittest.TestCase):
    def test_match_when_mid_within_expectation(self) -> None:
        fit, penalty = classify_fit(
            220_000,
            expected_min=180_000,
            expected_max=260_000,
            currency="RUB",
            expected_currency="RUB",
        )
        self.assertEqual(fit, "match")
        self.assertEqual(penalty, 0.0)

    def test_below_applies_proportional_penalty(self) -> None:
        fit, penalty = classify_fit(
            100_000,
            expected_min=200_000,
            expected_max=300_000,
            currency="RUB",
            expected_currency="RUB",
        )
        self.assertEqual(fit, "below")
        self.assertGreater(penalty, 0.0)
        self.assertLessEqual(penalty, 0.25)

    def test_above_only_penalised_past_1_5x(self) -> None:
        fit, _ = classify_fit(
            310_000,
            expected_min=200_000,
            expected_max=300_000,
            currency="RUB",
            expected_currency="RUB",
        )
        self.assertEqual(fit, "match")
        fit, penalty = classify_fit(
            520_000,
            expected_min=200_000,
            expected_max=300_000,
            currency="RUB",
            expected_currency="RUB",
        )
        self.assertEqual(fit, "above")
        self.assertGreater(penalty, 0.0)

    def test_unknown_when_currency_mismatch(self) -> None:
        fit, _ = classify_fit(
            200_000,
            expected_min=180_000,
            expected_max=260_000,
            currency="USD",
            expected_currency="RUB",
        )
        self.assertEqual(fit, "unknown")

    def test_unknown_when_no_expectation(self) -> None:
        fit, _ = classify_fit(
            200_000,
            expected_min=None,
            expected_max=None,
            currency="RUB",
            expected_currency="RUB",
        )
        self.assertEqual(fit, "unknown")


if __name__ == "__main__":
    unittest.main()
