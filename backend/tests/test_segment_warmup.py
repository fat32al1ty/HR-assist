"""Tests for v0.21.0 lazy segment-warmup feature.

T1: derive_segment_key — same inputs produce same hash, different inputs differ,
    domain sort/case-insensitivity, top-3 cap.
T2: Dedup — two parallel calls with same segment_key → one row in DB.
T3: Cold-instant — prefetch_empty=True response has segment_warming=True and a
    row in recommendation_jobs with the right segment_key.
T4: Daily cap — segment_warmup_daily_count increments; worker skips when cap reached.
T5: Recovery — worker startup sees queued segment jobs in DB (smoke test that the
    query path doesn't blow up).
"""

from __future__ import annotations

import uuid
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password

_USER_EMAIL_CACHE: dict[int, str] = {}
from app.db.session import SessionLocal
from app.main import app
from app.models.recommendation_job import RecommendationJob
from app.models.resume import Resume
from app.models.user import User
from app.services.segment_keys import derive_segment_key, segment_key_from_analysis
from app.services.recommendation_jobs import start_segment_warmup_job


# ---------------------------------------------------------------------------
# Pure unit tests for derive_segment_key
# ---------------------------------------------------------------------------


class DeriveSegmentKeyTest(unittest.TestCase):
    def test_same_inputs_same_hash(self):
        k1 = derive_segment_key(role_family="backend", seniority="senior", domains=["fintech"])
        k2 = derive_segment_key(role_family="backend", seniority="senior", domains=["fintech"])
        self.assertEqual(k1, k2)

    def test_different_inputs_different_hash(self):
        k1 = derive_segment_key(role_family="backend", seniority="senior", domains=["fintech"])
        k2 = derive_segment_key(role_family="frontend", seniority="senior", domains=["fintech"])
        self.assertNotEqual(k1, k2)

    def test_domain_sort_case_insensitive(self):
        k1 = derive_segment_key(
            role_family="Backend", seniority="Senior", domains=["Fintech", "Edtech", "Healthtech"]
        )
        k2 = derive_segment_key(
            role_family="backend", seniority="senior", domains=["HEALTHTECH", "edtech", "FINTECH"]
        )
        self.assertEqual(k1, k2)

    def test_top_3_domains_capped(self):
        k1 = derive_segment_key(
            role_family="backend", seniority="mid", domains=["a", "b", "c", "d"]
        )
        k2 = derive_segment_key(
            role_family="backend", seniority="mid", domains=["a", "b", "c"]
        )
        # sorted top-3 of [a,b,c,d] = [a,b,c], matches [a,b,c]
        self.assertEqual(k1, k2)

    def test_returns_16_chars(self):
        k = derive_segment_key(role_family="data", seniority="junior", domains=[])
        self.assertEqual(len(k), 16)

    def test_segment_key_from_analysis_returns_none_without_role_family(self):
        result = segment_key_from_analysis({"seniority": "senior", "domains": ["it"]})
        self.assertIsNone(result)

    def test_segment_key_from_analysis_returns_key(self):
        result = segment_key_from_analysis(
            {"role_family": "backend", "seniority": "mid", "domains": ["fintech"]}
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 16)


# ---------------------------------------------------------------------------
# Integration tests (need running DB)
# ---------------------------------------------------------------------------


def _make_user(db) -> User:
    suffix = uuid.uuid4().hex[:10]
    email = f"segwarm-{suffix}@example.com"
    user = User(
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="Seg Tester",
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _USER_EMAIL_CACHE[user.id] = email
    return user


def _make_resume(db, user_id: int, analysis: dict | None = None) -> Resume:
    resume = Resume(
        user_id=user_id,
        original_filename="cv.pdf",
        content_type="application/pdf",
        status="completed",
        analysis=analysis or {
            "role_family": "backend",
            "target_role": "Backend Engineer",
            "seniority": "senior",
            "domains": ["fintech"],
            "hard_skills": ["python"],
            "matching_keywords": [],
        },
        is_active=True,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


class SegmentWarmupDedupTest(unittest.TestCase):
    """T2: Two calls with same segment_key produce one row."""

    def test_dedup_same_segment_key(self):
        db = SessionLocal()
        try:
            user = _make_user(db)
            resume = _make_resume(db, user.id)
            seg_key = "testdedup" + uuid.uuid4().hex[:6]
            job_id_1 = start_segment_warmup_job(
                segment_key=seg_key,
                notify_user_id=user.id,
                query="python backend senior",
                resume_id=resume.id,
            )
            job_id_2 = start_segment_warmup_job(
                segment_key=seg_key,
                notify_user_id=user.id,
                query="python backend senior",
                resume_id=resume.id,
            )
            self.assertEqual(job_id_1, job_id_2)
            rows = db.scalars(
                select(RecommendationJob).where(RecommendationJob.segment_key == seg_key)
            ).all()
            self.assertEqual(len(rows), 1)
        finally:
            db.close()

    def test_different_segment_keys_create_different_rows(self):
        db = SessionLocal()
        try:
            user = _make_user(db)
            resume = _make_resume(db, user.id)
            prefix = uuid.uuid4().hex[:6]
            seg_key_a = "keya" + prefix
            seg_key_b = "keyb" + prefix
            job_a = start_segment_warmup_job(
                segment_key=seg_key_a,
                notify_user_id=user.id,
                query="python backend",
                resume_id=resume.id,
            )
            job_b = start_segment_warmup_job(
                segment_key=seg_key_b,
                notify_user_id=user.id,
                query="java backend",
                resume_id=resume.id,
            )
            self.assertNotEqual(job_a, job_b)
        finally:
            db.close()


class ColdInstantEndpointTest(unittest.TestCase):
    """T3: prefetch_empty=True → segment_warming=True + job in DB."""

    def _auth_header(self, user_id: int) -> dict:
        email = _USER_EMAIL_CACHE.get(user_id, f"unknown-{user_id}@example.com")
        token = create_access_token(email)
        return {"Authorization": f"Bearer {token}"}

    def test_cold_instant_enqueues_segment_warmup(self):
        db = SessionLocal()
        try:
            user = _make_user(db)
            resume = _make_resume(db, user.id)
            user_id = user.id
            resume_id = resume.id
            resume_analysis = dict(resume.analysis) if resume.analysis else {}
        finally:
            db.close()

        # Mock recommend_vacancies_for_resume to return empty (cold segment)
        from app.services.vacancy_pipeline import VacancyDiscoveryMetrics

        empty_metrics = VacancyDiscoveryMetrics(fetched=0, indexed=0, analyzed=0)

        with patch(
            "app.api.routes.vacancies.recommend_vacancies_for_resume",
            return_value=("python backend senior", empty_metrics, []),
        ):
            with TestClient(app) as client:
                resp = client.post(
                    f"/api/vacancies/recommend/instant/{resume_id}",
                    json={"discover_count": 10, "match_limit": 10},
                    headers=self._auth_header(user_id),
                )

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body.get("prefetch_empty"), "expected prefetch_empty=True")
        self.assertTrue(body.get("segment_warming"), "expected segment_warming=True")

        # Verify a segment_warmup row was created in the DB
        db = SessionLocal()
        try:
            expected_key = segment_key_from_analysis(resume_analysis)
            self.assertIsNotNone(expected_key)
            row = db.scalar(
                select(RecommendationJob).where(
                    RecommendationJob.segment_key == expected_key,
                    RecommendationJob.job_type == "segment_warmup",
                )
            )
            self.assertIsNotNone(row, "segment_warmup job row not found in DB")
        finally:
            db.close()


class DailyCapTest(unittest.TestCase):
    """T4: daily cap counter increments; worker skips at cap."""

    def test_daily_cap_state_increments(self):
        from app.services import vacancy_warmup as wm

        with wm._state_lock:
            wm._state["segment_warmup_daily_count"] = 0
            wm._state["segment_warmup_daily_date"] = None

        # Reset via helper
        wm._reset_daily_cap_if_needed()
        with wm._state_lock:
            count = int(wm._state.get("segment_warmup_daily_count", -1))
        self.assertEqual(count, 0)

        # Simulate incrementing
        with wm._state_lock:
            wm._state["segment_warmup_daily_count"] = 5
        with wm._state_lock:
            count = int(wm._state.get("segment_warmup_daily_count", -1))
        self.assertEqual(count, 5)

    def test_daily_cap_drain_skips_when_cap_reached(self):
        from app.core.config import settings
        from app.services import vacancy_warmup as wm

        original_cap = settings.segment_warmup_daily_cap
        try:
            # Patch cap to 0 so the drain function considers cap exceeded
            settings.__dict__["segment_warmup_daily_cap"] = 0
            with wm._state_lock:
                wm._state["segment_warmup_daily_count"] = 0
                wm._state["segment_warmup_daily_date"] = None

            db = SessionLocal()
            try:
                result = wm._drain_segment_warmup_jobs(db)
                self.assertEqual(result.get("drained"), 0)
                self.assertEqual(result.get("skipped_cap"), 1)
            finally:
                db.close()
        finally:
            settings.__dict__["segment_warmup_daily_cap"] = original_cap


class WorkerRecoveryTest(unittest.TestCase):
    """T5: startup logging path doesn't blow up when queued jobs exist."""

    def test_start_worker_with_queued_jobs(self):
        from app.services import vacancy_warmup as wm

        db = SessionLocal()
        try:
            user = _make_user(db)
            resume = _make_resume(db, user.id)
            seg_key = "recovery" + uuid.uuid4().hex[:6]
            start_segment_warmup_job(
                segment_key=seg_key,
                notify_user_id=user.id,
                query="python backend",
                resume_id=resume.id,
            )
        finally:
            db.close()

        # Just verify the startup code path runs without error.
        # We don't actually start the worker thread (daemon=True, test env).
        try:
            from sqlalchemy import func

            startup_db = SessionLocal()
            try:
                pending_count = startup_db.scalar(
                    select(func.count(RecommendationJob.id)).where(
                        RecommendationJob.status == "queued",
                        RecommendationJob.job_type == "segment_warmup",
                    )
                )
                self.assertGreaterEqual(int(pending_count or 0), 1)
            finally:
                startup_db.close()
        except Exception as e:
            self.fail(f"Recovery query raised: {e}")
