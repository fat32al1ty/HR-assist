"""Request-ID middleware (pure ASGI implementation).

Every HTTP request gets a UUID. If the client supplied an `X-Request-ID`
header we trust it (so a frontend or upstream Caddy can correlate to its
own trace), otherwise we generate one. The id is exposed:

- in the response `X-Request-ID` header,
- via `current_request_id()` for service-layer code that wants to embed
  it in a log line or DB row,
- via the `RequestIdLogFilter` so every standard-logging line under the
  request gets the same id automatically.

Implementation note: implemented as a pure ASGI middleware (not
`BaseHTTPMiddleware`) because Starlette's BaseHTTPMiddleware has a
regression where `await call_next(request)` re-buffers the request body
in a way that breaks Pydantic body parsing for downstream endpoints. We
only need to manipulate headers, so the raw ASGI form is enough and
avoids the body-stream interaction entirely.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

REQUEST_ID_HEADER_BYTES = b"x-request-id"
REQUEST_ID_HEADER = "X-Request-ID"
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    return _request_id_var.get()


def _coerce_inbound(value: str | None) -> str | None:
    if not value:
        return None
    trimmed = value.strip()
    if not trimmed or len(trimmed) > 64:
        return None
    return trimmed


class RequestIdMiddleware:
    """Pure ASGI middleware. Extracts (or generates) X-Request-ID and
    echoes it on the response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        inbound: str | None = None
        for name, value in scope.get("headers", ()):
            if name == REQUEST_ID_HEADER_BYTES:
                try:
                    inbound = value.decode("latin-1")
                except Exception:
                    inbound = None
                break
        request_id = _coerce_inbound(inbound) or uuid.uuid4().hex
        token = _request_id_var.set(request_id)

        async def send_with_header(message):
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append(
                    (REQUEST_ID_HEADER_BYTES, request_id.encode("latin-1"))
                )
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            _request_id_var.reset(token)


class RequestIdLogFilter(logging.Filter):
    """Adds `request_id` as a record attribute so a structured formatter
    can emit it. Logs outside an HTTP request get `-`."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id() or "-"
        return True
