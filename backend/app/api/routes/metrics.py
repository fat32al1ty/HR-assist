"""GET /metrics — Prometheus exposition.

No auth: in prod Caddy already restricts the upstream, and Prometheus
metrics are not sensitive (no user identifiers, no payloads). If we ever
expose this endpoint outside the cluster we'll add a simple shared-secret
check; for now keep the surface minimal.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.services.metrics_registry import render_metrics

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)
