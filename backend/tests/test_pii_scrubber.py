"""Tests for pii_scrubber module (§1 and §7 of Level A PII minimization)."""

import unittest

from app.services.pii_scrubber import mask_email, scrub_pii


class ScrubEmailTest(unittest.TestCase):
    def test_russian_email_scrubbed(self):
        text = "Связь: ivan.petrov@yandex.ru по любым вопросам"
        cleaned, counters = scrub_pii(text)
        self.assertNotIn("ivan.petrov@yandex.ru", cleaned)
        self.assertIn("[EMAIL]", cleaned)
        self.assertEqual(counters["emails"], 1)

    def test_gmail_scrubbed(self):
        text = "Email: test.user+tag@gmail.com"
        cleaned, counters = scrub_pii(text)
        self.assertNotIn("test.user+tag@gmail.com", cleaned)
        self.assertEqual(counters["emails"], 1)


class ScrubPhoneTest(unittest.TestCase):
    def test_russian_mobile_plus7(self):
        text = "Телефон: +7 (916) 123-45-67"
        cleaned, counters = scrub_pii(text)
        self.assertNotIn("916", cleaned)
        self.assertIn("[PHONE]", cleaned)
        self.assertEqual(counters["phones"], 1)

    def test_russian_mobile_8(self):
        text = "Моб: 8(495)123-45-67"
        cleaned, counters = scrub_pii(text)
        self.assertIn("[PHONE]", cleaned)
        self.assertEqual(counters["phones"], 1)

    def test_international_phone(self):
        text = "Tel: +49 30 12345678"
        cleaned, counters = scrub_pii(text)
        self.assertIn("[PHONE]", cleaned)
        self.assertEqual(counters["phones"], 1)


class ScrubUrlTest(unittest.TestCase):
    def test_https_url_scrubbed(self):
        text = "Профиль: https://linkedin.com/in/ivan-petrov-dev"
        cleaned, counters = scrub_pii(text)
        self.assertNotIn("linkedin.com/in/ivan-petrov-dev", cleaned)
        self.assertIn("[URL]", cleaned)
        self.assertEqual(counters["urls"], 1)

    def test_vk_bare_url_scrubbed(self):
        text = "VK: vk.com/ivan123"
        cleaned, counters = scrub_pii(text)
        self.assertIn("[URL]", cleaned)
        self.assertEqual(counters["urls"], 1)

    def test_github_bare_url_scrubbed(self):
        text = "GitHub: github.com/ivanpetrov"
        cleaned, counters = scrub_pii(text)
        self.assertIn("[URL]", cleaned)
        self.assertEqual(counters["urls"], 1)

    def test_telegram_scrubbed(self):
        text = "TG: t.me/myhandle"
        cleaned, counters = scrub_pii(text)
        self.assertIn("[URL]", cleaned)
        self.assertEqual(counters["urls"], 1)


class ScrubNameTest(unittest.TestCase):
    def test_three_cyrillic_tokens_in_header(self):
        text = "Иванов Иван Иванович\n\nОпыт работы: 5 лет Python"
        cleaned, counters = scrub_pii(text)
        self.assertNotIn("Иванов Иван Иванович", cleaned)
        self.assertIn("[NAME]", cleaned)
        self.assertEqual(counters["names"], 1)

    def test_fio_line_scrubbed(self):
        text = "ФИО: Иван Петров\nДолжность: Backend Engineer"
        cleaned, counters = scrub_pii(text)
        self.assertIn("[NAME]", cleaned)
        self.assertNotIn("Иван Петров", cleaned)
        self.assertGreaterEqual(counters["names"], 1)

    def test_imya_line_scrubbed(self):
        text = "Имя: Мария Сидорова\nНавыки: Python, Django"
        cleaned, counters = scrub_pii(text)
        self.assertIn("[NAME]", cleaned)
        self.assertGreaterEqual(counters["names"], 1)


class NoFalsePositivesTest(unittest.TestCase):
    def test_postgresql_not_scrubbed(self):
        text = "Навыки: PostgreSQL, Redis, Apache Kafka, React, Docker"
        cleaned, counters = scrub_pii(text)
        self.assertIn("PostgreSQL", cleaned)
        self.assertIn("Apache Kafka", cleaned)
        self.assertIn("React", cleaned)
        self.assertEqual(counters["names"], 0)

    def test_company_name_not_scrubbed(self):
        text = "Работал в: Яндекс, Сбер, VK\nНавыки: Go, Rust"
        cleaned, counters = scrub_pii(text)
        self.assertEqual(counters["emails"], 0)
        self.assertEqual(counters["phones"], 0)

    def test_three_cyrillic_tokens_mid_line_not_scrubbed(self):
        # Employer name embedded in a longer experience line should NOT match —
        # the three-token pattern is anchored to full-line matches only.
        text = "Опыт: работал в Сбер Банк Технологии с 2020 по 2023 год"
        cleaned, counters = scrub_pii(text)
        self.assertIn("Сбер Банк Технологии", cleaned)
        self.assertEqual(counters["names"], 0)

    def test_counters_match_inputs(self):
        text = "Email: a@b.com и c@d.org, тел +7 916 111-22-33, github.com/user"
        cleaned, counters = scrub_pii(text)
        self.assertEqual(counters["emails"], 2)
        self.assertEqual(counters["phones"], 1)
        self.assertEqual(counters["urls"], 1)


class MaskEmailTest(unittest.TestCase):
    def test_standard_mask(self):
        self.assertEqual(mask_email("jane.doe@example.com"), "j***@e***.com")

    def test_short_local(self):
        result = mask_email("a@b.com")
        self.assertIn("***", result)
        self.assertTrue(result.startswith("a***"))

    def test_no_at_sign(self):
        self.assertEqual(mask_email("notanemail"), "***")

    def test_subdomain_preserved(self):
        result = mask_email("user@mail.example.co.uk")
        self.assertTrue(result.endswith(".example.co.uk"))


if __name__ == "__main__":
    unittest.main()
