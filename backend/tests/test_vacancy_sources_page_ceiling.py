"""v0.22.1: HH page-ceiling clamp tests.

HH public API rejects (page+1) * per_page > 2000 with a 400 "you can't
look up more than 2000 items in the list". With per_page=100 the hard
ceiling is page index 19. The retry-rotation path used to produce
start_page values up to 90, burning ~8 HH calls per retry on guaranteed
400s. This test guards the clamp.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.services import vacancy_sources
from app.services.vacancy_sources import _search_hh_public_api_vacancies


class HhPageCeilingTest(unittest.TestCase):
    def test_start_page_above_ceiling_returns_empty_without_calling_hh(self) -> None:
        """start_page=20 (== ceiling) must short-circuit — no HH calls."""
        with patch.object(vacancy_sources, "_hh_get_with_fallback") as mock_get:
            result = _search_hh_public_api_vacancies(query="python", count=40, start_page=20)
        self.assertEqual(result, [])
        mock_get.assert_not_called()

    def test_start_page_well_above_ceiling_returns_empty(self) -> None:
        """start_page=90 (the legacy worst case) must short-circuit."""
        with patch.object(vacancy_sources, "_hh_get_with_fallback") as mock_get:
            result = _search_hh_public_api_vacancies(query="python", count=40, start_page=90)
        self.assertEqual(result, [])
        mock_get.assert_not_called()

    def test_start_page_below_ceiling_does_call_hh(self) -> None:
        """Sanity: start_page=0 still hits the API."""
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"items": []}
        with patch.object(
            vacancy_sources, "_hh_get_with_fallback", return_value=response
        ) as mock_get:
            _search_hh_public_api_vacancies(query="python", count=40, start_page=0)
        self.assertGreater(mock_get.call_count, 0)


if __name__ == "__main__":
    unittest.main()
