from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from app.core.config import settings

_TRACKER: ContextVar[OpenAIUsageTracker | None] = ContextVar("openai_usage_tracker", default=None)

# Dedicated logger name so operators can grep/filter ("docker logs | grep OPENAI_CALL").
OPENAI_CALL_LOGGER = logging.getLogger("openai_call")
OPENAI_CALL_EVENT = "OPENAI_CALL"

DAILY_BUDGET_USER_MESSAGE = (
    "Дневной лимит OpenAI исчерпан. Попробуйте снова завтра "
    "или свяжитесь с администратором, чтобы поднять лимит."
)


def compute_responses_cost_usd(*, input_tokens: int, output_tokens: int) -> float:
    safe_input = max(0, int(input_tokens))
    safe_output = max(0, int(output_tokens))
    return (
        (safe_input / 1_000_000.0) * settings.openai_responses_input_usd_per_1m
        + (safe_output / 1_000_000.0) * settings.openai_responses_output_usd_per_1m
    ) * settings.openai_cost_safety_multiplier


def compute_embeddings_cost_usd(*, input_tokens: int) -> float:
    safe_input = max(0, int(input_tokens))
    return (
        (safe_input / 1_000_000.0) * settings.openai_embeddings_input_usd_per_1m
    ) * settings.openai_cost_safety_multiplier


def log_openai_call(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    user_id: int | None,
    duration_ms: int,
    event: str = OPENAI_CALL_EVENT,
) -> None:
    """Emit one JSON line per OpenAI call for audit + cost attribution.

    v0.23.0: also writes a persistent row to `openai_call_log` and bumps
    the Prometheus counter+histogram. Both DB write and counter are
    best-effort — never let observability break an OpenAI request.
    """
    safe_prompt = int(max(0, prompt_tokens))
    safe_completion = int(max(0, completion_tokens))
    safe_cost = round(float(cost_usd), 6)
    safe_duration_ms = int(max(0, duration_ms))

    payload = {
        "event": event,
        "model": model,
        "prompt_tokens": safe_prompt,
        "completion_tokens": safe_completion,
        "cost_usd": safe_cost,
        "user_id": user_id,
        "duration_ms": safe_duration_ms,
    }
    OPENAI_CALL_LOGGER.info(json.dumps(payload, ensure_ascii=False))

    # Prometheus counter + duration histogram. Convert ms→seconds for
    # downstream Grafana rate() friendliness.
    try:
        from app.services.metrics_registry import record_openai_call as _record_metric

        _record_metric(model=model, status="ok", duration_seconds=safe_duration_ms / 1000.0)
    except Exception:
        pass

    # Persistent DB row. Local imports to avoid a circular import at
    # module load — `openai_usage.py` is imported very early.
    try:
        from app.api.middleware.request_id import current_request_id
        from app.db.session import SessionLocal
        from app.models.openai_call_log import OpenaiCallLog

        db = SessionLocal()
        try:
            db.add(
                OpenaiCallLog(
                    model=model,
                    prompt_tokens=safe_prompt,
                    completion_tokens=safe_completion,
                    cost_usd=safe_cost,
                    duration_ms=safe_duration_ms,
                    user_id=user_id,
                    request_id=current_request_id(),
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        # Don't let observability shake an OpenAI flow. The stdout JSON
        # line above is the always-on safety net.
        pass


def _current_user_id() -> int | None:
    tracker = _TRACKER.get()
    return tracker.user_id if tracker is not None else None


@dataclass
class OpenAIUsageSnapshot:
    prompt_tokens: int
    completion_tokens: int
    embedding_tokens: int
    total_tokens: int
    api_calls: int
    estimated_cost_usd: float
    budget_usd: float
    budget_exceeded: bool
    budget_enforced: bool

    def to_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "embedding_tokens": self.embedding_tokens,
            "total_tokens": self.total_tokens,
            "api_calls": self.api_calls,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "budget_usd": round(self.budget_usd, 6),
            "budget_exceeded": self.budget_exceeded,
            "budget_enforced": self.budget_enforced,
        }


class OpenAIBudgetExceeded(RuntimeError):
    def __init__(self, snapshot: OpenAIUsageSnapshot) -> None:
        self.snapshot = snapshot
        super().__init__(
            "OpenAI request budget exceeded: "
            f"${snapshot.estimated_cost_usd:.4f} > ${snapshot.budget_usd:.4f}"
        )


class DailyBudgetExceeded(RuntimeError):
    """Raised when a user's cumulative OpenAI cost for today exceeds their cap.

    Surfaced to the UI as DAILY_BUDGET_USER_MESSAGE — don't leak internals.
    """

    def __init__(self, *, user_id: int, daily_spend_usd: float, daily_budget_usd: float) -> None:
        self.user_id = user_id
        self.daily_spend_usd = daily_spend_usd
        self.daily_budget_usd = daily_budget_usd
        super().__init__(
            f"Daily OpenAI budget exceeded for user {user_id}: "
            f"${daily_spend_usd:.4f} >= ${daily_budget_usd:.4f}"
        )


class OpenAIUsageTracker:
    def __init__(
        self,
        *,
        budget_usd: float,
        budget_enforced: bool,
        user_id: int | None = None,
        daily_budget_usd: float | None = None,
        daily_budget_enforced: bool = False,
    ) -> None:
        self.budget_usd = max(0.0, float(budget_usd))
        self.budget_enforced = bool(budget_enforced)
        self.user_id = user_id
        self.daily_budget_usd = (
            max(0.0, float(daily_budget_usd)) if daily_budget_usd is not None else None
        )
        self.daily_budget_enforced = bool(daily_budget_enforced)
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.embedding_tokens = 0
        self.api_calls = 0
        self.estimated_cost_usd = 0.0

    def add_responses_usage(self, *, input_tokens: int, output_tokens: int) -> None:
        safe_input = max(0, int(input_tokens))
        safe_output = max(0, int(output_tokens))
        delta = compute_responses_cost_usd(input_tokens=safe_input, output_tokens=safe_output)
        self.prompt_tokens += safe_input
        self.completion_tokens += safe_output
        self.api_calls += 1
        self.estimated_cost_usd += delta
        self._persist_daily_spend(delta)
        self._enforce_budget()

    def add_embeddings_usage(self, *, input_tokens: int) -> None:
        safe_input = max(0, int(input_tokens))
        delta = compute_embeddings_cost_usd(input_tokens=safe_input)
        self.embedding_tokens += safe_input
        self.api_calls += 1
        self.estimated_cost_usd += delta
        self._persist_daily_spend(delta)
        self._enforce_budget()

    def snapshot(self) -> OpenAIUsageSnapshot:
        total = self.prompt_tokens + self.completion_tokens + self.embedding_tokens
        exceeded = self.estimated_cost_usd > self.budget_usd
        return OpenAIUsageSnapshot(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            embedding_tokens=self.embedding_tokens,
            total_tokens=total,
            api_calls=self.api_calls,
            estimated_cost_usd=self.estimated_cost_usd,
            budget_usd=self.budget_usd,
            budget_exceeded=exceeded,
            budget_enforced=self.budget_enforced,
        )

    def _enforce_budget(self) -> None:
        if not self.budget_enforced:
            return
        if self.estimated_cost_usd > self.budget_usd:
            raise OpenAIBudgetExceeded(self.snapshot())

    def _persist_daily_spend(self, delta_usd: float) -> None:
        if self.user_id is None or self.daily_budget_usd is None or delta_usd <= 0:
            return
        # Import here to avoid pulling DB deps when the tracker is used in tests
        # or non-DB contexts.
        from app.db.session import SessionLocal
        from app.repositories.user_daily_spend import increment_daily_spend

        db = SessionLocal()
        try:
            new_total = increment_daily_spend(db, user_id=self.user_id, amount_usd=delta_usd)
        finally:
            db.close()
        if self.daily_budget_enforced and new_total > self.daily_budget_usd:
            raise DailyBudgetExceeded(
                user_id=self.user_id,
                daily_spend_usd=new_total,
                daily_budget_usd=self.daily_budget_usd,
            )


@contextmanager
def openai_budget_scope(
    *,
    budget_usd: float,
    budget_enforced: bool,
    user_id: int | None = None,
    daily_budget_usd: float | None = None,
    daily_budget_enforced: bool = False,
):
    tracker = OpenAIUsageTracker(
        budget_usd=budget_usd,
        budget_enforced=budget_enforced,
        user_id=user_id,
        daily_budget_usd=daily_budget_usd,
        daily_budget_enforced=daily_budget_enforced,
    )
    token = _TRACKER.set(tracker)
    try:
        yield tracker
    finally:
        _TRACKER.reset(token)


@contextmanager
def system_budget_scope(budget_usd: float, budget_enforced: bool):
    """Budget scope for system-initiated work (segment warmup, etc.).

    Uses user_id=None so no user's daily spend is charged.
    Parallel to openai_budget_scope but without per-user daily tracking.
    """
    tracker = OpenAIUsageTracker(
        budget_usd=budget_usd,
        budget_enforced=budget_enforced,
        user_id=None,
        daily_budget_usd=None,
        daily_budget_enforced=False,
    )
    token = _TRACKER.set(tracker)
    try:
        yield tracker
    finally:
        _TRACKER.reset(token)


def record_responses_usage(
    *,
    input_tokens: int,
    output_tokens: int,
    model: str | None = None,
    duration_ms: int = 0,
) -> None:
    cost = compute_responses_cost_usd(input_tokens=input_tokens, output_tokens=output_tokens)
    log_openai_call(
        model=model or "unknown",
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
        cost_usd=cost,
        user_id=_current_user_id(),
        duration_ms=duration_ms,
    )
    tracker = _TRACKER.get()
    if tracker is None:
        return
    tracker.add_responses_usage(input_tokens=input_tokens, output_tokens=output_tokens)


def record_embeddings_usage(
    *,
    input_tokens: int,
    model: str | None = None,
    duration_ms: int = 0,
) -> None:
    cost = compute_embeddings_cost_usd(input_tokens=input_tokens)
    log_openai_call(
        model=model or "unknown",
        prompt_tokens=input_tokens,
        completion_tokens=0,
        cost_usd=cost,
        user_id=_current_user_id(),
        duration_ms=duration_ms,
    )
    tracker = _TRACKER.get()
    if tracker is None:
        return
    tracker.add_embeddings_usage(input_tokens=input_tokens)
