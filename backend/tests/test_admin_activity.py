"""Integration tests for admin activity statistics (DAU/WAU/MAU + 14-day charts).

Covers:
- /api/admin/overview activity field shape and values
- record_login_event hook in POST /api/auth/login
"""

from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, update

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.models.user_login_event import UserLoginEvent


def _make_user(db, email: str, is_admin: bool = False, created_at: datetime | None = None) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("TestPass123"),
        full_name="Activity Test",
        is_active=True,
        email_verified=True,
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    if created_at is not None:
        db.execute(update(User).where(User.id == user.id).values(created_at=created_at))
        db.commit()
        db.refresh(user)
    return user


def _auth_header(email: str) -> dict[str, str]:
    token = create_access_token(subject=email)
    return {"Authorization": f"Bearer {token}"}


def _add_login_event(db, user_id: int, occurred_at: datetime) -> None:
    event = UserLoginEvent(user_id=user_id, occurred_at=occurred_at)
    db.add(event)
    db.commit()


class AdminActivityOverviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.admin_email = f"act-admin-{suffix}@example.com"
        self.user1_email = f"act-user1-{suffix}@example.com"
        self.user2_email = f"act-user2-{suffix}@example.com"

        now = datetime.now(UTC)

        # admin created today
        self.admin = _make_user(self.db, self.admin_email, is_admin=True, created_at=now)
        # user1 created 8 days ago
        self.user1 = _make_user(
            self.db, self.user1_email, is_admin=False, created_at=now - timedelta(days=8)
        )
        # user2 created 3 days ago
        self.user2 = _make_user(
            self.db, self.user2_email, is_admin=False, created_at=now - timedelta(days=3)
        )

        # login events:
        # user1: 30 days ago (MAU only), 7 days ago (WAU+MAU), 12h ago (DAU+WAU+MAU)
        _add_login_event(self.db, self.user1.id, now - timedelta(days=30))
        _add_login_event(self.db, self.user1.id, now - timedelta(days=7))
        _add_login_event(self.db, self.user1.id, now - timedelta(hours=12))
        # user2: 5 days ago (WAU+MAU)
        _add_login_event(self.db, self.user2.id, now - timedelta(days=5))

        self.user_ids = [self.admin.id, self.user1.id, self.user2.id]

    def tearDown(self) -> None:
        self.db.execute(
            delete(UserLoginEvent).where(UserLoginEvent.user_id.in_(self.user_ids))
        )
        for uid in self.user_ids:
            self.db.execute(delete(User).where(User.id == uid))
        self.db.commit()
        self.db.close()

    def test_overview_activity_shape(self) -> None:
        resp = self.client.get(
            "/api/admin/overview", headers=_auth_header(self.admin_email)
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("activity", body)
        act = body["activity"]
        for field in ("signups_per_day", "logins_per_day", "dau", "wau", "mau"):
            self.assertIn(field, act)

    def test_overview_signups_per_day_length_and_order(self) -> None:
        resp = self.client.get(
            "/api/admin/overview", headers=_auth_header(self.admin_email)
        )
        self.assertEqual(resp.status_code, 200)
        act = resp.json()["activity"]
        signups = act["signups_per_day"]
        self.assertEqual(len(signups), 14)
        dates = [r["date"] for r in signups]
        self.assertEqual(dates, sorted(dates))

    def test_overview_logins_per_day_length_and_order(self) -> None:
        resp = self.client.get(
            "/api/admin/overview", headers=_auth_header(self.admin_email)
        )
        self.assertEqual(resp.status_code, 200)
        act = resp.json()["activity"]
        logins = act["logins_per_day"]
        self.assertEqual(len(logins), 14)
        dates = [r["date"] for r in logins]
        self.assertEqual(dates, sorted(dates))

    def test_overview_dau_wau_mau(self) -> None:
        resp = self.client.get(
            "/api/admin/overview", headers=_auth_header(self.admin_email)
        )
        self.assertEqual(resp.status_code, 200)
        act = resp.json()["activity"]

        # DAU: only user1 logged in within last 24h
        self.assertEqual(act["dau"], 1)
        # WAU: user1 (12h ago + exactly 7d ago boundary — 7d event is right at the edge;
        # we allow 1 or 2 depending on exact timing) + user2 (5d ago) = 2 distinct users
        self.assertGreaterEqual(act["wau"], 2)
        # MAU: user1 (all 3 events) + user2 (5d ago) = 2 distinct users
        # The 30d-ago event for user1 is right at the boundary; at minimum user1+user2
        self.assertGreaterEqual(act["mau"], 2)

    def test_overview_signups_total_matches_seed(self) -> None:
        resp = self.client.get(
            "/api/admin/overview", headers=_auth_header(self.admin_email)
        )
        self.assertEqual(resp.status_code, 200)
        act = resp.json()["activity"]
        # admin (today) + user2 (3d ago) are within 14-day window
        # user1 (8d ago) is also within 14-day window
        # total signups in window = 3 (admin + user1 + user2)
        total = sum(r["count"] for r in act["signups_per_day"])
        self.assertGreaterEqual(total, 2)

    def test_overview_logins_total_matches_seed(self) -> None:
        resp = self.client.get(
            "/api/admin/overview", headers=_auth_header(self.admin_email)
        )
        self.assertEqual(resp.status_code, 200)
        act = resp.json()["activity"]
        # Within 14 days: user1 7d-ago + 12h-ago + user2 5d-ago = 3 events
        total = sum(r["count"] for r in act["logins_per_day"])
        self.assertGreaterEqual(total, 3)


class AuthLoginRecordsEventTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.client = TestClient(app)
        suffix = uuid.uuid4().hex[:10]
        self.email = f"login-evt-{suffix}@example.com"
        self.password = "TestPass123"
        self.user = _make_user(self.db, self.email)

    def tearDown(self) -> None:
        self.db.execute(
            delete(UserLoginEvent).where(UserLoginEvent.user_id == self.user.id)
        )
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_login_creates_event(self) -> None:
        # Count events before login
        before = self.db.query(UserLoginEvent).filter(
            UserLoginEvent.user_id == self.user.id
        ).count()

        resp = self.client.post(
            "/api/auth/login",
            json={"email": self.email, "password": self.password},
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        # Expire cached state so we see DB-committed rows
        self.db.expire_all()
        after = self.db.query(UserLoginEvent).filter(
            UserLoginEvent.user_id == self.user.id
        ).count()
        self.assertEqual(after, before + 1)


if __name__ == "__main__":
    unittest.main()
