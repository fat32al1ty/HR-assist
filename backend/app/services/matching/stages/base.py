"""Stage protocol for the matching pipeline.

A stage is any callable that takes a ``MatchingState`` and returns one
(usually the same instance, mutated). Concrete stages subclass
``BaseStage`` to pick up ``name`` and a no-op ``__init__``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..state import MatchingState


class BaseStage(ABC):
    """Base class for pipeline stages.

    Subclasses set ``name`` as a class attribute (used for logging and
    diagnostics) and implement ``run``. Stage instances may keep
    constructor-time config — e.g. ``VectorRecallStage(top_k=500)``.
    """

    name: str = "unnamed"

    @abstractmethod
    def run(self, state: MatchingState) -> MatchingState:  # pragma: no cover - abstract
        """Execute the stage and return the (possibly-mutated) state."""
        raise NotImplementedError
