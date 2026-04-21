"""Console-mode email delivery must never leak the OTP code at INFO level.

We previously used `print()` to dump the raw body (which contains the OTP)
straight to stdout. Tests here lock in the new behavior: the INFO log
records only recipient (redacted), subject, and body length — never the
body itself. The raw body remains available at DEBUG for local dev.
"""
from __future__ import annotations

import logging
import unittest

from app.core.config import settings
from app.services.email_delivery import _redact_email, send_email


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class EmailDeliveryLoggingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("auth_email")
        self.capture = _Capture()
        self._previous_level = self.logger.level
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.capture)
        self._previous_mode = settings.auth_email_delivery_mode
        settings.auth_email_delivery_mode = "console"

    def tearDown(self) -> None:
        self.logger.removeHandler(self.capture)
        self.logger.setLevel(self._previous_level)
        settings.auth_email_delivery_mode = self._previous_mode

    def test_redact_email_keeps_first_letter_and_domain(self) -> None:
        self.assertEqual(_redact_email("alice@example.com"), "a***@example.com")
        self.assertEqual(_redact_email("@example.com"), "***@example.com")
        self.assertEqual(_redact_email("nobody"), "***")

    def test_console_mode_info_line_does_not_contain_otp_code(self) -> None:
        otp_code = "482195"
        body = f"Ваш код подтверждения: {otp_code}. Код действует 10 минут."
        send_email(to_email="alice@example.com", subject="Confirm email", body=body)

        info_records = [r for r in self.capture.records if r.levelno == logging.INFO]
        self.assertTrue(info_records, "Expected at least one INFO log line")
        for record in info_records:
            message = record.getMessage()
            self.assertNotIn(otp_code, message)
            self.assertNotIn("Ваш код", message)
        # Contract: redacted recipient, subject, and body length only.
        info_message = info_records[0].getMessage()
        self.assertIn("a***@example.com", info_message)
        self.assertIn("Confirm email", info_message)
        self.assertIn(f"body_len={len(body)}", info_message)

    def test_console_mode_debug_line_contains_full_body(self) -> None:
        otp_code = "913047"
        body = f"Ваш код подтверждения: {otp_code}. Код действует 10 минут."
        send_email(to_email="alice@example.com", subject="Confirm email", body=body)

        debug_records = [r for r in self.capture.records if r.levelno == logging.DEBUG]
        self.assertTrue(debug_records, "Expected a DEBUG log line with the raw body")
        self.assertIn(otp_code, debug_records[0].getMessage())


if __name__ == "__main__":
    unittest.main()
