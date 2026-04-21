"""API + schema tests for user job preferences (Phase 2.0 PR 1)."""

from __future__ import annotations

import unittest
import uuid

from pydantic import ValidationError
from sqlalchemy import delete

from app.api.routes.users import patch_me_preferences, read_me
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.user import (
    HOME_CITY_MAX,
    JOB_TITLE_MAX,
    PREFERRED_TITLES_MAX,
    UserPreferencesUpdate,
)


class UserPreferencesSchemaTest(unittest.TestCase):
    def test_defaults_all_none(self) -> None:
        payload = UserPreferencesUpdate()
        self.assertEqual(
            payload.model_dump(exclude_unset=True),
            {},
        )

    def test_rejects_bad_work_format(self) -> None:
        with self.assertRaises(ValidationError):
            UserPreferencesUpdate(preferred_work_format="contractor")

    def test_rejects_bad_relocation_mode(self) -> None:
        with self.assertRaises(ValidationError):
            UserPreferencesUpdate(relocation_mode="maybe")

    def test_rejects_overlong_home_city(self) -> None:
        with self.assertRaises(ValidationError):
            UserPreferencesUpdate(home_city="a" * (HOME_CITY_MAX + 1))

    def test_rejects_too_many_titles(self) -> None:
        with self.assertRaises(ValidationError):
            UserPreferencesUpdate(
                preferred_titles=[f"title-{i}" for i in range(PREFERRED_TITLES_MAX + 1)]
            )

    def test_rejects_overlong_single_title(self) -> None:
        with self.assertRaises(ValidationError):
            UserPreferencesUpdate(preferred_titles=["a" * (JOB_TITLE_MAX + 1)])

    def test_titles_are_trimmed_and_blanks_removed(self) -> None:
        payload = UserPreferencesUpdate(
            preferred_titles=["  Senior Backend  ", "", "   ", "Data Engineer"]
        )
        self.assertEqual(payload.preferred_titles, ["Senior Backend", "Data Engineer"])

    def test_empty_city_becomes_none(self) -> None:
        payload = UserPreferencesUpdate(home_city="   ")
        self.assertIsNone(payload.home_city)


class UserPreferencesApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.suffix = uuid.uuid4().hex[:10]
        self.email = f"prefs-{self.suffix}@example.com"
        self.user = User(
            email=self.email,
            hashed_password=hash_password("Str0ngPass!"),
            full_name="Prefs Tester",
            is_active=True,
            email_verified=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self) -> None:
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_me_returns_defaults(self) -> None:
        result = read_me(current_user=self.user)
        self.assertEqual(result.preferred_work_format, "any")
        self.assertEqual(result.relocation_mode, "home_only")
        self.assertIsNone(result.home_city)
        self.assertEqual(result.preferred_titles, [])

    def test_patch_partial_update_persists(self) -> None:
        payload = UserPreferencesUpdate(
            preferred_work_format="remote",
            home_city="Москва",
        )
        updated = patch_me_preferences(payload=payload, current_user=self.user, db=self.db)
        self.assertEqual(updated.preferred_work_format, "remote")
        self.assertEqual(updated.home_city, "Москва")
        # Untouched fields stay at defaults.
        self.assertEqual(updated.relocation_mode, "home_only")
        self.assertEqual(updated.preferred_titles, [])

        # Round-trip through the DB.
        self.db.expire_all()
        fresh = self.db.get(User, self.user.id)
        assert fresh is not None
        self.assertEqual(fresh.preferred_work_format, "remote")
        self.assertEqual(fresh.home_city, "Москва")

    def test_empty_patch_leaves_fields_unchanged(self) -> None:
        # Seed a value.
        patch_me_preferences(
            payload=UserPreferencesUpdate(home_city="СПб"),
            current_user=self.user,
            db=self.db,
        )
        # No fields set — repo should not touch anything.
        unchanged = patch_me_preferences(
            payload=UserPreferencesUpdate(),
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(unchanged.home_city, "СПб")

    def test_explicit_null_clears_home_city(self) -> None:
        patch_me_preferences(
            payload=UserPreferencesUpdate(home_city="СПб"),
            current_user=self.user,
            db=self.db,
        )
        cleared = patch_me_preferences(
            payload=UserPreferencesUpdate(home_city=None),
            current_user=self.user,
            db=self.db,
        )
        self.assertIsNone(cleared.home_city)

    def test_empty_string_also_clears_home_city(self) -> None:
        patch_me_preferences(
            payload=UserPreferencesUpdate(home_city="СПб"),
            current_user=self.user,
            db=self.db,
        )
        cleared = patch_me_preferences(
            payload=UserPreferencesUpdate(home_city=""),
            current_user=self.user,
            db=self.db,
        )
        self.assertIsNone(cleared.home_city)

    def test_patch_titles_persists(self) -> None:
        updated = patch_me_preferences(
            payload=UserPreferencesUpdate(
                preferred_titles=["Senior Backend Engineer", "Python Developer"]
            ),
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(
            updated.preferred_titles,
            ["Senior Backend Engineer", "Python Developer"],
        )

    def test_patch_relocation_mode(self) -> None:
        updated = patch_me_preferences(
            payload=UserPreferencesUpdate(relocation_mode="any_city"),
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(updated.relocation_mode, "any_city")


if __name__ == "__main__":
    unittest.main()
