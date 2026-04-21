import unittest
import uuid
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import delete

from app.api.routes.auth import GENERIC_AUTH_REJECTION, register
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.auth_otp_code import AuthOtpCode
from app.models.user import User
from app.schemas.auth import RegisterRequest


def _fake_request() -> SimpleNamespace:
    """Stub Request good enough for slowapi's key_func when the limiter is disabled."""
    return SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={},
        scope={"type": "http"},
        state=SimpleNamespace(),
    )


class AuthRegistrationTest(unittest.TestCase):
    """Covers the currently active (relaxed) registration flow.

    The hardened email-verify + login-2FA flow is intentionally disabled in
    `app.api.routes.auth` for the beta. Tests that exercised that flow
    (OTP issuance, verify-email, login/verify) were removed when the flow
    was disabled — reintroduce them alongside re-enabling the hardened path.
    """

    def setUp(self) -> None:
        self.db = SessionLocal()
        self.suffix = uuid.uuid4().hex[:10]
        self.email = f"auth-{self.suffix}@example.com"
        self.original_beta_keys = settings.beta_tester_keys
        settings.beta_tester_keys = "BETA-TEST-KEY"
        self._limiter_was_enabled = limiter.enabled
        limiter.enabled = False

    def tearDown(self) -> None:
        user = self.db.query(User).filter(User.email == self.email).one_or_none()
        if user is not None:
            self.db.execute(delete(AuthOtpCode).where(AuthOtpCode.user_id == user.id))
            self.db.execute(delete(User).where(User.id == user.id))
            self.db.commit()
        settings.beta_tester_keys = self.original_beta_keys
        limiter.enabled = self._limiter_was_enabled
        self.db.close()

    def test_register_requires_beta_key(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            register(
                request=_fake_request(),
                payload=RegisterRequest(
                    email=self.email,
                    password="SuperStrong123",
                    full_name="Test User",
                    beta_key="WRONG-KEY",
                ),
                db=self.db,
            )
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, GENERIC_AUTH_REJECTION)

    def test_register_marks_email_verified(self) -> None:
        response = register(
            request=_fake_request(),
            payload=RegisterRequest(
                email=self.email,
                password="SuperStrong123",
                full_name="Test User",
                beta_key="BETA-TEST-KEY",
            ),
            db=self.db,
        )
        self.assertTrue(response.user.email_verified)
        self.assertEqual(response.delivery_mode, "disabled")
        self.assertIsNone(response.debug_code)

    def test_register_existing_email_matches_wrong_key_response(self) -> None:
        """An attacker must not be able to distinguish 'email taken' from
        'wrong beta key' — both return 403 with the shared error detail."""
        # Seed a verified account for `self.email` first so the second request
        # hits the "existing + verified" branch.
        seeded = User(
            email=self.email,
            hashed_password=hash_password("OriginalPwd999"),
            full_name="Seed User",
            email_verified=True,
        )
        self.db.add(seeded)
        self.db.commit()

        with self.assertRaises(HTTPException) as wrong_key:
            register(
                request=_fake_request(),
                payload=RegisterRequest(
                    email=f"nobody-{self.suffix}@example.com",
                    password="SuperStrong123",
                    full_name="Test User",
                    beta_key="WRONG-KEY",
                ),
                db=self.db,
            )

        with self.assertRaises(HTTPException) as taken_email:
            register(
                request=_fake_request(),
                payload=RegisterRequest(
                    email=self.email,
                    password="SuperStrong123",
                    full_name="Test User",
                    beta_key="BETA-TEST-KEY",
                ),
                db=self.db,
            )

        self.assertEqual(wrong_key.exception.status_code, taken_email.exception.status_code)
        self.assertEqual(wrong_key.exception.detail, taken_email.exception.detail)
        self.assertEqual(wrong_key.exception.status_code, 403)
        self.assertEqual(wrong_key.exception.detail, GENERIC_AUTH_REJECTION)


if __name__ == "__main__":
    unittest.main()
