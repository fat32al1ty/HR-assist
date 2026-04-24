"""Unit tests for Phase v0.9.4 — two silent-drop counters in _collect_eligible.

Silent drop #1: fetched_dropped_analyzed_budget
  When max_analyzed is exhausted, the remaining items in found_items are
  skipped without entering the pipeline. We must count unique skipped URLs.

Silent drop #2: fetched_dedup_within_job
  When the same source_url appears across multiple search_vacancies calls
  (or within a single call), the duplicate is dropped silently. We count it.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services import vacancy_pipeline
from app.services.vacancy_pipeline import discover_and_index_vacancies


def _make_items(urls: list[str]) -> list[dict]:
    return [
        {
            "source": "hh_api",
            "source_url": url,
            "title": "Backend Dev",
            "company": "Acme",
            "location": "Москва",
            "raw_text": "Python FastAPI",
            "raw_payload": {},
        }
        for url in urls
    ]


def _make_vacancy(url: str, idx: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=idx,
        source_url=url,
        title="Backend Dev",
        company="Acme",
        status="pending",
        profile=None,
        raw_text="Python FastAPI",
        location="Москва",
        error_message=None,
    )


def _base_patches(vacancies_by_url: dict):
    """Return a patch.multiple context that bypasses DB and LLM calls."""
    call_state = {"idx": 0}

    def _fake_create(*_args, **kwargs):
        url = kwargs.get("source_url") or _args[1] if _args else None
        # Fall back to sequential allocation if URL not available
        obj = vacancies_by_url.get(url) or list(vacancies_by_url.values())[call_state["idx"]]
        call_state["idx"] = min(call_state["idx"] + 1, len(vacancies_by_url) - 1)
        return obj

    return patch.multiple(
        vacancy_pipeline,
        get_vacancy_by_source_url=MagicMock(return_value=None),
        create_vacancy=MagicMock(side_effect=_fake_create),
        analyze_vacancy_text=MagicMock(
            return_value={"is_vacancy": True, "vacancy_confidence": 0.9}
        ),
        persist_vacancy_profile=MagicMock(),
        _host_allowed_for_matching=MagicMock(return_value=True),
        _looks_like_rf_vacancy=MagicMock(return_value=True),
        _looks_non_vacancy_page=MagicMock(return_value=False),
        _looks_archived_vacancy_strict=MagicMock(return_value=False),
        _looks_like_listing_page=MagicMock(return_value=False),
    )


class BudgetDropTest(unittest.TestCase):
    def test_budget_stop_counts_dropped_fetched(self) -> None:
        """50 unique URLs, max_analyzed=5 → at least 45 counted as budget-dropped."""
        urls = [f"https://hh.ru/vacancy/{i}" for i in range(50)]
        items = _make_items(urls)
        vacancies_by_url = {url: _make_vacancy(url, idx) for idx, url in enumerate(urls)}

        db = MagicMock()
        patches = _base_patches(vacancies_by_url)
        with patch.object(vacancy_pipeline, "search_vacancies", return_value=items), patches:
            result = discover_and_index_vacancies(
                db, query="backend", count=50, max_analyzed=5, force_reindex=True
            )

        # fetched=6 (items 0-4 eligible + item 5 triggers stop_processing),
        # dropped=44 (items 6-49).  Together they account for all 50 unique URLs.
        self.assertGreaterEqual(
            result.metrics.fetched_dropped_analyzed_budget,
            44,
            msg=(
                f"Expected ≥44 budget-dropped, got "
                f"{result.metrics.fetched_dropped_analyzed_budget}"
            ),
        )

    def test_budget_dropped_urls_not_double_counted_as_fetched(self) -> None:
        """URLs that hit the budget cap must NOT inflate metrics.fetched."""
        urls = [f"https://hh.ru/vacancy/{i}" for i in range(20)]
        items = _make_items(urls)
        vacancies_by_url = {url: _make_vacancy(url, idx) for idx, url in enumerate(urls)}

        db = MagicMock()
        patches = _base_patches(vacancies_by_url)
        with patch.object(vacancy_pipeline, "search_vacancies", return_value=items), patches:
            result = discover_and_index_vacancies(
                db, query="backend", count=20, max_analyzed=3, force_reindex=True
            )

        total_accounted = (
            result.metrics.fetched
            + result.metrics.fetched_dropped_analyzed_budget
        )
        self.assertLessEqual(
            total_accounted,
            len(urls),
            msg=(
                f"fetched ({result.metrics.fetched}) + "
                f"fetched_dropped_analyzed_budget "
                f"({result.metrics.fetched_dropped_analyzed_budget}) "
                f"must not exceed total unique URLs ({len(urls)})"
            ),
        )


class WithinJobDedupTest(unittest.TestCase):
    def test_within_job_dedup_counts_skipped(self) -> None:
        """3 items where 2 are duplicate URLs → fetched_dedup_within_job == 2."""
        url_a = "https://hh.ru/vacancy/1001"
        url_b = "https://hh.ru/vacancy/1002"
        # url_a appears three times total, url_b once — 2 duplicates of url_a
        items = _make_items([url_a, url_b, url_a, url_a])
        vacancies_by_url = {
            url_a: _make_vacancy(url_a, 0),
            url_b: _make_vacancy(url_b, 1),
        }

        db = MagicMock()
        patches = _base_patches(vacancies_by_url)
        with patch.object(vacancy_pipeline, "search_vacancies", return_value=items), patches:
            result = discover_and_index_vacancies(
                db, query="backend", count=10, force_reindex=True
            )

        self.assertEqual(
            result.metrics.fetched_dedup_within_job,
            2,
            msg=(
                f"Expected 2 within-job dedup drops, got "
                f"{result.metrics.fetched_dedup_within_job}"
            ),
        )

    def test_dedup_does_not_increment_fetched(self) -> None:
        """Duplicate URLs must not inflate metrics.fetched."""
        url = "https://hh.ru/vacancy/9999"
        items = _make_items([url, url, url])
        vacancies_by_url = {url: _make_vacancy(url, 0)}

        db = MagicMock()
        patches = _base_patches(vacancies_by_url)
        with patch.object(vacancy_pipeline, "search_vacancies", return_value=items), patches:
            result = discover_and_index_vacancies(
                db, query="backend", count=10, force_reindex=True
            )

        self.assertEqual(
            result.metrics.fetched,
            1,
            msg=f"Only 1 unique URL should be fetched, got {result.metrics.fetched}",
        )
        self.assertEqual(
            result.metrics.fetched_dedup_within_job,
            2,
            msg=f"Expected 2 dedup drops, got {result.metrics.fetched_dedup_within_job}",
        )


if __name__ == "__main__":
    unittest.main()
