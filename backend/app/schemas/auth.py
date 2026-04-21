from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserRead

# Length caps are upper bounds on attacker-controlled strings. An uncapped
# field can be exploited to burn OpenAI quota or blow up a DB row.
EMAIL_MAX = 254  # RFC 5321 total address length
PASSWORD_MAX = 128
FULL_NAME_MAX = 200
BETA_KEY_MAX = 64


class RegisterRequest(BaseModel):
    email: EmailStr = Field(max_length=EMAIL_MAX)
    password: str = Field(min_length=8, max_length=PASSWORD_MAX)
    full_name: str | None = Field(default=None, max_length=FULL_NAME_MAX)
    beta_key: str = Field(min_length=8, max_length=BETA_KEY_MAX)


class LoginStartRequest(BaseModel):
    email: EmailStr = Field(max_length=EMAIL_MAX)
    password: str = Field(min_length=8, max_length=PASSWORD_MAX)


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=EMAIL_MAX)
    password: str = Field(min_length=8, max_length=PASSWORD_MAX)


class PasswordResetRequest(BaseModel):
    email: EmailStr = Field(max_length=EMAIL_MAX)
    new_password: str = Field(min_length=8, max_length=PASSWORD_MAX)
    beta_key: str = Field(min_length=8, max_length=BETA_KEY_MAX)


class VerifyEmailRequest(BaseModel):
    email: EmailStr = Field(max_length=EMAIL_MAX)
    code: str = Field(min_length=4, max_length=16)


class LoginStartResponse(BaseModel):
    challenge_id: str
    requires_code: bool = True
    message: str
    delivery_mode: str = "email"
    debug_code: str | None = None


class RegisterResponse(BaseModel):
    user: UserRead
    message: str
    delivery_mode: str = "email"
    debug_code: str | None = None


class LoginVerifyRequest(BaseModel):
    email: EmailStr = Field(max_length=EMAIL_MAX)
    challenge_id: str = Field(min_length=8, max_length=128)
    code: str = Field(min_length=4, max_length=16)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthMessageResponse(BaseModel):
    message: str
