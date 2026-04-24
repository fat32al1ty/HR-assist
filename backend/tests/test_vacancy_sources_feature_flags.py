"""Tests for feature-flag gating in search_vacancies."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.services import vacancy_sources
from app.services.vacancy_sources import search_vacancies


def _make_vacancy(n: int = 1) -> list[dict]:
    return [
        {
            "title": f"Vacancy {i}",
            "source_url": f"https://hh.ru/vacancy/{i}",
            "source": "hh_api",
            "description": "Python developer",
        }
        for i in range(n)
    ]


class SearchVacanciesFeatureFlagsTest(unittest.TestCase):
    def _patch_enrich(self):
        return patch.object(vacancy_sources, "_enrich_preview", side_effect=lambda x: x)

    def test_hh_always_active(self) -> None:
        with (
            patch.object(
                vacancy_sources,
                "_search_hh_public_api_vacancies",
                return_value=_make_vacancy(3),
            ) as mock_hh,
            patch.object(
                vacancy_sources, "_search_superjob_api_vacancies", return_value=[]
            ),
            patch.object(vacancy_sources, "_search_habr_api_vacancies", return_value=[]),
            patch.object(vacancy_sources, "_search_public_sources", return_value=[]),
            self._patch_enrich(),
        ):
            result = search_vacancies(query="python", count=10)
        mock_hh.assert_called_once()
        self.assertEqual(len(result), 3)

    def test_superjob_disabled_by_default(self) -> None:
        with (
            patch.object(
                vacancy_sources,
                "_search_hh_public_api_vacancies",
                return_value=[],
            ),
            patch.object(
                vacancy_sources, "_search_superjob_api_vacancies", return_value=[]
            ) as mock_sj,
            patch.object(vacancy_sources, "_search_habr_api_vacancies", return_value=[]),
            patch.object(vacancy_sources, "_search_public_sources", return_value=[]),
            self._patch_enrich(),
        ):
            search_vacancies(query="python", count=10)
        mock_sj.assert_not_called()

    def test_superjob_enabled_with_flag_and_key(self, monkeypatch=None) -> None:
        with (
            patch.object(vacancy_sources.settings, "feature_superjob_enabled", True),
            patch.object(vacancy_sources.settings, "superjob_api_key", "testkey"),
            patch.object(
                vacancy_sources,
                "_search_hh_public_api_vacancies",
                return_value=[],
            ),
            patch.object(
                vacancy_sources,
                "_search_superjob_api_vacancies",
                return_value=_make_vacancy(2),
            ) as mock_sj,
            patch.object(vacancy_sources, "_search_habr_api_vacancies", return_value=[]),
            patch.object(vacancy_sources, "_search_public_sources", return_value=[]),
            self._patch_enrich(),
        ):
            search_vacancies(query="python", count=10)
        mock_sj.assert_called_once()

    def test_superjob_enabled_without_key_is_noop(self) -> None:
        with (
            patch.object(vacancy_sources.settings, "feature_superjob_enabled", True),
            patch.object(vacancy_sources.settings, "superjob_api_key", None),
            patch.object(
                vacancy_sources,
                "_search_hh_public_api_vacancies",
                return_value=[],
            ),
            patch.object(
                vacancy_sources, "_search_superjob_api_vacancies", return_value=[]
            ) as mock_sj,
            patch.object(vacancy_sources, "_search_habr_api_vacancies", return_value=[]),
            patch.object(vacancy_sources, "_search_public_sources", return_value=[]),
            self._patch_enrich(),
        ):
            search_vacancies(query="python", count=10)
        mock_sj.assert_not_called()

    def test_habr_enabled_with_flag_and_token(self) -> None:
        with (
            patch.object(vacancy_sources.settings, "feature_habr_enabled", True),
            patch.object(vacancy_sources.settings, "habr_career_api_token", "tok"),
            patch.object(
                vacancy_sources,
                "_search_hh_public_api_vacancies",
                return_value=[],
            ),
            patch.object(vacancy_sources, "_search_superjob_api_vacancies", return_value=[]),
            patch.object(
                vacancy_sources,
                "_search_habr_api_vacancies",
                return_value=_make_vacancy(1),
            ) as mock_habr,
            patch.object(vacancy_sources, "_search_public_sources", return_value=[]),
            self._patch_enrich(),
        ):
            search_vacancies(query="python", count=10)
        mock_habr.assert_called_once()

    def test_public_sources_flag_gates_scraping(self) -> None:
        with (
            patch.object(vacancy_sources.settings, "feature_public_sources_enabled", True),
            patch.object(
                vacancy_sources,
                "_search_hh_public_api_vacancies",
                return_value=[],
            ),
            patch.object(vacancy_sources, "_search_superjob_api_vacancies", return_value=[]),
            patch.object(vacancy_sources, "_search_habr_api_vacancies", return_value=[]),
            patch.object(
                vacancy_sources,
                "_search_public_sources",
                return_value=_make_vacancy(2),
            ) as mock_pub,
            self._patch_enrich(),
        ):
            search_vacancies(query="python", count=10)
        mock_pub.assert_called_once()

    def test_source_exception_does_not_fail_others(self) -> None:
        with (
            patch.object(vacancy_sources.settings, "feature_superjob_enabled", True),
            patch.object(vacancy_sources.settings, "superjob_api_key", "key"),
            patch.object(
                vacancy_sources,
                "_search_hh_public_api_vacancies",
                return_value=_make_vacancy(2),
            ),
            patch.object(
                vacancy_sources,
                "_search_superjob_api_vacancies",
                side_effect=RuntimeError("network failure"),
            ),
            patch.object(vacancy_sources, "_search_habr_api_vacancies", return_value=[]),
            patch.object(vacancy_sources, "_search_public_sources", return_value=[]),
            self._patch_enrich(),
        ):
            result = search_vacancies(query="python", count=10)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
