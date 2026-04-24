"""Integration tests for GET /api/admin/jobs/{job_id}/funnel.

Covers the waterfall response contract that admin UI depends on:
- 403 for non-admin callers, 404 for unknown jobs
- Shape: stages/drops/matcher_stages as lists of {key,label,value,kind}, scalar
  summary counters (shown_to_user, fetched_raw, total_drops, residual)
- Values reflect the persisted RecommendationJob.metrics JSON blob
- Residual stays non-negative (the waterfall invariant)
"""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.recommendation_job import RecommendationJob
from app.models.resume import Resume
from app.models.user import User


def _make_user(db, email: str, is_admin: bool = False) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("TestPass123"),
        full_name="Funnel Test",
        is_active=True,
        email_verified=True,
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(email: str) -> dict[str, str]:
    token = create_access_token(subject=email)
    return {"Authorization": f"Bearer {token}"}


class AdminFunnelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.user_email = f"funnel-user-{suffix}@example.com"
        self.admin_email = f"funnel-admin-{suffix}@example.com"
        self.user = _make_user(self.db, self.user_email, is_admin=False)
        self.admin = _make_user(self.db, self.admin_email, is_admin=True)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="resume.pdf",
            content_type="application/pdf",
            status="completed",
            analysis={"target_role": "Python-разработчик"},
        )
        self.db.add(self.resume)
        self.db.commit()
        self.db.refresh(self.resume)

        self.job_id = str(uuid.uuid4())
        self.metrics = {
            "hh_fetched_raw": 1500,
            "fetched": 1200,
            "prefiltered": 900,
            "analyzed": 700,
            "indexed": 650,
            "matcher_recall_count": 300,
            "search_dedup_skipped": 100,
            "search_strict_rejected": 200,
            "enrich_failed": 50,
            "already_indexed_skipped": 40,
            "filtered_host_not_allowed": 30,
            "filtered_non_rf": 20,
            "filtered_non_vacancy_page": 15,
            "filtered_archived": 10,
            "filtered_listing": 5,
            "filtered_non_vacancy_llm": 12,
            "failed": 7,
            "skipped_parse_errors": 3,
            "hard_filter_drop_work_format": 8,
            "hard_filter_drop_geo": 9,
            "hard_filter_drop_no_skill_overlap": 11,
            "hard_filter_drop_domain_mismatch": 6,
            "archived_at_match_time": 2,
            "matcher_drop_listing_page": 1,
            "matcher_drop_non_vacancy_page": 1,
            "matcher_drop_host_not_allowed": 1,
            "matcher_drop_unlikely_stack": 1,
            "matcher_drop_business_role": 1,
            "matcher_drop_hard_non_it": 1,
            "matcher_drop_dedupe": 4,
            "matcher_drop_mmr_dedupe": 3,
            "matcher_runs_total": 2,
            "seniority_penalty_applied": 12,
            "title_boost_applied": 8,
        }
        self.matches_payload = [
            {"vacancy_id": i, "score": 0.9 - i * 0.01} for i in range(20)
        ]
        job = RecommendationJob(
            id=self.job_id,
            user_id=self.user.id,
            resume_id=self.resume.id,
            status="completed",
            stage="finished",
            progress=100,
            query="Python разработчик Москва",
            metrics=self.metrics,
            matches=self.matches_payload,
        )
        self.db.add(job)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.execute(delete(RecommendationJob).where(RecommendationJob.id == self.job_id))
        self.db.execute(delete(Resume).where(Resume.id == self.resume.id))
        for email in (self.user_email, self.admin_email):
            u = self.db.query(User).filter(User.email == email).one_or_none()
            if u:
                self.db.execute(delete(User).where(User.id == u.id))
        self.db.commit()
        self.db.close()

    def test_funnel_requires_admin(self) -> None:
        resp = self.client.get(
            f"/api/admin/jobs/{self.job_id}/funnel",
            headers=_auth_header(self.user_email),
        )
        self.assertEqual(resp.status_code, 403)

    def test_funnel_unknown_job_returns_404(self) -> None:
        resp = self.client.get(
            "/api/admin/jobs/no-such-job-id/funnel",
            headers=_auth_header(self.admin_email),
        )
        self.assertEqual(resp.status_code, 404)

    def test_funnel_shape_for_completed_job(self) -> None:
        resp = self.client.get(
            f"/api/admin/jobs/{self.job_id}/funnel",
            headers=_auth_header(self.admin_email),
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()

        for field in (
            "job_id",
            "status",
            "stage",
            "user_id",
            "user_email",
            "resume_id",
            "target_role",
            "query",
            "stages",
            "drops",
            "matcher_stages",
            "shown_to_user",
            "fetched_raw",
            "total_drops",
            "residual",
            "metrics",
            "created_at",
        ):
            self.assertIn(field, body, msg=f"missing field: {field}")

        self.assertEqual(body["job_id"], self.job_id)
        self.assertEqual(body["user_email"], self.user_email)
        self.assertEqual(body["target_role"], "Python-разработчик")
        self.assertEqual(body["query"], "Python разработчик Москва")
        self.assertEqual(body["shown_to_user"], len(self.matches_payload))
        self.assertEqual(body["fetched_raw"], 1500)

        self.assertIsInstance(body["stages"], list)
        self.assertIsInstance(body["drops"], list)
        self.assertIsInstance(body["matcher_stages"], list)
        self.assertGreater(len(body["stages"]), 0)
        self.assertGreater(len(body["drops"]), 0)

        for stage in body["stages"]:
            for key in ("key", "label", "value", "kind"):
                self.assertIn(key, stage)
            self.assertEqual(stage["kind"], "flow")
            self.assertGreaterEqual(stage["value"], 0)
        for drop in body["drops"]:
            self.assertEqual(drop["kind"], "drop")
            self.assertGreaterEqual(drop["value"], 0)
        for meta in body["matcher_stages"]:
            self.assertEqual(meta["kind"], "meta")

        stage_keys = {s["key"] for s in body["stages"]}
        self.assertIn("hh_fetched_raw", stage_keys)
        self.assertIn("fetched", stage_keys)
        self.assertIn("analyzed", stage_keys)
        self.assertIn("shown_to_user", stage_keys)

        drop_keys = {d["key"] for d in body["drops"]}
        self.assertIn("search_dedup_skipped", drop_keys)
        self.assertIn("matcher_drop_mmr_dedupe", drop_keys)

        # total_drops equals the sum of all drop buckets
        total = sum(d["value"] for d in body["drops"])
        self.assertEqual(body["total_drops"], total)

        # Residual never negative: the waterfall invariant
        self.assertGreaterEqual(body["residual"], 0)
        self.assertEqual(
            body["residual"],
            max(0, body["fetched_raw"] - body["shown_to_user"] - body["total_drops"]),
        )

        # metrics echoes the persisted dict (subset check — we only care our keys are there)
        self.assertEqual(body["metrics"]["hh_fetched_raw"], 1500)
        self.assertEqual(body["metrics"]["matcher_runs_total"], 2)

    def test_funnel_flow_stage_values_match_metrics(self) -> None:
        resp = self.client.get(
            f"/api/admin/jobs/{self.job_id}/funnel",
            headers=_auth_header(self.admin_email),
        )
        self.assertEqual(resp.status_code, 200)
        stages_by_key = {s["key"]: s["value"] for s in resp.json()["stages"]}
        self.assertEqual(stages_by_key["hh_fetched_raw"], self.metrics["hh_fetched_raw"])
        self.assertEqual(stages_by_key["fetched"], self.metrics["fetched"])
        self.assertEqual(stages_by_key["prefiltered"], self.metrics["prefiltered"])
        self.assertEqual(stages_by_key["analyzed"], self.metrics["analyzed"])
        self.assertEqual(stages_by_key["indexed"], self.metrics["indexed"])
        self.assertEqual(
            stages_by_key["matcher_recall_count"], self.metrics["matcher_recall_count"]
        )
        self.assertEqual(stages_by_key["shown_to_user"], len(self.matches_payload))

    def test_funnel_handles_missing_metrics_gracefully(self) -> None:
        """A job with metrics=None should still return a well-formed response
        with zeros everywhere — not a 500."""
        blank_id = str(uuid.uuid4())
        blank_job = RecommendationJob(
            id=blank_id,
            user_id=self.user.id,
            resume_id=self.resume.id,
            status="queued",
            stage="queued",
            progress=0,
            metrics=None,
            matches=None,
        )
        self.db.add(blank_job)
        self.db.commit()
        try:
            resp = self.client.get(
                f"/api/admin/jobs/{blank_id}/funnel",
                headers=_auth_header(self.admin_email),
            )
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertEqual(body["shown_to_user"], 0)
            self.assertEqual(body["fetched_raw"], 0)
            self.assertEqual(body["total_drops"], 0)
            self.assertEqual(body["residual"], 0)
            for stage in body["stages"]:
                self.assertEqual(stage["value"], 0)
            for drop in body["drops"]:
                self.assertEqual(drop["value"], 0)
        finally:
            self.db.execute(delete(RecommendationJob).where(RecommendationJob.id == blank_id))
            self.db.commit()


if __name__ == "__main__":
    unittest.main()
