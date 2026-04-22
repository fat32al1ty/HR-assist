import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.services import vacancy_sources
from app.services.vacancy_sources import (
    HH_CONCURRENCY,
    _search_hh_public_api_vacancies,
    search_vacancies,
)


def _mock_response(items: list[dict]) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"items": items}
    return response


def _make_hh_item(vid: int) -> dict:
    return {
        "name": f"Backend Engineer {vid}",
        "alternate_url": f"https://hh.ru/vacancy/{vid}",
        "employer": {"name": "Acme"},
        "area": {"name": "Москва"},
        "snippet": {"requirement": "Python", "responsibility": "APIs"},
    }


class ParallelHhPaginationTest(unittest.TestCase):
    """Phase 2.0 PR A3 — HH pagination runs in parallel, not sequentially.

    We verify two properties that matter for the first-run UX:
    1. Concurrent page fetches genuinely overlap in time (wall-clock
       shrinks vs. sequential).
    2. Per-page HTTP errors are logged but do not tear down the whole
       search — other pages' items still flow through.
    """

    def test_pages_are_fetched_in_parallel(self) -> None:
        in_flight = 0
        max_concurrent = 0
        lock = threading.Lock()

        def _slow_fetch(*_args, **kwargs):
            nonlocal in_flight, max_concurrent
            with lock:
                in_flight += 1
                max_concurrent = max(max_concurrent, in_flight)
            time.sleep(0.05)
            with lock:
                in_flight -= 1
            # Return empty so the search finishes without extra iterations.
            return _mock_response([])

        with patch.object(vacancy_sources, "_hh_get_with_fallback", side_effect=_slow_fetch):
            _search_hh_public_api_vacancies(query="backend", count=40)

        self.assertGreaterEqual(max_concurrent, 2)

    def test_page_error_is_logged_but_does_not_abort_search(self) -> None:
        call_state = {"n": 0}
        state_lock = threading.Lock()

        def _mixed_fetch(*_args, **kwargs):
            with state_lock:
                call_state["n"] += 1
                nth = call_state["n"]
            if nth == 1:
                request = httpx.Request("GET", "https://api.hh.ru/vacancies")
                response = httpx.Response(status_code=503, request=request, text="maintenance")
                raise httpx.HTTPStatusError("503", request=request, response=response)
            return _mock_response([_make_hh_item(100 + nth)])

        with patch.object(vacancy_sources, "_hh_get_with_fallback", side_effect=_mixed_fetch):
            with self.assertLogs(vacancy_sources.logger, level="WARNING") as cm:
                result = _search_hh_public_api_vacancies(query="backend", count=40)

        self.assertTrue(any("hh_api_http_error" in line for line in cm.output))
        # At least one surviving page produced a vacancy — the failing
        # page was isolated, not fatal.
        self.assertGreaterEqual(len(result), 1)

    def test_first_wave_size_matches_hh_concurrency(self) -> None:
        # When the first wave returns nothing, the search short-circuits
        # — so exactly HH_CONCURRENCY calls happen in that case.
        def _empty(*_args, **_kwargs):
            return _mock_response([])

        with patch.object(vacancy_sources, "_hh_get_with_fallback", side_effect=_empty) as mock:
            _search_hh_public_api_vacancies(query="backend", count=40)

        self.assertEqual(mock.call_count, HH_CONCURRENCY)


class SearchVacanciesFailureLoggingTest(unittest.TestCase):
    """search_vacancies used to swallow HH failures silently. Now any
    uncaught exception from the underlying search is logged so operators
    can see why the index stopped growing."""

    def test_hh_search_failure_is_logged(self) -> None:
        def _boom(*_args, **_kwargs):
            raise RuntimeError("network nuked")

        with patch.object(vacancy_sources, "_search_hh_public_api_vacancies", side_effect=_boom):
            with self.assertLogs(vacancy_sources.logger, level="WARNING") as cm:
                result = search_vacancies(query="backend", count=40)

        self.assertEqual(result, [])
        self.assertTrue(any("hh_search_failed" in line for line in cm.output))


if __name__ == "__main__":
    unittest.main()
