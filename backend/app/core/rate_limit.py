from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

AUTH_REGISTER_LIMIT = "10/minute"
AUTH_LOGIN_LIMIT = "20/minute"
AUTH_PASSWORD_RESET_LIMIT = "10/minute"

limiter = Limiter(key_func=get_remote_address, headers_enabled=True)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many requests. Try again later."},
    )
