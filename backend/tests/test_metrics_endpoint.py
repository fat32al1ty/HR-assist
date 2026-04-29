"""v0.23.0: GET /metrics returns Prometheus exposition format."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services.metrics_registry import (
    record_freshness_archived,
    record_hh_api,
    record_match_event,
    record_openai_call,
    record_search,
    record_segment_warmup,
)


class PrometheusMetricsEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_metrics_endpoint_returns_text_plain_with_expected_metrics(self) -> None:
        # Pre-bump every counter once so a fresh registry has at least one
        # sample in each series — Prometheus exposition includes a HELP+TYPE
        # block for any metric that has been touched, which is what we want
        # to assert against.
        record_search(job_type="instant", status="ok", duration_seconds=0.42)
        record_openai_call(model="gpt-test", status="ok", duration_seconds=0.11)
        record_hh_api(status_code=200)
        record_segment_warmup(status="completed")
        record_freshness_archived(source="hh_api", count=1)
        record_match_event(event="track_section_expanded")

        resp = self.client.get("/api/metrics")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/plain", resp.headers.get("content-type", ""))
        body = resp.text

        for metric in (
            "search_requests_total",
            "search_duration_seconds",
            "openai_calls_total",
            "openai_call_duration_seconds",
            "hh_api_requests_total",
            "segment_warmup_jobs_total",
            "freshness_archived_total",
            "match_events_total",
        ):
            self.assertIn(metric, body, f"missing metric: {metric}")

    def test_hh_status_buckets(self) -> None:
        from app.services.metrics_registry import _status_bucket

        self.assertEqual(_status_bucket(200), "2xx")
        self.assertEqual(_status_bucket(404), "404")
        self.assertEqual(_status_bucket(429), "429")
        self.assertEqual(_status_bucket(418), "4xx")
        self.assertEqual(_status_bucket(503), "503")
        self.assertEqual(_status_bucket(0), "network")
        self.assertEqual(_status_bucket(-1), "network")


if __name__ == "__main__":
    unittest.main()
