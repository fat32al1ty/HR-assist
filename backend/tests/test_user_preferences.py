"""Integration tests for preferred_domains in PATCH /api/users/me/preferences.

T1: PATCH {"preferred_domains": ["FinTech"]} → 200, UserRead.preferred_domains == ["FinTech"].
    Re-GET /me confirms the value was persisted in the DB.
T2: PATCH {"preferred_domains": []} after having ["X"] set → column is cleared.
T3: PATCH body without preferred_domains → existing value untouched.
T4: PATCH {"preferred_domains": ["a"]*4} → 422 (over the 3-item cap).
T5: PATCH {"preferred_domains": ["x"*65]} → 422 (item > 64 chars).
T6: PATCH {"preferred_domains": ["  ", ""]} → items cleaned to [] (blanks stripped).
"""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User


def _make_user(db) -> User:
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"domainpref-{suffix}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Domain Prefs Tester",
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=email)}"}


class PreferredDomainsPatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.user = _make_user(self.db)
        self.client = TestClient(app)
        self.headers = _auth_headers(self.user.email)

    def tearDown(self) -> None:
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    # T1 ─────────────────────────────────────────────────────────────────────
    def test_patch_preferred_domains_set_and_persisted(self) -> None:
        """PATCH with ["FinTech"] → 200, response + GET /me both show ["FinTech"]."""
        resp = self.client.patch(
            "/api/users/me/preferences",
            json={"preferred_domains": ["FinTech"]},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["preferred_domains"], ["FinTech"])

        # Re-GET confirms DB persistence.
        me = self.client.get("/api/users/me", headers=self.headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["preferred_domains"], ["FinTech"])

    # T2 ─────────────────────────────────────────────────────────────────────
    def test_patch_preferred_domains_clear_with_empty_list(self) -> None:
        """PATCH [] after having ["X"] → column becomes empty."""
        # Seed a value first.
        self.client.patch(
            "/api/users/me/preferences",
            json={"preferred_domains": ["X"]},
            headers=self.headers,
        )
        # Now clear it.
        resp = self.client.patch(
            "/api/users/me/preferences",
            json={"preferred_domains": []},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["preferred_domains"], [])

        # DB round-trip.
        self.db.expire_all()
        fresh = self.db.get(User, self.user.id)
        self.assertIsNotNone(fresh)
        self.assertEqual(fresh.preferred_domains, [])  # type: ignore[union-attr]

    # T3 ─────────────────────────────────────────────────────────────────────
    def test_patch_omitting_preferred_domains_leaves_value_untouched(self) -> None:
        """PATCH without preferred_domains key → existing value untouched."""
        # Seed.
        self.client.patch(
            "/api/users/me/preferences",
            json={"preferred_domains": ["HealthTech"]},
            headers=self.headers,
        )
        # Update something else — no preferred_domains key.
        resp = self.client.patch(
            "/api/users/me/preferences",
            json={"preferred_work_format": "remote"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["preferred_domains"], ["HealthTech"])

    # T4 ─────────────────────────────────────────────────────────────────────
    def test_patch_preferred_domains_over_cap_returns_422(self) -> None:
        """4 items (cap is 3) → 422."""
        resp = self.client.patch(
            "/api/users/me/preferences",
            json={"preferred_domains": ["a", "b", "c", "d"]},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 422, resp.text)

    # T5 ─────────────────────────────────────────────────────────────────────
    def test_patch_preferred_domains_overlong_item_returns_422(self) -> None:
        """Item of 65 chars (cap is 64) → 422."""
        resp = self.client.patch(
            "/api/users/me/preferences",
            json={"preferred_domains": ["x" * 65]},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 422, resp.text)

    # T6 ─────────────────────────────────────────────────────────────────────
    def test_patch_preferred_domains_blank_items_are_stripped_to_empty(self) -> None:
        """["  ", ""] → validator strips blanks → stored as []."""
        resp = self.client.patch(
            "/api/users/me/preferences",
            json={"preferred_domains": ["  ", ""]},
            headers=self.headers,
        )
        # Validator removes empty-after-strip items → list becomes [] → 200.
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["preferred_domains"], [])


if __name__ == "__main__":
    unittest.main()
