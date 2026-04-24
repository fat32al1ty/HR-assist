"""Unit tests for ``_merge_metrics``.

The interactive recommender runs ``discover_and_index_vacancies`` multiple
times (prefetch → deep scan → retry) and then merges each result into one
``aggregate`` before writing to ``recommendation_jobs.metrics``. The merge
must SUM integer counters — an earlier bug overwrote them, so the admin
waterfall under-counted drops whenever the pipeline made more than one pass.
"""

from __future__ import annotations

import unittest
from dataclasses import fields as dataclass_fields

from app.services.vacancy_pipeline import VacancyDiscoveryMetrics
from app.services.vacancy_recommendation import _METRIC_INT_FIELDS, _merge_metrics


class MergeMetricsTest(unittest.TestCase):
    def test_all_int_fields_are_accumulated(self) -> None:
        a = VacancyDiscoveryMetrics(sources=[])
        b = VacancyDiscoveryMetrics(sources=[])
        for idx, name in enumerate(_METRIC_INT_FIELDS, start=1):
            setattr(a, name, idx)
            setattr(b, name, idx * 2)

        merged = _merge_metrics(a, b)

        for idx, name in enumerate(_METRIC_INT_FIELDS, start=1):
            self.assertEqual(
                getattr(merged, name),
                idx + idx * 2,
                msg=f"{name} should be summed (a={idx} + b={idx * 2})",
            )

    def test_merge_across_three_runs_is_cumulative(self) -> None:
        """Regression for the original bug: the final aggregate must reflect
        every pass, not just the last one."""
        aggregate = VacancyDiscoveryMetrics(sources=[])
        for run_count in (1, 2, 3):
            run = VacancyDiscoveryMetrics(sources=[])
            run.fetched = 100
            run.analyzed = 10
            run.search_dedup_skipped = 5
            run.filtered_host_not_allowed = 2
            aggregate = _merge_metrics(aggregate, run)
            self.assertEqual(aggregate.fetched, 100 * run_count)
            self.assertEqual(aggregate.analyzed, 10 * run_count)
            self.assertEqual(aggregate.search_dedup_skipped, 5 * run_count)
            self.assertEqual(aggregate.filtered_host_not_allowed, 2 * run_count)

    def test_sources_deduplicated_across_runs(self) -> None:
        a = VacancyDiscoveryMetrics(sources=["https://hh.ru/1", "https://hh.ru/2"])
        b = VacancyDiscoveryMetrics(sources=["https://hh.ru/2", "https://hh.ru/3"])
        merged = _merge_metrics(a, b)
        self.assertEqual(
            merged.sources,
            ["https://hh.ru/1", "https://hh.ru/2", "https://hh.ru/3"],
        )

    def test_metric_int_fields_cover_all_int_dataclass_fields(self) -> None:
        """Guard against adding a new int field to VacancyDiscoveryMetrics
        without wiring it into _METRIC_INT_FIELDS — which would silently
        zero the counter on merge."""
        int_fields = {
            f.name
            for f in dataclass_fields(VacancyDiscoveryMetrics)
            if f.type is int or f.type == "int"
        }
        missing = int_fields.difference(_METRIC_INT_FIELDS)
        self.assertFalse(
            missing,
            msg=f"VacancyDiscoveryMetrics has int fields not in _METRIC_INT_FIELDS: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
