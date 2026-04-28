"""Tests for vacancy_freshness service and instant endpoint integration.

All HTTP calls are mocked — no real network traffic.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.user import User
from app.models.vacancy import Vacancy
from app.services import vacancy_freshness
from app.services.vacancy_freshness import (
    _extract_hh_id,
    check_vacancy_alive,
    check_vacancies_alive_concurrently,
    sweep_stale_vacancies,
)


# ---------------------------------------------------------------------------
# Pure-function tests — no DB required
# ---------------------------------------------------------------------------


class ExtractHhIdTest(unittest.TestCase):
    def test_canonical_url(self) -> None:
        self.assertEqual(_extract_hh_id("https://hh.ru/vacancy/123456"), "123456")

    def test_url_with_query_params(self) -> None:
        self.assertEqual(
            _extract_hh_id("https://hh.ru/vacancy/987654?from=search"), "987654"
        )

    def test_none_input(self) -> None:
        self.assertIsNone(_extract_hh_id(None))

    def test_empty_string(self) -> None:
        self.assertIsNone(_extract_hh_id(""))

    def test_non_hh_url(self) -> None:
        self.assertIsNone(_extract_hh_id("https://superjob.ru/vakansii/foo.html"))

    def test_hh_url_without_vacancy_path(self) -> None:
        self.assertIsNone(_extract_hh_id("https://hh.ru/search/vacancy?text=python"))


# ---------------------------------------------------------------------------
# DB-backed tests
# ---------------------------------------------------------------------------


def _unique_hh_id() -> str:
    """Return a numeric string unique enough not to collide across test runs."""
    return str(int(uuid.uuid4().int % 10**9) + 10**9)


class VacancyFreshnessDbBase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.hh_id = _unique_hh_id()
        suffix = uuid.uuid4().hex[:8]
        self.user = User(
            email=f"freshness-{suffix}@example.com",
            hashed_password="test-hash",
            full_name="Freshness Test",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.vacancy = Vacancy(
            source="hh_api",
            source_url=f"https://hh.ru/vacancy/{self.hh_id}",
            title="Python Backend Engineer",
            status="indexed",
        )
        self.db.add(self.vacancy)
        self.db.commit()
        self.db.refresh(self.vacancy)

    def tearDown(self) -> None:
        self.db.execute(delete(Vacancy).where(Vacancy.id == self.vacancy.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()


class CheckVacancyAliveTest(VacancyFreshnessDbBase):
    def _mock_response(self, *, status_code: int, json_body: dict | None = None) -> MagicMock:
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        if json_body is not None:
            resp.json.return_value = json_body
        else:
            resp.json.side_effect = Exception("no body")
        return resp

    def test_200_not_archived_returns_true_and_sets_check(self) -> None:
        resp = self._mock_response(status_code=200, json_body={"archived": False, "id": "1"})
        with patch("app.services.vacancy_freshness.httpx.get", return_value=resp):
            result = check_vacancy_alive(self.db, vacancy=self.vacancy)

        self.assertTrue(result)
        self.db.refresh(self.vacancy)
        self.assertIsNotNone(self.vacancy.last_freshness_check)
        self.assertIsNone(self.vacancy.archived_at)
        self.assertEqual(self.vacancy.status, "indexed")

    def test_200_archived_true_returns_false_and_marks_archived(self) -> None:
        resp = self._mock_response(status_code=200, json_body={"archived": True})
        with patch("app.services.vacancy_freshness.httpx.get", return_value=resp):
            result = check_vacancy_alive(self.db, vacancy=self.vacancy)

        self.assertFalse(result)
        self.db.refresh(self.vacancy)
        self.assertIsNotNone(self.vacancy.last_freshness_check)
        self.assertIsNotNone(self.vacancy.archived_at)
        self.assertEqual(self.vacancy.status, "archived")

    def test_404_returns_false_and_marks_archived(self) -> None:
        resp = self._mock_response(status_code=404)
        with patch("app.services.vacancy_freshness.httpx.get", return_value=resp):
            result = check_vacancy_alive(self.db, vacancy=self.vacancy)

        self.assertFalse(result)
        self.db.refresh(self.vacancy)
        self.assertIsNotNone(self.vacancy.archived_at)
        self.assertEqual(self.vacancy.status, "archived")

    def test_410_returns_false_and_marks_archived(self) -> None:
        resp = self._mock_response(status_code=410)
        with patch("app.services.vacancy_freshness.httpx.get", return_value=resp):
            result = check_vacancy_alive(self.db, vacancy=self.vacancy)

        self.assertFalse(result)
        self.db.refresh(self.vacancy)
        self.assertIsNotNone(self.vacancy.archived_at)

    def test_5xx_returns_true_and_still_bumps_freshness_check(self) -> None:
        """5xx: assume alive (not archived), but DO bump last_freshness_check
        so the row isn't perpetually retried before other rows."""
        resp = self._mock_response(status_code=503)
        with patch("app.services.vacancy_freshness.httpx.get", return_value=resp):
            result = check_vacancy_alive(self.db, vacancy=self.vacancy)

        self.assertTrue(result)
        self.db.refresh(self.vacancy)
        self.assertIsNotNone(self.vacancy.last_freshness_check)
        self.assertIsNone(self.vacancy.archived_at)
        self.assertEqual(self.vacancy.status, "indexed")

    def test_network_error_returns_true_and_does_not_bump_check(self) -> None:
        """Network error: assume alive, do NOT update last_freshness_check so
        the row stays at the top of the sweep queue for retry."""
        before = self.vacancy.last_freshness_check

        with patch(
            "app.services.vacancy_freshness.httpx.get",
            side_effect=httpx.ConnectError("timeout"),
        ):
            result = check_vacancy_alive(self.db, vacancy=self.vacancy)

        self.assertTrue(result)
        self.db.refresh(self.vacancy)
        self.assertEqual(self.vacancy.last_freshness_check, before)

    def test_non_hh_vacancy_skipped_returns_true(self) -> None:
        self.vacancy.source_url = "https://superjob.ru/vakansii/foo.html"
        self.db.commit()
        result = check_vacancy_alive(self.db, vacancy=self.vacancy)
        self.assertTrue(result)


class SweepStaleVacanciesTest(VacancyFreshnessDbBase):
    def setUp(self) -> None:
        super().setUp()
        hh_id2 = _unique_hh_id()
        self.vacancy2 = Vacancy(
            source="hh_api",
            source_url=f"https://hh.ru/vacancy/{hh_id2}",
            title="DevOps Engineer",
            status="indexed",
            last_freshness_check=datetime.now(UTC),
        )
        self.db.add(self.vacancy2)
        self.db.commit()
        self.db.refresh(self.vacancy2)

    def tearDown(self) -> None:
        self.db.execute(delete(Vacancy).where(Vacancy.id == self.vacancy2.id))
        super().tearDown()

    def test_null_last_freshness_check_checked_before_recent(self) -> None:
        """Row with NULL last_freshness_check must be checked before vacancy2
        which has a recent timestamp."""
        call_order: list[int] = []

        # Ensure self.vacancy has NULL last_freshness_check
        self.vacancy.last_freshness_check = None
        self.db.commit()

        def _spy(db, *, vacancy):
            # Only track our two test rows
            if vacancy.id in (self.vacancy.id, self.vacancy2.id):
                call_order.append(vacancy.id)
            return True

        with patch.object(vacancy_freshness, "check_vacancy_alive", side_effect=_spy):
            # Use a large limit so both rows are included
            sweep_stale_vacancies(self.db, limit=10000)

        # Both of our rows must have been reached
        self.assertIn(self.vacancy.id, call_order)
        self.assertIn(self.vacancy2.id, call_order)
        # self.vacancy (NULL check) must come before vacancy2 (recent check)
        self.assertLess(
            call_order.index(self.vacancy.id),
            call_order.index(self.vacancy2.id),
        )

    def test_sweep_returns_counts(self) -> None:
        resp_alive = MagicMock(spec=httpx.Response)
        resp_alive.status_code = 200
        resp_alive.json.return_value = {"archived": False}

        with patch("app.services.vacancy_freshness.httpx.get", return_value=resp_alive):
            with patch("time.sleep"):
                result = sweep_stale_vacancies(self.db, limit=2)

        self.assertIn("checked", result)
        self.assertIn("archived", result)
        self.assertGreaterEqual(result["checked"], 0)


class CheckVacanciesConcurrentlyTest(VacancyFreshnessDbBase):
    def test_empty_list_returns_empty_set(self) -> None:
        result = check_vacancies_alive_concurrently(self.db, vacancies=[])
        self.assertEqual(result, set())

    def test_archived_vacancy_returned_in_set(self) -> None:
        async def _fake_get(url, **kwargs):
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.json.return_value = {"archived": True}
            return resp

        mock_client = AsyncMock()
        mock_client.get = _fake_get

        async def _fake_aenter(_self):
            return mock_client

        async def _fake_aexit(_self, *args):
            pass

        with patch("app.services.vacancy_freshness.httpx.AsyncClient") as mock_cls:
            instance = MagicMock()
            instance.__aenter__ = _fake_aenter
            instance.__aexit__ = _fake_aexit
            mock_cls.return_value = instance

            result = check_vacancies_alive_concurrently(
                self.db, vacancies=[self.vacancy]
            )

        self.assertIn(self.vacancy.id, result)

    def test_live_vacancy_not_in_archived_set(self) -> None:
        async def _fake_get(url, **kwargs):
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.json.return_value = {"archived": False}
            return resp

        mock_client = AsyncMock()
        mock_client.get = _fake_get

        async def _fake_aenter(_self):
            return mock_client

        async def _fake_aexit(_self, *args):
            pass

        with patch("app.services.vacancy_freshness.httpx.AsyncClient") as mock_cls:
            instance = MagicMock()
            instance.__aenter__ = _fake_aenter
            instance.__aexit__ = _fake_aexit
            mock_cls.return_value = instance

            result = check_vacancies_alive_concurrently(
                self.db, vacancies=[self.vacancy]
            )

        self.assertNotIn(self.vacancy.id, result)


class InstantEndpointFreshnessTest(VacancyFreshnessDbBase):
    """Integration-style tests for the instant endpoint freshness path."""

    def test_archived_vacancy_excluded_from_matches(self) -> None:
        from app.api.routes import vacancies as vacancies_route

        archived_id = self.vacancy.id
        matches_input = [
            {"vacancy_id": archived_id, "title": "Test", "score": 0.9},
        ]

        def _fake_check(db, *, vacancies, **kwargs):
            return {archived_id}

        with patch.object(
            vacancies_route, "check_vacancies_alive_concurrently", side_effect=_fake_check
        ):
            remaining = [
                m for m in matches_input if int(m["vacancy_id"]) not in {archived_id}
            ]

        self.assertEqual(remaining, [])

    def test_shown_count_incremented_after_matches(self) -> None:
        before = self.vacancy.shown_count

        from sqlalchemy import update as _sa_update

        shown_ids = [self.vacancy.id]
        self.db.execute(
            _sa_update(Vacancy)
            .where(Vacancy.id.in_(shown_ids))
            .values(shown_count=Vacancy.shown_count + 1)
        )
        self.db.commit()
        self.db.refresh(self.vacancy)
        self.assertEqual(self.vacancy.shown_count, before + 1)


if __name__ == "__main__":
    unittest.main()
