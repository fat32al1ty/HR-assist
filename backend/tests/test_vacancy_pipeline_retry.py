import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services import vacancy_pipeline
from app.services.vacancy_pipeline import discover_and_index_vacancies


class VacancyPipelineRetryTest(unittest.TestCase):
    """Phase 1.9 PR A1: retry triggers when the first pass fetches fewer
    than 5 genuinely-new vacancies, not only when it fetches literally
    zero. The old `indexed==0 AND analyzed==0` guard missed the partial
    case where we'd index 2-3 and call it a day, leaving users watching
    the same top ~40 results forever."""

    @patch.object(vacancy_pipeline, "search_vacancies")
    def test_retry_fires_when_first_pass_indexed_less_than_five(
        self, mock_search: MagicMock
    ) -> None:
        # First pass: nothing. Retry pass: nothing either. We just need to
        # observe that the function kept calling search_vacancies past the
        # first attempt — which it wouldn't have done under the old guard
        # if first-pass indexed > 0 at all.
        mock_search.return_value = []
        db = MagicMock()

        result = discover_and_index_vacancies(
            db,
            query="devops observability",
            count=40,
        )

        # 1 first pass + up to 6 retry attempts = >= 2 total calls.
        self.assertGreaterEqual(mock_search.call_count, 2)
        self.assertEqual(result.metrics.indexed, 0)

    @patch.object(vacancy_pipeline, "search_vacancies")
    def test_retry_does_not_fire_when_first_pass_hits_target(self, mock_search: MagicMock) -> None:
        # Fake items that'll make process_items bump metrics.indexed past
        # the 5-new-results target after the first pass, so retry is
        # skipped entirely.
        fake_items = [
            {
                "source": "hh_api",
                "source_url": f"https://hh.ru/vacancy/{i}",
                "title": "DevOps Engineer",
                "company": "Acme",
                "location": "Москва",
                "raw_text": "Python",
                "raw_payload": {},
            }
            for i in range(6)
        ]
        mock_search.return_value = fake_items

        db = MagicMock()
        # Simulate repository returning no existing vacancy and a freshly
        # created one with a profile attribute. We directly patch the
        # vacancy-pipeline internals to sidestep DB-layer plumbing.
        created = [
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
            for i, item in enumerate(fake_items)
        ]
        call_state = {"idx": 0}

        def _fake_create(*_args, **_kwargs):
            obj = created[call_state["idx"]]
            call_state["idx"] += 1
            return obj

        with (
            patch.object(vacancy_pipeline, "get_vacancy_by_source_url", return_value=None),
            patch.object(vacancy_pipeline, "create_vacancy", side_effect=_fake_create),
            patch.object(
                vacancy_pipeline,
                "analyze_vacancy_text",
                return_value={"is_vacancy": True, "vacancy_confidence": 0.9},
            ),
            patch.object(vacancy_pipeline, "persist_vacancy_profile"),
            patch.object(vacancy_pipeline, "_host_allowed_for_matching", return_value=True),
            patch.object(vacancy_pipeline, "_looks_like_rf_vacancy", return_value=True),
            patch.object(vacancy_pipeline, "_looks_non_vacancy_page", return_value=False),
            patch.object(vacancy_pipeline, "_looks_archived_vacancy_strict", return_value=False),
            patch.object(vacancy_pipeline, "_looks_like_listing_page", return_value=False),
        ):
            discover_and_index_vacancies(db, query="devops", count=40)

        # With indexed >= 5 from the first pass, the guard must skip retry
        # and call search_vacancies exactly once.
        self.assertEqual(mock_search.call_count, 1)


if __name__ == "__main__":
    unittest.main()
