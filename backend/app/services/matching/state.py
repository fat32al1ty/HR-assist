"""Data shapes carried through the matching pipeline.

Three records, kept tiny on purpose:

- ``ResumeContext`` is everything the matcher needs to know about the
  user's resume + preferences. Built once at the top of the pipeline
  and read-only after that — stages must not mutate it.
- ``Candidate`` is a single vacancy moving through the cascade.
  Mutable because later stages annotate it (``hybrid_score``, ``tier``,
  etc.) — but ``vacancy_id`` / ``payload`` / ``vector_score`` are
  invariant once the recall stage writes them.
- ``MatchingState`` bundles the active candidate list with the
  read-only context and a diagnostics counter. Each stage receives and
  returns one of these.

The point of naming these is that stages get a typed contract instead
of a dict-of-dicts. When Phase 2.4 adds ``role_family``, it is an
optional field here — no stage downstream has to know how it was
produced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ``Vacancy`` is imported lazily inside stages that need it to avoid
# pulling SQLAlchemy into this module just for a type hint.


@dataclass(frozen=True)
class ResumeContext:
    """Everything the pipeline reads about the resume owner.

    Frozen on purpose — stages should never reach back and rewrite the
    resume side of the match. If a stage needs derived state (e.g. a
    normalized token set), it caches that inside ``MatchingState``, not
    here.
    """

    resume_id: int
    user_id: int
    analysis: dict[str, Any] | None
    query_vector: list[float]
    resume_skills: set[str]
    resume_roles: set[str]
    resume_skill_phrases: list[str]
    resume_hard_skills: list[str]
    resume_phrase_aliases: set[str]
    resume_total_years: float | None
    leadership_preferred: bool
    preferences: dict[str, Any]
    preferred_titles: list[str]
    excluded_vacancy_ids: set[int]
    rejected_skill_norms: set[str]


@dataclass
class Candidate:
    """One vacancy under consideration.

    ``vector_score`` is set once by the recall stage and never changed.
    Downstream stages write ``lexical_score``, ``hybrid_score``, and
    ``tier`` and may annotate ``drop_reason`` when they filter the
    candidate out; pipeline runner discards candidates with a
    non-empty ``drop_reason`` at stage boundaries.
    """

    vacancy_id: int
    vacancy: Any  # ORM ``Vacancy`` — typed Any to avoid SQLA import here
    payload: dict[str, Any]
    vector_score: float
    lexical_score: float = 0.0
    hybrid_score: float = 0.0
    tier: str = ""
    drop_reason: str = ""
    augmented_profile: dict[str, Any] = field(default_factory=dict)
    # Stage-specific scratch space — e.g. leadership_hint flag, title
    # boost magnitude. Keeps Candidate flat while letting stages pass
    # small hints downstream.
    annotations: dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchingDiagnostics:
    """Per-stage drop counts and telemetry.

    Exposed on the final state so the top-level wrapper can publish
    them through the existing ``metrics`` dict argument without any
    stage needing to know the public contract. Extra counters are just
    extra keys in ``custom`` — no schema migration.
    """

    recall_count: int = 0
    drop_archived: int = 0
    drop_listing_page: int = 0
    drop_non_vacancy_page: int = 0
    drop_host_not_allowed: int = 0
    drop_unlikely_stack: int = 0
    drop_business_role: int = 0
    drop_hard_non_it: int = 0
    drop_domain_mismatch: int = 0
    drop_work_format: int = 0
    drop_geo: int = 0
    drop_no_skill_overlap: int = 0
    drop_dedupe: int = 0
    drop_mmr_dedupe: int = 0
    seniority_penalty_applied: int = 0
    title_boost_applied: int = 0
    custom: dict[str, int] = field(default_factory=dict)

    def export_to(self, metrics: dict[str, int] | None) -> None:
        """Copy the historical counter names into a caller-provided dict.

        Preserves the public metric keys the existing endpoint tests
        assert on (``hard_filter_drop_*``, ``seniority_penalty_applied``,
        ``archived_at_match_time``, ``title_boost_applied``). Anything
        new goes into ``custom`` and is exported under the same key.
        """
        if metrics is None:
            return
        metrics["hard_filter_drop_work_format"] = self.drop_work_format
        metrics["hard_filter_drop_geo"] = self.drop_geo
        metrics["hard_filter_drop_no_skill_overlap"] = self.drop_no_skill_overlap
        metrics["hard_filter_drop_domain_mismatch"] = self.drop_domain_mismatch
        metrics["seniority_penalty_applied"] = self.seniority_penalty_applied
        metrics["archived_at_match_time"] = self.drop_archived
        metrics["title_boost_applied"] = self.title_boost_applied
        for key, value in self.custom.items():
            metrics[key] = value


@dataclass
class MatchingState:
    """Container passed through every stage.

    Stages may:
      * mutate ``candidates`` — add, remove, reorder, annotate;
      * mutate ``diagnostics`` — bump counters;
      * write to ``scratch`` — e.g. a shared embedding cache.

    They must not reassign ``resume_context``.
    """

    resume_context: ResumeContext
    candidates: list[Candidate]
    diagnostics: MatchingDiagnostics = field(default_factory=MatchingDiagnostics)
    scratch: dict[str, Any] = field(default_factory=dict)

    def drop(self, index: int, reason: str) -> None:
        """Mark a candidate as dropped and bump the matching counter."""
        self.candidates[index].drop_reason = reason

    def surviving(self) -> list[Candidate]:
        """Return the candidates a downstream stage should still consider."""
        return [c for c in self.candidates if not c.drop_reason]
