"""Phase 2.3 matching package.

Splits the historical ``matching_service.match_vacancies_for_resume``
monolith into a composable cascade of named stages:

    recall → filter → domain_gate → lexical → hybrid → tier → diversify → augment

Each stage is a small, testable unit that consumes a ``MatchingState``
and either prunes, scores, or annotates its candidates. The top-level
runner (``run_pipeline``) folds the stages in order and returns the
final state. This separation is what lets Phase 2.4 (ESCO / role
classifier) and Phase 2.5 (cross-encoder rerank) drop in as single
stage files without touching the rest of the code.

The package deliberately avoids importing from ``matching_service`` at
module top-level to keep imports lean; stages that need the existing
helpers (tokenization, alias expansion, domain detection) import them
inside ``run`` so we do not grow a circular import when the wrapper
itself lives in ``matching_service``.
"""

from .pipeline import run_pipeline
from .stages.base import BaseStage
from .state import Candidate, MatchingDiagnostics, MatchingState, ResumeContext

__all__ = [
    "BaseStage",
    "Candidate",
    "MatchingDiagnostics",
    "MatchingState",
    "ResumeContext",
    "run_pipeline",
]
