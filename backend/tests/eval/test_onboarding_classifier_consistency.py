"""Phase 5.0.5 — Onboarding question classifier consistency tests.

Tests the YAML rule evaluator (feature_onboarding_llm_classifier_enabled=False)
against all 20 bootstrap cases without LLM calls.

Invariants verified:
  1. Ambiguous cases (total_experience_years 4-6, non-explicit seniority)
     must trigger seniority_ambiguous in the returned question set.
  2. Cases missing salary_expectation must trigger salary_missing.
  3. The returned set must never exceed 5 questions (hard cap from spec).
  4. The rule evaluator is deterministic — two calls for the same profile
     return the same question IDs.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.resume_clarification import ResumeClarification
from app.models.resume_profile import ResumeProfile
from app.models.user import User
from app.services.onboarding_questions import _build_context, _load_questions, _select_via_rules
from app.schemas.onboarding import OnboardingQuestionOut

BOOTSTRAP_DIR = Path(__file__).parent.parent / "fixtures" / "audit_bootstrap"


def _load_all_cases() -> list[dict]:
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(BOOTSTRAP_DIR.glob("case_*.json"))
    ]


def _make_user(db) -> User:
    suffix = uuid.uuid4().hex[:12]
    user = User(
        email=f"onboard-eval-{suffix}@example.com",
        hashed_password=hash_password("EvalPass123!"),
        full_name="Onboard Eval User",
        is_active=True,
        email_verified=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_resume_with_profile(db, user_id: int, profile_data: dict) -> Resume:
    resume = Resume(
        user_id=user_id,
        original_filename="onboard_eval.pdf",
        content_type="application/pdf",
        status="completed",
        analysis={},
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    profile_row = ResumeProfile(
        resume_id=resume.id,
        user_id=user_id,
        profile=profile_data,
        canonical_text=f"Seniority: {profile_data.get('seniority', '')}",
        qdrant_collection="eval_collection",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(profile_row)
    db.commit()
    db.refresh(profile_row)
    return resume


def _cleanup(db, user_id: int, resume_id: int) -> None:
    db.execute(delete(ResumeClarification).where(ResumeClarification.resume_id == resume_id))
    db.execute(delete(ResumeProfile).where(ResumeProfile.resume_id == resume_id))
    db.execute(delete(Resume).where(Resume.id == resume_id))
    db.execute(delete(User).where(User.id == user_id))
    db.commit()


def _select_questions_from_profile(profile_data: dict) -> list[OnboardingQuestionOut]:
    """Call rule selector directly without DB — pure unit path for the context builder."""
    questions = _load_questions()
    ctx = _build_context(profile_data)
    return _select_via_rules(questions, ctx, answered_ids=set())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_bootstrap_cases_return_at_most_5_questions() -> None:
    """Hard cap: no profile may trigger more than 5 onboarding questions."""
    cases = _load_all_cases()
    for case in cases:
        questions = _select_questions_from_profile(case["resume_profile"])
        assert len(questions) <= 5, (
            f"case {case['case_id']}: returned {len(questions)} questions but cap is 5"
        )


def test_ambiguous_seniority_cases_trigger_seniority_ambiguous_question() -> None:
    """Cases with years_in_role 4-6 and non-explicit seniority must include seniority_ambiguous.

    Ambiguous cases in the bootstrap: case_14, case_15, case_16
    (total_experience_years 4-6, seniority 'middle', no senior keyword).
    """
    cases = _load_all_cases()
    ambiguous_cases = [
        c for c in cases
        if c["expected_audit"].get("onboarding_should_trigger") and
        "seniority_ambiguous" in c["expected_audit"]["onboarding_should_trigger"]
    ]

    assert len(ambiguous_cases) >= 3, (
        f"Expected at least 3 ambiguous cases in bootstrap, found {len(ambiguous_cases)}"
    )

    for case in ambiguous_cases:
        questions = _select_questions_from_profile(case["resume_profile"])
        question_ids = [q.id for q in questions]
        assert "seniority_ambiguous" in question_ids, (
            f"case {case['case_id']}: expected seniority_ambiguous to be triggered but got {question_ids}"
        )


def test_salary_missing_cases_trigger_salary_missing_question() -> None:
    """Cases with no salary_expectation must include salary_missing question.

    Salary-missing cases in the bootstrap: case_18, case_19.
    """
    cases = _load_all_cases()
    salary_missing_cases = [
        c for c in cases
        if c["expected_audit"].get("onboarding_should_trigger") and
        "salary_missing" in c["expected_audit"]["onboarding_should_trigger"]
    ]

    assert len(salary_missing_cases) >= 2, (
        f"Expected at least 2 salary-missing cases in bootstrap, found {len(salary_missing_cases)}"
    )

    for case in salary_missing_cases:
        questions = _select_questions_from_profile(case["resume_profile"])
        question_ids = [q.id for q in questions]
        assert "salary_missing" in question_ids, (
            f"case {case['case_id']}: expected salary_missing to be triggered but got {question_ids}"
        )


def test_profiles_with_salary_do_not_trigger_salary_missing() -> None:
    """Cases that have salary_expectation must NOT include salary_missing question."""
    cases = _load_all_cases()
    salary_present_cases = [
        c for c in cases
        if c["resume_profile"].get("salary_expectation") is not None
    ]

    assert len(salary_present_cases) > 0, "No cases with salary present found in bootstrap"

    for case in salary_present_cases:
        questions = _select_questions_from_profile(case["resume_profile"])
        question_ids = [q.id for q in questions]
        assert "salary_missing" not in question_ids, (
            f"case {case['case_id']}: salary_expectation is set but salary_missing was triggered"
        )


def test_non_ambiguous_senior_profiles_do_not_trigger_seniority_ambiguous() -> None:
    """Senior profiles with explicit seniority should NOT trigger seniority_ambiguous.

    Senior happy-path cases (01-05) have explicit senior keyword in seniority field.
    """
    cases = _load_all_cases()
    explicit_senior_cases = [
        c for c in cases
        if c["resume_profile"].get("seniority") == "senior" and
        # Verify years >= 5 so the years_in_role condition would fire, but
        # seniority_explicit=True should suppress it
        (c["resume_profile"].get("total_experience_years") or 0) >= 5.0
    ]

    assert len(explicit_senior_cases) > 0, (
        "No explicit-senior cases found in bootstrap"
    )

    for case in explicit_senior_cases:
        questions = _select_questions_from_profile(case["resume_profile"])
        question_ids = [q.id for q in questions]
        assert "seniority_ambiguous" not in question_ids, (
            f"case {case['case_id']}: seniority='senior' but seniority_ambiguous was triggered"
        )


def test_rule_selector_is_deterministic() -> None:
    """Calling the rule selector twice with the same profile yields identical results."""
    cases = _load_all_cases()
    # Test determinism on all cases
    for case in cases:
        first = [q.id for q in _select_questions_from_profile(case["resume_profile"])]
        second = [q.id for q in _select_questions_from_profile(case["resume_profile"])]
        assert first == second, (
            f"case {case['case_id']}: rule selector is non-deterministic "
            f"(got {first} then {second})"
        )


def test_question_objects_have_required_fields() -> None:
    """Every triggered question must have id, text, answer_type set."""
    cases = _load_all_cases()
    for case in cases:
        questions = _select_questions_from_profile(case["resume_profile"])
        for q in questions:
            assert q.id, f"case {case['case_id']}: question has empty id"
            assert q.text, f"case {case['case_id']}: question {q.id!r} has empty text"
            assert q.answer_type, (
                f"case {case['case_id']}: question {q.id!r} has empty answer_type"
            )


def test_answered_questions_are_excluded_from_selection() -> None:
    """If seniority_ambiguous is in answered_ids it must not appear in the returned set."""
    cases = _load_all_cases()
    ambiguous_cases = [
        c for c in cases
        if c["expected_audit"].get("onboarding_should_trigger") and
        "seniority_ambiguous" in c["expected_audit"]["onboarding_should_trigger"]
    ]

    assert len(ambiguous_cases) >= 1

    for case in ambiguous_cases:
        questions = _load_questions()
        ctx = _build_context(case["resume_profile"])
        # Pre-answered seniority_ambiguous
        answered = {"seniority_ambiguous"}
        result = _select_via_rules(questions, ctx, answered_ids=answered)
        question_ids = [q.id for q in result]
        assert "seniority_ambiguous" not in question_ids, (
            f"case {case['case_id']}: seniority_ambiguous still shown after being answered"
        )
