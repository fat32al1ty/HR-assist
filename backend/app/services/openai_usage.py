from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from app.core.config import settings

_TRACKER: ContextVar[OpenAIUsageTracker | None] = ContextVar("openai_usage_tracker", default=None)


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


class OpenAIUsageTracker:
    def __init__(self, *, budget_usd: float, budget_enforced: bool) -> None:
        self.budget_usd = max(0.0, float(budget_usd))
        self.budget_enforced = bool(budget_enforced)
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.embedding_tokens = 0
        self.api_calls = 0
        self.estimated_cost_usd = 0.0

    def add_responses_usage(self, *, input_tokens: int, output_tokens: int) -> None:
        safe_input = max(0, int(input_tokens))
        safe_output = max(0, int(output_tokens))
        self.prompt_tokens += safe_input
        self.completion_tokens += safe_output
        self.api_calls += 1
        self.estimated_cost_usd += (
            (safe_input / 1_000_000.0) * settings.openai_responses_input_usd_per_1m
            + (safe_output / 1_000_000.0) * settings.openai_responses_output_usd_per_1m
        ) * settings.openai_cost_safety_multiplier
        self._enforce_budget()

    def add_embeddings_usage(self, *, input_tokens: int) -> None:
        safe_input = max(0, int(input_tokens))
        self.embedding_tokens += safe_input
        self.api_calls += 1
        self.estimated_cost_usd += (
            (safe_input / 1_000_000.0) * settings.openai_embeddings_input_usd_per_1m
        ) * settings.openai_cost_safety_multiplier
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


@contextmanager
def openai_budget_scope(*, budget_usd: float, budget_enforced: bool):
    tracker = OpenAIUsageTracker(budget_usd=budget_usd, budget_enforced=budget_enforced)
    token = _TRACKER.set(tracker)
    try:
        yield tracker
    finally:
        _TRACKER.reset(token)


def record_responses_usage(*, input_tokens: int, output_tokens: int) -> None:
    tracker = _TRACKER.get()
    if tracker is None:
        return
    tracker.add_responses_usage(input_tokens=input_tokens, output_tokens=output_tokens)


def record_embeddings_usage(*, input_tokens: int) -> None:
    tracker = _TRACKER.get()
    if tracker is None:
        return
    tracker.add_embeddings_usage(input_tokens=input_tokens)
