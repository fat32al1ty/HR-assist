from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserRead


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    beta_key: str = Field(min_length=8, max_length=255)


class LoginStartRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class PasswordResetRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(min_length=8, max_length=128)
    beta_key: str = Field(min_length=8, max_length=255)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
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
    email: EmailStr
    challenge_id: str = Field(min_length=8, max_length=128)
    code: str = Field(min_length=4, max_length=16)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthMessageResponse(BaseModel):
    message: str
