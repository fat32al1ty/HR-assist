import unittest
import uuid

from fastapi import HTTPException
from sqlalchemy import delete

from app.api.routes.auth import register
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth_otp_code import AuthOtpCode
from app.models.user import User
from app.schemas.auth import RegisterRequest


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

    def tearDown(self) -> None:
        user = self.db.query(User).filter(User.email == self.email).one_or_none()
        if user is not None:
            self.db.execute(delete(AuthOtpCode).where(AuthOtpCode.user_id == user.id))
            self.db.execute(delete(User).where(User.id == user.id))
            self.db.commit()
        settings.beta_tester_keys = self.original_beta_keys
        self.db.close()

    def test_register_requires_beta_key(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            register(
                RegisterRequest(
                    email=self.email,
                    password="SuperStrong123",
                    full_name="Test User",
                    beta_key="WRONG-KEY",
                ),
                db=self.db,
            )
        self.assertEqual(raised.exception.status_code, 403)

    def test_register_marks_email_verified(self) -> None:
        response = register(
            RegisterRequest(
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


if __name__ == "__main__":
    unittest.main()
