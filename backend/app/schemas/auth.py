from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    beta_key: str = Field(min_length=8, max_length=255)


class LoginStartRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=16)


class LoginStartResponse(BaseModel):
    challenge_id: str
    requires_code: bool = True
    message: str


class LoginVerifyRequest(BaseModel):
    email: EmailStr
    challenge_id: str = Field(min_length=8, max_length=128)
    code: str = Field(min_length=4, max_length=16)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
