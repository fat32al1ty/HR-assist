from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import (
    AUTH_LOGIN_LIMIT,
    AUTH_PASSWORD_RESET_LIMIT,
    AUTH_REGISTER_LIMIT,
    limiter,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.repositories.auth_otp_codes import (
    PURPOSE_EMAIL_VERIFY,
    PURPOSE_LOGIN_2FA,
    consume_code,
    create_otp_code,
    get_active_otp_code,
    invalidate_active_codes,
    register_failed_attempt,
)
from app.repositories.user_login_event import record_login_event
from app.repositories.users import (
    create_user,
    get_user_by_email,
    mark_email_verified,
    touch_last_login,
)
from app.schemas.auth import (
    AuthMessageResponse,
    LoginRequest,
    LoginStartRequest,
    LoginStartResponse,
    LoginVerifyRequest,
    PasswordResetRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.user import UserRead
from app.services.auth_security import (
    generate_otp_code,
    hash_otp_code,
    is_valid_beta_key,
    otp_expiry,
    verify_otp_code,
)
from app.services.email_delivery import send_email

router = APIRouter()

# Shared error detail to avoid revealing whether the beta key, the email, or
# the password was the reason for rejection.
GENERIC_AUTH_REJECTION = "Invalid credentials or beta key"


def issue_email_verification_code(*, db: Session, user) -> tuple[str, str]:
    code = generate_otp_code()
    invalidate_active_codes(db, email=user.email, purpose=PURPOSE_EMAIL_VERIFY)
    create_otp_code(
        db,
        user_id=user.id,
        email=user.email,
        purpose=PURPOSE_EMAIL_VERIFY,
        challenge_id=None,
        code_hash=hash_otp_code(code),
        expires_at=otp_expiry(settings.auth_email_code_ttl_minutes),
        max_attempts=settings.auth_code_max_attempts,
    )
    delivery_mode = settings.auth_email_delivery_mode.lower()
    send_email(
        to_email=user.email,
        subject="Подтверждение email для HR Assistant",
        body=f"Ваш код подтверждения: {code}. Код действует {settings.auth_email_code_ttl_minutes} минут.",
    )
    return code, delivery_mode


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(AUTH_REGISTER_LIMIT)
def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    if not is_valid_beta_key(payload.beta_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=GENERIC_AUTH_REJECTION)

    existing = get_user_by_email(db, email=payload.email)
    if existing is not None and existing.email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=GENERIC_AUTH_REJECTION)

    if existing is None:
        user = create_user(
            db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            email_verified=True,
        )
    else:
        existing.hashed_password = hash_password(payload.password)
        existing.full_name = payload.full_name or existing.full_name
        db.add(existing)
        db.commit()
        db.refresh(existing)
        user = mark_email_verified(db, existing)

    return RegisterResponse(
        user=UserRead.model_validate(user),
        message="Account created. Email verification is disabled.",
        delivery_mode="disabled",
        debug_code=None,
    )


@router.post("/verify-email", response_model=UserRead)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> UserRead:
    user = get_user_by_email(db, email=payload.email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User is not found")

    code_row = get_active_otp_code(
        db, email=user.email, purpose=PURPOSE_EMAIL_VERIFY, challenge_id=None
    )
    if code_row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code is invalid or expired",
        )
    if not verify_otp_code(payload.code, code_row.code_hash):
        register_failed_attempt(db, code_row=code_row)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code is invalid"
        )

    consume_code(db, code_row=code_row)
    return mark_email_verified(db, user)


@router.post("/login/start", response_model=LoginStartResponse)
@limiter.limit(AUTH_LOGIN_LIMIT)
def login_start(
    request: Request,
    response: Response,
    payload: LoginStartRequest,
    db: Session = Depends(get_db),
) -> LoginStartResponse:
    user = get_user_by_email(db, email=payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    return LoginStartResponse(
        challenge_id="",
        requires_code=False,
        message="Login code is not required",
        delivery_mode="disabled",
        debug_code=None,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(AUTH_LOGIN_LIMIT)
def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = get_user_by_email(db, email=payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not active")
    touch_last_login(db, user)
    try:
        record_login_event(db, user_id=user.id)
        db.commit()
    except Exception:
        pass
    return TokenResponse(access_token=create_access_token(user.email))


@router.post("/password/reset", response_model=AuthMessageResponse)
@limiter.limit(AUTH_PASSWORD_RESET_LIMIT)
def reset_password(
    request: Request,
    response: Response,
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> AuthMessageResponse:
    if not is_valid_beta_key(payload.beta_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=GENERIC_AUTH_REJECTION)
    user = get_user_by_email(db, email=payload.email)
    if user is None:
        # Swallow the "unknown email" signal — return the same success shape so
        # an attacker can't enumerate accounts via this endpoint.
        return AuthMessageResponse(message="Password updated. You can now sign in.")
    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return AuthMessageResponse(message="Password updated. You can now sign in.")


@router.post("/login/verify", response_model=TokenResponse)
@limiter.limit(AUTH_LOGIN_LIMIT)
def login_verify(
    request: Request,
    response: Response,
    payload: LoginVerifyRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = get_user_by_email(db, email=payload.email)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    code_row = get_active_otp_code(
        db,
        email=user.email,
        purpose=PURPOSE_LOGIN_2FA,
        challenge_id=payload.challenge_id,
    )
    if code_row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Login code is invalid or expired"
        )
    if not verify_otp_code(payload.code, code_row.code_hash):
        register_failed_attempt(db, code_row=code_row)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login code is invalid")

    consume_code(db, code_row=code_row)
    touch_last_login(db, user)
    try:
        record_login_event(db, user_id=user.id)
        db.commit()
    except Exception:
        pass
    return TokenResponse(access_token=create_access_token(user.email))
