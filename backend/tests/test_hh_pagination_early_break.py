"""Tests for Level 2 D1 — HH pagination early-break on saturation.

When a fetched HH page has ≥90% URLs already indexed in our DB, keep paging
is wasted work: further pages return the same stale inventory. We stop the
sequential page loop and bump ``pages_truncated_by_indexed`` in
``VacancyParseStats`` so the admin funnel can show the event happened.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services import vacancy_sources
from app.services.vacancy_sources import (
    ALREADY_INDEXED_BREAK_MIN_PAGE_SIZE,
    VacancyParseStats,
    _search_hh_public_api_vacancies,
    vacancy_parse_stats_scope,
)


def _fake_page(page_num: int, size: int) -> list[dict]:
    return [
        {
            "name": f"Vacancy P{page_num}-{i}",
            "alternate_url": f"https://hh.ru/vacancy/{page_num * 1000 + i}",
            "employer": {"name": "ACME"},
            "area": {"name": "Moscow"},
            "snippet": {"requirement": "Python", "responsibility": "Backend"},
        }
        for i in range(size)
    ]


class HHPaginationEarlyBreakTest(unittest.TestCase):
    def test_break_when_probe_reports_high_saturation(self) -> None:
        """If ≥90% of a page's URLs are already indexed, pagination stops."""
        page_size = max(ALREADY_INDEXED_BREAK_MIN_PAGE_SIZE, 30)
        calls: list[int] = []

        def fake_fetch(*, query, per_page, page, date_from):
            calls.append(page)
            return _fake_page(page, page_size)

        def probe_all_indexed(urls: list[str]) -> int:
            return len(urls)

        stats = VacancyParseStats()
        with (
            vacancy_parse_stats_scope(stats),
            patch.object(vacancy_sources, "_fetch_hh_page", side_effect=fake_fetch),
            patch.object(vacancy_sources, "HH_CONCURRENCY", 1),
        ):
            result = _search_hh_public_api_vacancies(
                query="python",
                count=10_000,
                start_page=0,
                already_indexed_probe=probe_all_indexed,
            )

        self.assertGreaterEqual(stats.pages_truncated_by_indexed, 1)
        # Stopped early — did NOT fetch all 20 possible pages.
        self.assertLess(len(calls), 20)
        # Returned what it did fetch up to the break.
        self.assertGreater(len(result), 0)

    def test_no_break_when_probe_reports_fresh_pages(self) -> None:
        """Normal case: pagination runs to natural exhaustion."""
        page_size = 40
        pages_available = 3
        calls: list[int] = []

        def fake_fetch(*, query, per_page, page, date_from):
            calls.append(page)
            if page >= pages_available:
                return []
            return _fake_page(page, page_size)

        def probe_none_indexed(urls: list[str]) -> int:
            return 0

        stats = VacancyParseStats()
        with (
            vacancy_parse_stats_scope(stats),
            patch.object(vacancy_sources, "_fetch_hh_page", side_effect=fake_fetch),
            patch.object(vacancy_sources, "HH_CONCURRENCY", 1),
        ):
            _search_hh_public_api_vacancies(
                query="python",
                count=10_000,
                start_page=0,
                already_indexed_probe=probe_none_indexed,
            )

        self.assertEqual(stats.pages_truncated_by_indexed, 0)

    def test_no_break_on_tiny_pages(self) -> None:
        """A sub-threshold page (< ALREADY_INDEXED_BREAK_MIN_PAGE_SIZE)
        should not trigger the break even if 100% are known — too noisy."""
        tiny_size = max(1, ALREADY_INDEXED_BREAK_MIN_PAGE_SIZE - 5)

        def fake_fetch(*, query, per_page, page, date_from):
            if page == 0:
                return _fake_page(page, tiny_size)
            return []

        def probe_all_indexed(urls: list[str]) -> int:
            return len(urls)

        stats = VacancyParseStats()
        with (
            vacancy_parse_stats_scope(stats),
            patch.object(vacancy_sources, "_fetch_hh_page", side_effect=fake_fetch),
            patch.object(vacancy_sources, "HH_CONCURRENCY", 1),
        ):
            _search_hh_public_api_vacancies(
                query="python",
                count=10_000,
                start_page=0,
                already_indexed_probe=probe_all_indexed,
            )

        self.assertEqual(stats.pages_truncated_by_indexed, 0)

    def test_probe_none_means_no_break(self) -> None:
        """Back-compat: if no probe is passed, pagination behaves as before."""

        def fake_fetch(*, query, per_page, page, date_from):
            if page >= 2:
                return []
            return _fake_page(page, 40)

        stats = VacancyParseStats()
        with (
            vacancy_parse_stats_scope(stats),
            patch.object(vacancy_sources, "_fetch_hh_page", side_effect=fake_fetch),
            patch.object(vacancy_sources, "HH_CONCURRENCY", 1),
        ):
            _search_hh_public_api_vacancies(
                query="python",
                count=10_000,
                start_page=0,
                already_indexed_probe=None,
            )

        self.assertEqual(stats.pages_truncated_by_indexed, 0)


if __name__ == "__main__":
    unittest.main()
