"""Pipeline runner.

Composes a list of stages and folds them over the state. Stages that
filter candidates mark them with ``drop_reason``; the runner prunes
those between stages so every stage after the first sees only the
surviving candidates.
"""

from __future__ import annotations

from collections.abc import Sequence

from .stages.base import BaseStage
from .state import MatchingState


def run_pipeline(state: MatchingState, stages: Sequence[BaseStage]) -> MatchingState:
    """Run ``stages`` in order, pruning dropped candidates between each.

    We prune *after* every stage instead of in each stage because
    filters are easier to write when they just flag ``drop_reason`` —
    no list-index-while-you-mutate bugs.
    """
    for stage in stages:
        state = stage.run(state)
        state.candidates = [c for c in state.candidates if not c.drop_reason]
    return state
