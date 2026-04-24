"""Tests for Level 2 D2 — UserVacancySeen dedup.

The matcher must exclude vacancies a user has seen in the last 14 days, and
every successful match response must record new impressions so the next run
sees them. Both the upsert and the exclusion are behind
``feature_exclude_seen_enabled`` so ops can flip it off without deploying.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User
from app.models.user_vacancy_seen import UserVacancySeen
from app.models.vacancy import Vacancy
from app.repositories.user_vacancy_seen import (
    list_seen_vacancy_ids,
    upsert_seen_vacancies,
)


class UserVacancySeenRepoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        self.user = User(
            email=f"seen-{suffix}@example.com",
            hashed_password=hash_password("TestPass123"),
            full_name="Seen Test",
            is_active=True,
            email_verified=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.vacancies: list[Vacancy] = []
        for i in range(3):
            v = Vacancy(
                source="hh_api",
                source_url=f"https://hh.ru/vacancy/seentest-{suffix}-{i}",
                title=f"Test Vacancy {i}",
                status="indexed",
            )
            self.db.add(v)
            self.vacancies.append(v)
        self.db.commit()
        for v in self.vacancies:
            self.db.refresh(v)

    def tearDown(self) -> None:
        self.db.execute(
            delete(UserVacancySeen).where(UserVacancySeen.user_id == self.user.id)
        )
        for v in self.vacancies:
            self.db.execute(delete(Vacancy).where(Vacancy.id == v.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def test_upsert_creates_rows(self) -> None:
        ids = [v.id for v in self.vacancies]
        n = upsert_seen_vacancies(self.db, user_id=self.user.id, vacancy_ids=ids)
        self.assertEqual(n, len(ids))
        self.assertEqual(
            list_seen_vacancy_ids(self.db, user_id=self.user.id, within_days=14),
            set(ids),
        )

    def test_upsert_is_idempotent_and_refreshes_shown_at(self) -> None:
        ids = [v.id for v in self.vacancies]
        upsert_seen_vacancies(self.db, user_id=self.user.id, vacancy_ids=ids)
        # Artificially age the rows to 20 days ago.
        aged = datetime.now(UTC) - timedelta(days=20)
        self.db.query(UserVacancySeen).filter(
            UserVacancySeen.user_id == self.user.id
        ).update({"shown_at": aged}, synchronize_session=False)
        self.db.commit()
        # Outside a 14-day window — must be invisible.
        self.assertEqual(
            list_seen_vacancy_ids(self.db, user_id=self.user.id, within_days=14),
            set(),
        )
        # Re-upsert bumps shown_at to now — now they come back inside the window.
        upsert_seen_vacancies(self.db, user_id=self.user.id, vacancy_ids=ids)
        self.assertEqual(
            list_seen_vacancy_ids(self.db, user_id=self.user.id, within_days=14),
            set(ids),
        )

    def test_list_seen_respects_within_days(self) -> None:
        ids = [v.id for v in self.vacancies]
        upsert_seen_vacancies(self.db, user_id=self.user.id, vacancy_ids=ids)
        # within_days=0 — empty window, nothing considered seen.
        self.assertEqual(
            list_seen_vacancy_ids(self.db, user_id=self.user.id, within_days=0),
            set(),
        )
        self.assertEqual(
            list_seen_vacancy_ids(self.db, user_id=self.user.id, within_days=14),
            set(ids),
        )

    def test_upsert_empty_list_is_noop(self) -> None:
        self.assertEqual(
            upsert_seen_vacancies(self.db, user_id=self.user.id, vacancy_ids=[]),
            0,
        )

    def test_feature_flag_default_is_enabled(self) -> None:
        self.assertTrue(settings.feature_exclude_seen_enabled)
        self.assertEqual(settings.feature_exclude_seen_window_days, 14)


if __name__ == "__main__":
    unittest.main()
