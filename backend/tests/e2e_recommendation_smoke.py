import os
import sys
import time
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.user import User


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
SMOKE_TIMEOUT_SECONDS = int(os.getenv("SMOKE_TIMEOUT_SECONDS", "90"))
SMOKE_POLL_INTERVAL_SECONDS = float(os.getenv("SMOKE_POLL_INTERVAL_SECONDS", "2"))


@dataclass
class SmokeContext:
    user_id: int | None = None
    resume_id: int | None = None
    email: str | None = None


def _request(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, f"{API_BASE_URL}{path}", **kwargs)
    return response


def _create_auth_user(client: httpx.Client, ctx: SmokeContext) -> tuple[str, int]:
    suffix = uuid.uuid4().hex[:10]
    email = f"autotest-{suffix}@example.com"
    password = "StrongPass123!"
    register_payload = {"email": email, "password": password, "full_name": "Autotest User"}
    register_response = _request(client, "POST", "/api/auth/register", json=register_payload)
    if register_response.status_code not in (201, 409):
        raise RuntimeError(
            f"Register failed: {register_response.status_code} {register_response.text}"
        )

    login_response = _request(
        client,
        "POST",
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    if login_response.status_code != 200:
        raise RuntimeError(f"Login failed: {login_response.status_code} {login_response.text}")
    token = login_response.json()["access_token"]

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise RuntimeError("Failed to resolve user after registration")
        ctx.user_id = int(user.id)
        ctx.email = email
    finally:
        db.close()
    return token, int(ctx.user_id)


def _create_completed_resume_for_user(user_id: int, ctx: SmokeContext) -> int:
    db = SessionLocal()
    try:
        resume = Resume(
            user_id=user_id,
            original_filename="smoke-resume.pdf",
            content_type="application/pdf",
            storage_path=f"/tmp/smoke-{uuid.uuid4().hex}.pdf",
            status="completed",
            analysis={
                "target_role": "Backend Engineer",
                "specialization": "Platform services",
                "hard_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "matching_keywords": ["python", "backend", "fastapi", "platform"],
            },
            error_message=None,
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        ctx.resume_id = int(resume.id)
        return int(resume.id)
    finally:
        db.close()


def _cleanup(ctx: SmokeContext) -> None:
    if ctx.user_id is None:
        return
    db = SessionLocal()
    try:
        if ctx.resume_id is not None:
            db.execute(delete(Resume).where(Resume.id == ctx.resume_id))
        db.execute(delete(User).where(User.id == ctx.user_id))
        db.commit()
    finally:
        db.close()


def run_smoke() -> None:
    ctx = SmokeContext()
    client = httpx.Client(timeout=30)
    try:
        token, user_id = _create_auth_user(client, ctx)
        resume_id = _create_completed_resume_for_user(user_id, ctx)
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "discover_count": 5,
            "match_limit": 5,
            "deep_scan": False,
            "rf_only": True,
            "use_brave_fallback": False,
            "use_prefetched_index": True,
            "discover_if_few_matches": False,
            "min_prefetched_matches": 1,
        }
        start_response = _request(
            client,
            "POST",
            f"/api/vacancies/recommend/start/{resume_id}",
            headers=headers,
            json=payload,
        )
        if start_response.status_code != 200:
            raise RuntimeError(
                f"Start recommendation failed: {start_response.status_code} {start_response.text}"
            )

        job_id = start_response.json()["job_id"]
        deadline = time.time() + SMOKE_TIMEOUT_SECONDS
        final_status = None
        final_payload = None

        while time.time() < deadline:
            status_response = _request(
                client,
                "GET",
                f"/api/vacancies/recommend/status/{job_id}",
                headers=headers,
            )
            if status_response.status_code != 200:
                raise RuntimeError(
                    f"Polling failed: {status_response.status_code} {status_response.text}"
                )
            status_payload = status_response.json()
            status = status_payload.get("status")
            stage = status_payload.get("stage")
            progress = status_payload.get("progress")
            print(f"[smoke] job={job_id} status={status} stage={stage} progress={progress}")
            if status in {"completed", "failed"}:
                final_status = status
                final_payload = status_payload
                break
            time.sleep(SMOKE_POLL_INTERVAL_SECONDS)

        if final_status is None:
            raise RuntimeError(
                f"Recommendation job timeout after {SMOKE_TIMEOUT_SECONDS}s (job={job_id})"
            )
        if final_status != "completed":
            error_message = (final_payload or {}).get("error_message") or "Unknown failure"
            raise RuntimeError(f"Recommendation job failed (job={job_id}): {error_message}")

        matches_count = len((final_payload or {}).get("matches") or [])
        print(f"[smoke] PASS job={job_id} completed, matches={matches_count}")
    finally:
        client.close()
        _cleanup(ctx)


if __name__ == "__main__":
    try:
        run_smoke()
    except Exception as error:
        print(f"[smoke] FAIL: {error}", file=sys.stderr)
        sys.exit(1)
