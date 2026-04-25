"""Unit tests for track_classifier.classify().

No DB, no fixtures. Each test corresponds to an observable invariant about
the classification decision — not the implementation details.
"""

from __future__ import annotations

import pytest

from app.services.track_classifier import TrackDecision, classify


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _call(**kwargs) -> TrackDecision:
    """Thin wrapper that provides safe defaults so each test only overrides
    the parameters it cares about."""
    defaults = dict(
        vector_score=0.80,
        resume_seniority="middle",
        vacancy_seniority="middle",
        resume_skills={"Python", "FastAPI"},
        vacancy_must_have_skills=["Python", "FastAPI"],
    )
    defaults.update(kwargs)
    return classify(**defaults)


# ---------------------------------------------------------------------------
# match band
# ---------------------------------------------------------------------------


def test_same_seniority_full_overlap_high_vector_is_match():
    """Same level, 100 % skill overlap, high vector → match. Reason says «точка»."""
    decision = _call(
        vector_score=0.90,
        resume_seniority="middle",
        vacancy_seniority="middle",
        resume_skills={"Python", "FastAPI"},
        vacancy_must_have_skills=["Python", "FastAPI"],
    )
    assert decision.track == "match"
    assert "точка" in decision.reason


def test_same_seniority_partial_overlap_high_vector_is_match():
    """Partial overlap (50 %) is still match at same level — matcher already filtered."""
    decision = _call(
        vector_score=0.85,
        resume_seniority="senior",
        vacancy_seniority="senior",
        resume_skills={"Python"},
        vacancy_must_have_skills=["Python", "Kafka"],
    )
    assert decision.track == "match"


def test_same_seniority_low_overlap_low_vector_is_match():
    """Low vector + low overlap at same level → still match (no 2+ level gap, no diff==1 rule)."""
    decision = _call(
        vector_score=0.50,
        resume_seniority="junior",
        vacancy_seniority="junior",
        resume_skills={"SQL"},
        vacancy_must_have_skills=["Python", "Kafka", "Docker"],
    )
    assert decision.track == "match"


def test_vacancy_below_resume_is_match():
    """Vacancy is below resume seniority → negative diff → match."""
    decision = _call(
        vector_score=0.80,
        resume_seniority="senior",
        vacancy_seniority="junior",
        resume_skills={"Python"},
        vacancy_must_have_skills=["Python"],
    )
    assert decision.track == "match"
    assert decision.seniority_diff < 0


# ---------------------------------------------------------------------------
# grow band
# ---------------------------------------------------------------------------


def test_one_level_above_good_overlap_high_vector_is_grow():
    """1 level above, overlap >= 0.5, vector >= 0.65 → grow. Reason mentions «вырост»."""
    decision = _call(
        vector_score=0.70,
        resume_seniority="junior",
        vacancy_seniority="middle",
        resume_skills={"Python", "FastAPI", "PostgreSQL"},
        vacancy_must_have_skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
    )
    # overlap = 3/4 = 0.75 — qualifies for grow, NOT stretch (diff==1 and overlap >= 0.5)
    assert decision.track == "grow"
    assert "вырост" in decision.reason


def test_grow_seniority_diff_is_one():
    """grow decisions always have seniority_diff == 1."""
    decision = _call(
        vector_score=0.70,
        resume_seniority="middle",
        vacancy_seniority="senior",
        resume_skills={"Python", "FastAPI"},
        vacancy_must_have_skills=["Python", "FastAPI"],
    )
    assert decision.track == "grow"
    assert decision.seniority_diff == 1


# ---------------------------------------------------------------------------
# stretch band
# ---------------------------------------------------------------------------


def test_one_level_above_low_overlap_is_stretch():
    """diff == 1, overlap < 0.5 → stretch even though only 1 level above."""
    decision = _call(
        vector_score=0.70,
        resume_seniority="junior",
        vacancy_seniority="middle",
        resume_skills={"Python"},
        vacancy_must_have_skills=["Python", "Kafka", "K8s"],
    )
    # overlap = 1/3 ≈ 0.33 < 0.5 → stretch
    assert decision.track == "stretch"


def test_two_levels_above_reasonable_overlap_is_stretch():
    """2 levels above → stretch regardless of overlap."""
    decision = _call(
        vector_score=0.65,
        resume_seniority="junior",
        vacancy_seniority="senior",
        resume_skills={"Python", "FastAPI", "PostgreSQL"},
        vacancy_must_have_skills=["Python", "FastAPI", "PostgreSQL", "K8s", "Terraform"],
    )
    # overlap = 3/5 = 0.6, diff = 2 → stretch
    assert decision.track == "stretch"
    assert decision.seniority_diff == 2


def test_three_levels_above_is_stretch():
    """principal vs middle = diff 3 → stretch."""
    decision = _call(
        vector_score=0.65,
        resume_seniority="middle",
        vacancy_seniority="principal",
        resume_skills={"Python"},
        vacancy_must_have_skills=["Python"],
    )
    assert decision.track == "stretch"
    assert decision.seniority_diff == 3


# ---------------------------------------------------------------------------
# None / unknown seniority handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "resume_sen, vacancy_sen",
    [
        (None, "middle"),
        ("middle", None),
        (None, None),
        ("unknown_level", "middle"),
        ("middle", "gobbledygook"),
    ],
)
def test_unknown_seniority_treated_as_zero_diff(resume_sen, vacancy_sen):
    """When either seniority is None or unrecognized, diff = 0 → track is match."""
    decision = _call(
        vector_score=0.80,
        resume_seniority=resume_sen,
        vacancy_seniority=vacancy_sen,
        resume_skills={"Python"},
        vacancy_must_have_skills=["Python"],
    )
    assert decision.track == "match"
    assert decision.seniority_diff == 0


# ---------------------------------------------------------------------------
# Empty vacancy_must_have_skills
# ---------------------------------------------------------------------------


def test_empty_vacancy_must_have_skills_overlap_is_zero_still_match():
    """No required skills → overlap 0.0; same level → match (no stretch trigger)."""
    decision = _call(
        vector_score=0.80,
        resume_seniority="middle",
        vacancy_seniority="middle",
        resume_skills={"Python", "FastAPI"},
        vacancy_must_have_skills=[],
    )
    assert decision.track == "match"
    assert decision.skills_overlap == 0.0


# ---------------------------------------------------------------------------
# Case-insensitive and whitespace-tolerant skill matching
# ---------------------------------------------------------------------------


def test_skill_matching_is_case_insensitive():
    """Resume has 'Python' (title case), vacancy has 'python' (lower) and 'Kafka' (title).
    Overlap = 1 matched / 2 required = 0.5."""
    decision = classify(
        vector_score=0.80,
        resume_seniority="middle",
        vacancy_seniority="middle",
        resume_skills={"Python"},
        vacancy_must_have_skills=["python", "Kafka"],
    )
    assert decision.skills_overlap == pytest.approx(0.5, abs=1e-9)
    assert decision.track == "match"


def test_skill_matching_strips_whitespace():
    """Resume has ' Python ' with surrounding spaces — should still match 'python'."""
    decision = classify(
        vector_score=0.80,
        resume_seniority="middle",
        vacancy_seniority="middle",
        resume_skills={" Python "},
        vacancy_must_have_skills=["python"],
    )
    assert decision.skills_overlap == pytest.approx(1.0, abs=1e-9)
    assert decision.track == "match"
