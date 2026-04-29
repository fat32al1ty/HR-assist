"""Prometheus metrics registry.

Single module owns every metric name + label set in the codebase. Service
code calls the helper functions (e.g. `record_search_duration`) instead
of touching `prometheus_client` directly — that keeps the metric surface
auditable from one file.

Counter and Histogram instances are module-level singletons; they live
in the `prometheus_client.REGISTRY` global, which the `/metrics` route
exposition reads.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

search_requests_total = Counter(
    "search_requests_total",
    "Recommendation jobs run, by job_type and terminal status.",
    labelnames=("job_type", "status"),
)

openai_calls_total = Counter(
    "openai_calls_total",
    "OpenAI API calls, by model and status.",
    labelnames=("model", "status"),
)

hh_api_requests_total = Counter(
    "hh_api_requests_total",
    "Outbound calls to api.hh.ru, by HTTP status bucket.",
    labelnames=("status",),
)

segment_warmup_jobs_total = Counter(
    "segment_warmup_jobs_total",
    "Segment-warmup jobs reaching a terminal state.",
    labelnames=("status",),
)

freshness_archived_total = Counter(
    "freshness_archived_total",
    "Vacancies soft-deleted (status='archived') by the freshness pipeline.",
    labelnames=("source",),
)

match_events_total = Counter(
    "match_events_total",
    "User-side match telemetry events received via /api/telemetry/event.",
    labelnames=("event",),
)

# ---------------------------------------------------------------------------
# Histograms
# ---------------------------------------------------------------------------

search_duration_seconds = Histogram(
    "search_duration_seconds",
    "Wall-clock duration of a recommendation job, by job_type.",
    labelnames=("job_type",),
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

openai_call_duration_seconds = Histogram(
    "openai_call_duration_seconds",
    "Wall-clock duration of an OpenAI API call.",
    labelnames=("model",),
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def record_search(*, job_type: str, status: str, duration_seconds: float | None = None) -> None:
    search_requests_total.labels(job_type=job_type, status=status).inc()
    if duration_seconds is not None and duration_seconds >= 0:
        search_duration_seconds.labels(job_type=job_type).observe(duration_seconds)


def record_openai_call(
    *, model: str, status: str = "ok", duration_seconds: float | None = None
) -> None:
    openai_calls_total.labels(model=model, status=status).inc()
    if duration_seconds is not None and duration_seconds >= 0:
        openai_call_duration_seconds.labels(model=model).observe(duration_seconds)


def record_hh_api(*, status_code: int) -> None:
    hh_api_requests_total.labels(status=_status_bucket(status_code)).inc()


def record_segment_warmup(*, status: str) -> None:
    segment_warmup_jobs_total.labels(status=status).inc()


def record_freshness_archived(*, source: str = "hh_api", count: int = 1) -> None:
    if count > 0:
        freshness_archived_total.labels(source=source).inc(count)


def record_match_event(*, event: str) -> None:
    match_events_total.labels(event=event).inc()


def _status_bucket(status_code: int) -> str:
    if status_code <= 0:
        return "network"
    if 200 <= status_code < 300:
        return "2xx"
    if 300 <= status_code < 400:
        return "3xx"
    if 400 <= status_code < 500:
        return f"{status_code}" if status_code in (400, 401, 403, 404, 410, 429) else "4xx"
    if 500 <= status_code < 600:
        return f"{status_code}" if status_code in (500, 502, 503, 504) else "5xx"
    return "other"


def render_metrics() -> tuple[bytes, str]:
    """Return (body, content_type) for the /metrics endpoint."""
    return generate_latest(), CONTENT_TYPE_LATEST
