"""Phase 2.6 — match telemetry writer + endpoint smoke tests.

Hits the real Postgres via SessionLocal and the real FastAPI handlers;
no mocks except the rate limiter (flipped off so we can fire N rows).
"""

from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace

from fastapi import Request
from sqlalchemy import delete, select

from app.api.routes.telemetry import (
    ClickPayload,
    DwellPayload,
    DwellRow,
    post_click,
    post_dwell,
)
from app.core.rate_limit import limiter
from app.db.session import SessionLocal
from app.models.match_telemetry import MatchClick, MatchDwell, MatchImpression
from app.models.resume import Resume
from app.models.user import User
from app.models.vacancy import Vacancy
from app.services.match_telemetry import (
    log_click,
    log_dwell_batch,
    log_impressions,
)


def _make_request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/telemetry/click",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 0),
        "query_string": b"",
    }
    return Request(scope)


class MatchTelemetryTest(unittest.TestCase):
    def setUp(self) -> None:
        self._limiter_was_enabled = limiter.enabled
        limiter.enabled = False
        self.db = SessionLocal()
        self.suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"tlm-{self.suffix}@example.com",
            hashed_password="test-hash",
            full_name="Telemetry Tester",
            is_active=True,
            email_verified=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.resume = Resume(
            user_id=self.user.id,
            original_filename="resume.txt",
            storage_path=f"resume-{self.suffix}.txt",
            content_type="text/plain",
        )
        self.db.add(self.resume)
        self.db.commit()
        self.db.refresh(self.resume)

        self.vacancy = Vacancy(
            source="test",
            source_url=f"https://example.test/vacancy/{self.suffix}",
            title="Backend engineer",
            company="Example Inc.",
            location="Москва",
            status="indexed",
        )
        self.db.add(self.vacancy)
        self.db.commit()
        self.db.refresh(self.vacancy)

    def tearDown(self) -> None:
        self.db.execute(delete(MatchImpression).where(MatchImpression.user_id == self.user.id))
        self.db.execute(delete(MatchClick).where(MatchClick.user_id == self.user.id))
        self.db.execute(delete(MatchDwell).where(MatchDwell.vacancy_id == self.vacancy.id))
        self.db.execute(delete(Vacancy).where(Vacancy.id == self.vacancy.id))
        self.db.execute(delete(Resume).where(Resume.id == self.resume.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()
        limiter.enabled = self._limiter_was_enabled

    def test_log_impressions_bulk_inserts_one_per_match(self) -> None:
        run_id = uuid.uuid4()
        matches = [
            {
                "vacancy_id": self.vacancy.id,
                "similarity_score": 0.82,
                "tier": "strong",
                "profile": {
                    "vector_score": 0.71,
                    "rerank_score": 0.9,
                    "llm_confidence": 0.85,
                    "role_family": "software_engineering",
                },
            }
        ]
        written = log_impressions(
            self.db,
            user_id=self.user.id,
            resume_id=self.resume.id,
            match_run_id=run_id,
            matches=matches,
        )
        self.assertEqual(written, 1)
        row = self.db.execute(
            select(MatchImpression).where(MatchImpression.match_run_id == run_id)
        ).scalar_one()
        self.assertEqual(row.vacancy_id, self.vacancy.id)
        self.assertEqual(row.tier, "strong")
        self.assertAlmostEqual(row.hybrid_score, 0.82)
        self.assertAlmostEqual(row.rerank_score, 0.9)
        self.assertEqual(row.role_family, "software_engineering")

    def test_log_impressions_empty_list_is_zero(self) -> None:
        self.assertEqual(
            log_impressions(
                self.db,
                user_id=self.user.id,
                resume_id=self.resume.id,
                match_run_id=uuid.uuid4(),
                matches=[],
            ),
            0,
        )

    def test_log_click_rejects_unknown_kind(self) -> None:
        ok = log_click(
            self.db,
            user_id=self.user.id,
            vacancy_id=self.vacancy.id,
            click_kind="not_a_real_kind",
        )
        self.assertFalse(ok)

    def test_log_click_persists_allowed_kind(self) -> None:
        run_id = uuid.uuid4()
        ok = log_click(
            self.db,
            user_id=self.user.id,
            resume_id=self.resume.id,
            vacancy_id=self.vacancy.id,
            match_run_id=run_id,
            position=3,
            click_kind="apply",
        )
        self.assertTrue(ok)
        row = self.db.execute(
            select(MatchClick).where(MatchClick.match_run_id == run_id)
        ).scalar_one()
        self.assertEqual(row.click_kind, "apply")
        self.assertEqual(row.position, 3)

    def test_log_dwell_upsert_sums_ms_on_conflict(self) -> None:
        run_id = uuid.uuid4()
        log_dwell_batch(
            self.db,
            match_run_id=run_id,
            entries=[(self.vacancy.id, 500)],
        )
        log_dwell_batch(
            self.db,
            match_run_id=run_id,
            entries=[(self.vacancy.id, 800)],
        )
        row = self.db.execute(
            select(MatchDwell).where(MatchDwell.match_run_id == run_id)
        ).scalar_one()
        self.assertEqual(row.ms, 1300)

    def test_click_endpoint_persists_row(self) -> None:
        run_id = uuid.uuid4()
        payload = ClickPayload(
            vacancy_id=self.vacancy.id,
            click_kind="open_card",
            match_run_id=run_id,
            resume_id=self.resume.id,
            position=0,
        )
        response = post_click(
            _make_request(),
            SimpleNamespace(),
            payload,
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(response.status_code, 204)
        row = self.db.execute(
            select(MatchClick).where(MatchClick.match_run_id == run_id)
        ).scalar_one()
        self.assertEqual(row.click_kind, "open_card")

    def test_dwell_endpoint_persists_rows(self) -> None:
        run_id = uuid.uuid4()
        payload = DwellPayload(
            match_run_id=run_id,
            rows=[DwellRow(vacancy_id=self.vacancy.id, ms=250)],
        )
        response = post_dwell(
            _make_request(),
            SimpleNamespace(),
            payload,
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(response.status_code, 204)
        row = self.db.execute(
            select(MatchDwell).where(MatchDwell.match_run_id == run_id)
        ).scalar_one()
        self.assertEqual(row.ms, 250)

    def test_dwell_endpoint_drops_zero_ms_rows(self) -> None:
        run_id = uuid.uuid4()
        payload = DwellPayload(
            match_run_id=run_id,
            rows=[DwellRow(vacancy_id=self.vacancy.id, ms=0)],
        )
        post_dwell(
            _make_request(),
            SimpleNamespace(),
            payload,
            current_user=self.user,
            db=self.db,
        )
        row = self.db.execute(
            select(MatchDwell).where(MatchDwell.match_run_id == run_id)
        ).scalar_one_or_none()
        self.assertIsNone(row)


if __name__ == "__main__":
    unittest.main()
