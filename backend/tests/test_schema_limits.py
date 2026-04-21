"""Regression: reject over-cap strings at the schema layer (422), not downstream."""
from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.schemas.auth import (
    BETA_KEY_MAX,
    EMAIL_MAX,
    FULL_NAME_MAX,
    PASSWORD_MAX,
    LoginRequest,
    LoginStartRequest,
    LoginVerifyRequest,
    PasswordResetRequest,
    RegisterRequest,
    VerifyEmailRequest,
)
from app.schemas.vacancy import VacancyDiscoverRequest


def _overlong(count: int) -> str:
    return "a" * count


class AuthSchemaLengthCapsTest(unittest.TestCase):
    def test_register_rejects_overlong_full_name(self) -> None:
        with self.assertRaises(ValidationError):
            RegisterRequest(
                email="ok@example.com",
                password="SuperStrong123",
                full_name=_overlong(FULL_NAME_MAX + 1),
                beta_key="BETA-KEY",
            )

    def test_register_rejects_overlong_beta_key(self) -> None:
        with self.assertRaises(ValidationError):
            RegisterRequest(
                email="ok@example.com",
                password="SuperStrong123",
                full_name="Ok",
                beta_key=_overlong(BETA_KEY_MAX + 1),
            )

    def test_register_rejects_overlong_password(self) -> None:
        with self.assertRaises(ValidationError):
            RegisterRequest(
                email="ok@example.com",
                password=_overlong(PASSWORD_MAX + 1),
                full_name="Ok",
                beta_key="BETA-KEY",
            )

    def test_register_rejects_overlong_email_local(self) -> None:
        # 240-char local part + '@example.com' easily exceeds 254.
        with self.assertRaises(ValidationError):
            RegisterRequest(
                email=f"{_overlong(EMAIL_MAX)}@example.com",
                password="SuperStrong123",
                full_name="Ok",
                beta_key="BETA-KEY",
            )

    def test_login_schemas_cap_email(self) -> None:
        long_email = f"{_overlong(EMAIL_MAX)}@example.com"
        for cls in (LoginRequest, LoginStartRequest):
            with self.assertRaises(ValidationError):
                cls(email=long_email, password="SuperStrong123")

    def test_password_reset_caps_beta_key(self) -> None:
        with self.assertRaises(ValidationError):
            PasswordResetRequest(
                email="ok@example.com",
                new_password="SuperStrong123",
                beta_key=_overlong(BETA_KEY_MAX + 1),
            )

    def test_verify_email_caps_code(self) -> None:
        with self.assertRaises(ValidationError):
            VerifyEmailRequest(email="ok@example.com", code=_overlong(17))

    def test_login_verify_caps_challenge_id(self) -> None:
        with self.assertRaises(ValidationError):
            LoginVerifyRequest(
                email="ok@example.com",
                challenge_id=_overlong(129),
                code="1234",
            )


class VacancySchemaLengthCapsTest(unittest.TestCase):
    def test_discover_caps_query(self) -> None:
        # query is capped at 300 chars; 301 must be rejected.
        with self.assertRaises(ValidationError):
            VacancyDiscoverRequest(query=_overlong(301))


if __name__ == "__main__":
    unittest.main()
