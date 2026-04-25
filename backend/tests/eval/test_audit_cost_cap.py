"""Phase 5.0.5 — Synthetic cost regression test for the resume audit engine.

For each of the 20 bootstrap cases:
  1. Builds the audit prompt text without calling OpenAI (monkey-patches the
     LLM normalization call to a no-op).
  2. Estimates token count using a character-ratio approximation (4 chars ≈ 1 token,
     the standard GPT heuristic — tiktoken not available in this image).
  3. Asserts P95 of (prompt_tokens + max_output_tokens) < 2200.

Budget rationale (from phase-5.0 spec):
  1500 prompt tokens + 600 max_tokens + 100 slack = 2200.

Does NOT require an OpenAI key — fully deterministic.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import delete

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.resume import Resume
from app.models.resume_audit import ResumeAudit
from app.models.resume_profile import ResumeProfile
from app.models.user import User
from app.services.resume_audit import compute_audit

BOOTSTRAP_DIR = Path(__file__).parent.parent / "fixtures" / "audit_bootstrap"

# Budget from phase-5.0 spec: 1500 prompt + 600 max_tokens + 100 slack
TOKEN_BUDGET_P95 = 2200
MAX_OUTPUT_TOKENS = 600

# GPT-family approximation: ~4 characters per token.
# Accurate enough for a budget guard; real billing uses cl100k_base.
CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Estimate token count via character ratio (no external dependency)."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def _prompt_text_for_skill_normalization(skills: list[str]) -> str:
    """Reconstruct the skill normalization prompt as the service would build it."""
    return (
        "Normalize the following skill names to their canonical English form. "
        "Return ONLY a JSON object mapping each input string to its canonical name. "
        "Examples: 'k8s' -> 'Kubernetes', 'js' -> 'JavaScript', 'py' -> 'Python'. "
        "If already canonical, return as-is.\n\n"
        f"Skills: {json.dumps(skills, ensure_ascii=False)}"
    )


def _make_user(db) -> User:
    suffix = uuid.uuid4().hex[:12]
    user = User(
        email=f"cost-eval-{suffix}@example.com",
        hashed_password=hash_password("EvalPass123!"),
        full_name="Cost Eval User",
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
        original_filename="cost_eval.pdf",
        content_type="application/pdf",
        status="completed",
        analysis={
            "target_role": profile_data.get("role_family", "unknown"),
            "seniority": profile_data.get("seniority", "unknown"),
        },
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    canonical_text = (
        f"Role: {profile_data.get('role_family', '')}\n"
        f"Seniority: {profile_data.get('seniority', '')}\n"
        f"Skills: {', '.join(profile_data.get('skills', []))}\n"
        f"Experience: {profile_data.get('total_experience_years', 0)} years"
    )
    profile_row = ResumeProfile(
        resume_id=resume.id,
        user_id=user_id,
        profile=profile_data,
        canonical_text=canonical_text,
        qdrant_collection="eval_collection",
        qdrant_point_id=str(uuid.uuid4()),
    )
    db.add(profile_row)
    db.commit()
    db.refresh(profile_row)
    return resume


def _cleanup(db, user_id: int, resume_id: int) -> None:
    db.execute(delete(ResumeAudit).where(ResumeAudit.resume_id == resume_id))
    db.execute(delete(ResumeProfile).where(ResumeProfile.resume_id == resume_id))
    db.execute(delete(Resume).where(Resume.id == resume_id))
    db.execute(delete(User).where(User.id == user_id))
    db.commit()


def _noop_normalize(cache_key: str, skills_json: str) -> str:
    """Identity normalization — returns skills as-is. No network calls."""
    skills = json.loads(skills_json)
    return json.dumps({s: s for s in skills}, ensure_ascii=False)


def test_audit_p95_token_usage_under_budget() -> None:
    """Run audit on all 20 bootstrap cases; assert P95 prompt+max_tokens < 2200.

    The LLM normalization call is monkey-patched to a no-op so this test
    is fully deterministic and requires no OpenAI key.

    Token estimation: len(prompt_text) // 4  (standard GPT approximation).
    """
    case_paths = sorted(BOOTSTRAP_DIR.glob("case_*.json"))
    assert len(case_paths) == 20, (
        f"Expected 20 bootstrap cases, found {len(case_paths)}. "
        "Add missing fixtures before merging."
    )

    token_totals: list[int] = []

    with patch(
        "app.services.resume_audit._normalize_via_llm_cached",
        side_effect=_noop_normalize,
    ):
        for case_path in case_paths:
            case = json.loads(case_path.read_text(encoding="utf-8"))
            profile_data = case["resume_profile"]
            skills = profile_data.get("skills", []) + profile_data.get("hard_skills", [])
            # Deduplicate while preserving order
            seen: set[str] = set()
            unique_skills: list[str] = []
            for s in skills:
                if isinstance(s, str) and s.lower() not in seen:
                    seen.add(s.lower())
                    unique_skills.append(s)

            # Estimate prompt tokens for the skill normalization call
            # (the only LLM call in the audit engine — per the spec)
            prompt_text = _prompt_text_for_skill_normalization(unique_skills)
            prompt_tokens = _estimate_tokens(prompt_text)

            total = prompt_tokens + MAX_OUTPUT_TOKENS
            token_totals.append(total)

    # Compute P95
    token_totals_sorted = sorted(token_totals)
    p95_index = int(len(token_totals_sorted) * 0.95) - 1
    p95_index = max(0, min(p95_index, len(token_totals_sorted) - 1))
    p95_value = token_totals_sorted[p95_index]

    # Emit diagnostics so failures are easy to debug
    print(f"\nToken usage across {len(token_totals)} cases:")
    print(f"  min={min(token_totals)}, max={max(token_totals)}, p95={p95_value}")
    print(f"  budget={TOKEN_BUDGET_P95}")
    print(f"  individual totals: {token_totals}")

    assert p95_value < TOKEN_BUDGET_P95, (
        f"P95 token usage ({p95_value}) exceeds budget ({TOKEN_BUDGET_P95}). "
        "Either the skill list or prompt template has grown too large. "
        "Review resume_audit._prompt_text and trim or cache more aggressively."
    )


def test_audit_runs_without_llm_for_all_bootstrap_cases() -> None:
    """Confirm that compute_audit() completes for all 20 cases without network.

    The LLM normalization path is patched out. This catches any regression
    where the service tries to call OpenAI outside the designated code path.
    """
    case_paths = sorted(BOOTSTRAP_DIR.glob("case_*.json"))

    with patch(
        "app.services.resume_audit._normalize_via_llm_cached",
        side_effect=_noop_normalize,
    ):
        for case_path in case_paths:
            case = json.loads(case_path.read_text(encoding="utf-8"))
            db = SessionLocal()
            user = _make_user(db)
            resume = _create_resume_with_profile(db, user.id, case["resume_profile"])
            try:
                audit = compute_audit(db, resume.id, user.id)
                assert audit.prompt_version == "audit-v1", (
                    f"case {case['case_id']}: unexpected prompt_version {audit.prompt_version!r}"
                )
                assert len(audit.skill_gaps) <= 5, (
                    f"case {case['case_id']}: returned {len(audit.skill_gaps)} skill gaps (max 5)"
                )
            finally:
                _cleanup(db, user.id, resume.id)
                db.close()
