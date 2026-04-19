import unittest
import uuid
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import delete

from app.api.routes.auth import login_start, login_verify, register, verify_email
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth_otp_code import AuthOtpCode
from app.models.user import User
from app.repositories.auth_otp_codes import PURPOSE_EMAIL_VERIFY, PURPOSE_LOGIN_2FA
from app.schemas.auth import LoginStartRequest, LoginVerifyRequest, RegisterRequest, VerifyEmailRequest


class AuthHardeningFlowTest(unittest.TestCase):
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

    @patch("app.api.routes.auth.send_email")
    @patch("app.api.routes.auth.generate_otp_code")
    def test_register_verify_and_login_with_second_code(
        self,
        mock_generate_otp_code: object,
        _mock_send_email: object,
    ) -> None:
        mock_generate_otp_code.side_effect = ["123456", "654321"]

        user = register(
            RegisterRequest(
                email=self.email,
                password="SuperStrong123",
                full_name="Test User",
                beta_key="BETA-TEST-KEY",
            ),
            db=self.db,
        )
        self.assertFalse(user.email_verified)

        email_verify_row = (
            self.db.query(AuthOtpCode)
            .filter(AuthOtpCode.email == self.email, AuthOtpCode.purpose == PURPOSE_EMAIL_VERIFY)
            .order_by(AuthOtpCode.id.desc())
            .first()
        )
        self.assertIsNotNone(email_verify_row)

        verified = verify_email(VerifyEmailRequest(email=self.email, code="123456"), db=self.db)
        self.assertTrue(verified.email_verified)

        login_start_response = login_start(
            LoginStartRequest(email=self.email, password="SuperStrong123"),
            db=self.db,
        )
        self.assertTrue(login_start_response.challenge_id)

        login_row = (
            self.db.query(AuthOtpCode)
            .filter(AuthOtpCode.email == self.email, AuthOtpCode.purpose == PURPOSE_LOGIN_2FA)
            .order_by(AuthOtpCode.id.desc())
            .first()
        )
        self.assertIsNotNone(login_row)
        self.assertEqual(login_row.challenge_id, login_start_response.challenge_id)

        token = login_verify(
            LoginVerifyRequest(
                email=self.email,
                challenge_id=login_start_response.challenge_id,
                code="654321",
            ),
            db=self.db,
        )
        self.assertTrue(token.access_token)

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


if __name__ == "__main__":
    unittest.main()
