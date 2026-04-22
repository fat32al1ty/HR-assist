import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services import vacancy_pipeline
from app.services.openai_usage import OpenAIBudgetExceeded, OpenAIUsageSnapshot
from app.services.vacancy_pipeline import discover_and_index_vacancies


def _budget_exhausted_snapshot() -> OpenAIUsageSnapshot:
    return OpenAIUsageSnapshot(
        prompt_tokens=0,
        completion_tokens=0,
        embedding_tokens=0,
        total_tokens=0,
        api_calls=0,
        estimated_cost_usd=1.0,
        budget_usd=0.5,
        budget_exceeded=True,
        budget_enforced=True,
    )


def _make_fake_items(n: int) -> list[dict]:
    return [
        {
            "source": "hh_api",
            "source_url": f"https://hh.ru/vacancy/{i}",
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Москва",
            "raw_text": "Python FastAPI",
            "raw_payload": {},
        }
        for i in range(n)
    ]


def _make_fake_vacancies(items: list[dict]) -> list:
    return [
        SimpleNamespace(
            id=i,
            source_url=item["source_url"],
            title=item["title"],
            company=item["company"],
            status="pending",
            profile=None,
            raw_text=item["raw_text"],
            location=item["location"],
            error_message=None,
        )
        for i, item in enumerate(items)
    ]


class ParallelLLMAnalysisTest(unittest.TestCase):
    """Phase 2.0 PR A2 — LLM parse goes from sequential to ThreadPool.

    We verify three properties that matter for correctness:
    1. Multiple analyze_vacancy_text calls genuinely overlap in time.
    2. A single analyzer exception is isolated to that one vacancy (others
       still get persisted with profiles).
    3. OpenAIBudgetExceeded from any worker re-raises out of the batch,
       so the pipeline short-circuits instead of retrying forever.
    """

    def _patched_pipeline(self, items, analyzer):
        vacancies = _make_fake_vacancies(items)
        call_state = {"idx": 0}

        def _fake_create(*_args, **_kwargs):
            obj = vacancies[call_state["idx"]]
            call_state["idx"] += 1
            return obj

        return patch.multiple(
            vacancy_pipeline,
            get_vacancy_by_source_url=MagicMock(return_value=None),
            create_vacancy=MagicMock(side_effect=_fake_create),
            analyze_vacancy_text=MagicMock(side_effect=analyzer),
            persist_vacancy_profile=MagicMock(),
            _host_allowed_for_matching=MagicMock(return_value=True),
            _looks_like_rf_vacancy=MagicMock(return_value=True),
            _looks_non_vacancy_page=MagicMock(return_value=False),
            _looks_archived_vacancy_strict=MagicMock(return_value=False),
            _looks_like_listing_page=MagicMock(return_value=False),
        ), vacancies

    def test_multiple_analyses_overlap_in_time(self) -> None:
        items = _make_fake_items(6)
        in_flight = 0
        max_concurrent = 0
        lock = threading.Lock()

        def _slow_analyze(_text: str) -> dict:
            nonlocal in_flight, max_concurrent
            with lock:
                in_flight += 1
                max_concurrent = max(max_concurrent, in_flight)
            time.sleep(0.05)
            with lock:
                in_flight -= 1
            return {"is_vacancy": True, "vacancy_confidence": 0.9}

        patcher, _ = self._patched_pipeline(items, _slow_analyze)
        db = MagicMock()
        with patch.object(vacancy_pipeline, "search_vacancies", return_value=items), patcher:
            discover_and_index_vacancies(db, query="backend", count=10)

        # At least 2 workers ran simultaneously — proves we left the
        # sequential world behind without coupling to the exact sem value.
        self.assertGreaterEqual(max_concurrent, 2)

    def test_single_analyzer_exception_is_isolated(self) -> None:
        items = _make_fake_items(3)
        call_count = {"n": 0}
        call_lock = threading.Lock()

        def _mixed_analyze(_text: str) -> dict:
            with call_lock:
                call_count["n"] += 1
                current = call_count["n"]
            if current == 2:
                raise RuntimeError("transient analyzer failure")
            return {"is_vacancy": True, "vacancy_confidence": 0.9}

        patcher, _ = self._patched_pipeline(items, _mixed_analyze)
        db = MagicMock()
        with patch.object(vacancy_pipeline, "search_vacancies", return_value=items), patcher:
            result = discover_and_index_vacancies(db, query="backend", count=10)

        self.assertEqual(result.metrics.failed, 1)
        self.assertEqual(result.metrics.indexed, 2)
        self.assertEqual(result.metrics.analyzed, 3)

    def test_budget_exceeded_propagates(self) -> None:
        items = _make_fake_items(4)

        def _budget_blown(_text: str) -> dict:
            raise OpenAIBudgetExceeded(_budget_exhausted_snapshot())

        patcher, _ = self._patched_pipeline(items, _budget_blown)
        db = MagicMock()
        with patch.object(vacancy_pipeline, "search_vacancies", return_value=items), patcher:
            with self.assertRaises(OpenAIBudgetExceeded):
                discover_and_index_vacancies(db, query="backend", count=10)


if __name__ == "__main__":
    unittest.main()
