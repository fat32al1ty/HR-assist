from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.config import settings


def normalize_beta_keys() -> set[str]:
    return {item.strip() for item in (settings.beta_tester_keys or "").split(",") if item.strip()}


def is_valid_beta_key(key: str) -> bool:
    if not key:
        return False
    keys = normalize_beta_keys()
    return bool(keys) and key.strip() in keys


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp_code(code: str) -> str:
    secret = settings.jwt_secret_key.encode("utf-8")
    payload = code.strip().encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def verify_otp_code(code: str, expected_hash: str) -> bool:
    actual_hash = hash_otp_code(code)
    return hmac.compare_digest(actual_hash, expected_hash)


def issue_challenge_id() -> str:
    return uuid4().hex


def otp_expiry(minutes: int) -> datetime:
    safe_minutes = max(1, int(minutes))
    return datetime.now(timezone.utc) + timedelta(minutes=safe_minutes)
