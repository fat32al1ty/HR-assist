"""v0.23.0: POST /api/telemetry/event persists into match_event."""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.match_event import MatchEvent
from app.models.user import User


class MatchEventPersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"matchevt-{suffix}@example.com",
            hashed_password=hash_password("TestPass123"),
            full_name="MatchEvt",
            is_active=True,
            email_verified=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        self.token = create_access_token(subject=self.user.email)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.db.execute(MatchEvent.__table__.delete().where(MatchEvent.user_id == self.user.id))
        self.db.execute(User.__table__.delete().where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def test_known_event_writes_row(self) -> None:
        resp = self.client.post(
            "/api/telemetry/event",
            json={"event": "track_section_expanded", "payload": {"section": "match"}},
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 204)

        rows = self.db.scalars(select(MatchEvent).where(MatchEvent.user_id == self.user.id)).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].event, "track_section_expanded")
        self.assertEqual(rows[0].payload, {"section": "match"})
        # Middleware-generated request_id should be present + non-empty.
        self.assertIsNotNone(rows[0].request_id)
        self.assertGreater(len(rows[0].request_id), 0)

    def test_unknown_event_rejected_no_row(self) -> None:
        resp = self.client.post(
            "/api/telemetry/event",
            json={"event": "made_up_event", "payload": {}},
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 400)
        rows = self.db.scalars(select(MatchEvent).where(MatchEvent.user_id == self.user.id)).all()
        self.assertEqual(len(rows), 0)

    def test_payload_size_cap_rejects_oversized(self) -> None:
        big = {f"k{i}": "x" for i in range(40)}  # 40 > 32 cap
        resp = self.client.post(
            "/api/telemetry/event",
            json={"event": "track_section_expanded", "payload": big},
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
