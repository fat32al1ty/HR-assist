"""Tests for the salary baseline cache and lookup."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.services.salary_baseline import (
    MIN_BASELINE_SUPPORT,
    SalaryBaselineCache,
    get_baseline_band,
)


def _make_db_row(role_family, seniority, location, salary_min, salary_max):
    return ({"role_family": role_family, "seniority": seniority, "location": location}, salary_min, salary_max)


def _build_cache_from_rows(rows):
    """Build a fresh SalaryBaselineCache using mocked DB rows."""
    cache = SalaryBaselineCache()

    mock_db = MagicMock()

    class _FakeResult:
        def __init__(self, data):
            self._data = data

        def all(self):
            return self._data

        def __iter__(self):
            return iter(self._data)

    mock_db.execute.return_value = _FakeResult(rows)

    cache.rebuild(mock_db)
    return cache


class TestBaselineReturnsNoneWhenNoSupport(unittest.TestCase):
    def test_empty_db(self):
        cache = _build_cache_from_rows([])
        result = cache.lookup(
            role_family="software_engineering", seniority="middle", city="Москва", db=MagicMock()
        )
        self.assertIsNone(result)

    def test_insufficient_support(self):
        # 4 rows for the triple key — below MIN_BASELINE_SUPPORT (5)
        rows = [_make_db_row("software_engineering", "middle", "Москва", 100000, 150000)] * 4
        cache = _build_cache_from_rows(rows)
        result = cache.lookup(
            role_family="software_engineering", seniority="middle", city="Москва", db=MagicMock()
        )
        self.assertIsNone(result)


class TestBaselineUsesTripleKey(unittest.TestCase):
    def test_triple_key_returned_when_support_sufficient(self):
        rows = [_make_db_row("software_engineering", "middle", "Москва", 90000, 110000)] * 6
        cache = _build_cache_from_rows(rows)
        result = cache.lookup(
            role_family="software_engineering", seniority="middle", city="москва", db=MagicMock()
        )
        self.assertIsNotNone(result)
        self.assertGreater(result.p50, 0)
        self.assertGreaterEqual(result.support, MIN_BASELINE_SUPPORT)

    def test_confidence_capped_at_0_6(self):
        # 30+ rows → confidence should cap at 0.6
        rows = [_make_db_row("software_engineering", "middle", "Москва", 100000, 200000)] * 35
        cache = _build_cache_from_rows(rows)
        result = cache.lookup(
            role_family="software_engineering", seniority="middle", city="москва", db=MagicMock()
        )
        self.assertIsNotNone(result)
        self.assertLessEqual(result.confidence, 0.6)


class TestBaselineFallbackToPair(unittest.TestCase):
    def test_falls_back_to_pair_when_triple_thin(self):
        # Only 2 rows with the triple match, but 10 rows for (role, seniority)
        triple_rows = [_make_db_row("software_engineering", "middle", "Москва", 100000, 120000)] * 2
        pair_rows = [_make_db_row("software_engineering", "middle", "Казань", 90000, 110000)] * 10
        rows = triple_rows + pair_rows

        cache = _build_cache_from_rows(rows)
        # Ask for triple key that only has 2 rows (below floor)
        result = cache.lookup(
            role_family="software_engineering", seniority="middle", city="москва", db=MagicMock()
        )
        # Should fall back to pair key (role, seniority) which has 12 rows total
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.support, MIN_BASELINE_SUPPORT)


class TestBaselineCacheRefreshesAfterTtl(unittest.TestCase):
    def test_cache_rebuilds_after_ttl(self):
        rows = [_make_db_row("software_engineering", "middle", "Москва", 100000, 150000)] * 6
        cache = _build_cache_from_rows(rows)

        # Simulate TTL expiry by resetting _built_at to long ago
        cache._built_at = 0.0

        mock_db = MagicMock()

        class _FakeResult:
            def __init__(self, data):
                self._data = data

            def all(self):
                return self._data

            def __iter__(self):
                return iter(self._data)

        # Return empty rows on rebuild — should clear the cache
        mock_db.execute.return_value = _FakeResult([])

        result = cache.lookup(
            role_family="software_engineering", seniority="middle", city="москва", db=mock_db
        )
        # After rebuild with empty rows, should return None
        self.assertIsNone(result)
        # Verify rebuild was called
        mock_db.execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
