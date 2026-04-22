import unittest
from datetime import UTC, datetime, timezone
from unittest.mock import MagicMock, patch

from app.services import vacancy_sources
from app.services.vacancy_sources import (
    _format_hh_date_from,
    _search_hh_public_api_vacancies,
)


class FormatHhDateFromTest(unittest.TestCase):
    def test_naive_datetime_is_treated_as_utc(self) -> None:
        naive = datetime(2026, 4, 21, 12, 0, 0)
        formatted = _format_hh_date_from(naive)
        self.assertTrue(formatted.startswith("2026-04-21T12:00:00"))
        # Must include a +0000 / UTC offset, not drop the timezone silently.
        self.assertTrue(formatted.endswith("+0000"))

    def test_aware_datetime_preserves_offset(self) -> None:
        aware = datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC)
        formatted = _format_hh_date_from(aware)
        self.assertTrue(formatted.endswith("+0000"))


class SearchHhApiDateFromTest(unittest.TestCase):
    def _mock_response(self) -> MagicMock:
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"items": []}
        return response

    @patch.object(vacancy_sources, "_hh_get_with_fallback")
    def test_date_from_propagates_to_hh_params(self, mock_get: MagicMock) -> None:
        mock_get.return_value = self._mock_response()
        cursor = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)

        _search_hh_public_api_vacancies(
            query="devops",
            count=40,
            date_from=cursor,
        )

        self.assertGreaterEqual(mock_get.call_count, 1)
        params = mock_get.call_args.kwargs.get("params") or mock_get.call_args[1].get("params")
        self.assertIsNotNone(params)
        self.assertIn("date_from", params)
        self.assertTrue(params["date_from"].startswith("2026-04-21T10:00:00"))

    @patch.object(vacancy_sources, "_hh_get_with_fallback")
    def test_date_from_omitted_when_cursor_none(self, mock_get: MagicMock) -> None:
        mock_get.return_value = self._mock_response()

        _search_hh_public_api_vacancies(query="devops", count=40, date_from=None)

        self.assertGreaterEqual(mock_get.call_count, 1)
        params = mock_get.call_args.kwargs.get("params") or mock_get.call_args[1].get("params")
        self.assertNotIn("date_from", params)


if __name__ == "__main__":
    unittest.main()
