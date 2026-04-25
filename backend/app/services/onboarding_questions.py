"""Phase 5.0.2 — Light hybrid onboarding question selector.

Loads onboarding_templates.yaml once and evaluates trigger conditions
deterministically against a resume profile context dict. No LLM by default
(feature_onboarding_llm_classifier_enabled = False).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.resume_clarification import ResumeClarification
from app.models.resume_profile import ResumeProfile
from app.schemas.onboarding import OnboardingQuestionOut

logger = logging.getLogger(__name__)

YAML_VERSION = "v1"
_YAML_PATH = Path(__file__).resolve().parent.parent / "data" / "onboarding_templates.yaml"


@lru_cache(maxsize=1)
def _load_questions() -> list[dict]:
    try:
        with _YAML_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or []
    except FileNotFoundError:
        logger.warning("onboarding_templates.yaml not found at %s", _YAML_PATH)
        return []
    if not isinstance(data, list):
        return []
    return [q for q in data if isinstance(q, dict) and q.get("id")]


def _build_context(profile: dict) -> dict:
    """Build a flat boolean/numeric context dict from resume profile for condition evaluation."""
    skills = profile.get("skills") or profile.get("hard_skills") or []
    if not isinstance(skills, list):
        skills = []
    skills_lower = {s.lower() for s in skills if isinstance(s, str)}

    experiences = profile.get("experience") or []
    if not isinstance(experiences, list):
        experiences = []

    seniority = (profile.get("seniority") or "").lower()
    total_years = _safe_float(profile.get("total_experience_years"))
    location = profile.get("location") or profile.get("city") or profile.get("home_city")
    role_family = profile.get("role_family") or ""

    # seniority_explicit means the user unambiguously declared a high seniority level.
    # "middle" and "junior" with 4-6 years experience are ambiguous, hence the question.
    seniority_explicit_keywords = {"senior", "lead", "principal", "staff"}
    seniority_explicit = seniority in seniority_explicit_keywords

    return {
        "years_in_role_between_4_and_6": total_years is not None and 4.0 <= total_years <= 6.0,
        "years_in_role_gt_5": total_years is not None and total_years > 5.0,
        "seniority_explicit": seniority_explicit,
        "salary_expectation_missing": not profile.get("salary_expectation"),
        "salary_expectation_present": bool(profile.get("salary_expectation")),
        "location_missing": not location,
        "relocation_missing": not profile.get("relocation"),
        "relocation_ready": bool(profile.get("relocation")),
        "work_format_missing": not profile.get("work_format")
        and not profile.get("preferred_work_format"),
        "english_level_missing": not profile.get("english_level") and "english" not in skills_lower,
        "employment_type_missing": not profile.get("employment_type"),
        "domains_missing": not (profile.get("domains") or []),
        "domains_count_less_than_2": len(profile.get("domains") or []) < 2,
        "github_missing": not profile.get("github") and not profile.get("github_url"),
        "agile_missing": not any(k in skills_lower for k in {"scrum", "kanban", "agile"}),
        "skills_count_less_than_5": len(skills) < 5,
        "experience_count_less_than_3": len(experiences) < 3,
        "stack_has_python": any("python" in s for s in skills_lower),
        "stack_has_go": any(s in {"go", "golang"} for s in skills_lower),
        "stack_has_frontend": any(
            s in {"react", "vue", "angular", "typescript", "javascript", "html", "css"}
            for s in skills_lower
        ),
        "role_is_technical": bool(profile.get("role_is_technical")),
        "role_family_is_software_engineering": role_family == "software_engineering",
        "role_family_is_data_ml": role_family == "data_ml",
        "role_family_is_infrastructure_devops": role_family == "infrastructure_devops",
        "role_family_is_customer_support": role_family == "customer_support",
        "seniority_is_junior": seniority in {"junior"},
        "seniority_is_middle": seniority in {"middle"},
        "seniority_is_senior": seniority in {"senior"},
        "seniority_is_lead": seniority in {"lead", "principal", "staff"},
        "always": True,
    }


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _eval_condition(condition: str, ctx: dict) -> bool:
    """Evaluate AND/OR/NOT/parens-free condition against ctx dict.

    AND binds tighter than OR (standard precedence). NOT is unary prefix.
    On any parse error returns False and logs at debug — silent failures
    used to mask seven YAML rules; debug log surfaces YAML authoring bugs.
    """
    try:
        tokens = condition.split()
        if not tokens:
            return False

        or_groups: list[bool] = []
        and_acc: bool | None = None
        negate = False

        def push_and(value: bool) -> None:
            nonlocal and_acc
            and_acc = value if and_acc is None else (and_acc and value)

        for token in tokens:
            upper = token.upper()
            if upper == "AND":
                continue
            if upper == "OR":
                if and_acc is not None:
                    or_groups.append(and_acc)
                and_acc = None
                continue
            if upper == "NOT":
                negate = not negate
                continue
            val = bool(ctx.get(token, False))
            if negate:
                val = not val
                negate = False
            push_and(val)

        if and_acc is not None:
            or_groups.append(and_acc)
        return any(or_groups)
    except Exception as exc:
        logger.debug("onboarding condition parse failed for %r: %s", condition, exc)
        return False


def _question_triggered(question: dict, ctx: dict) -> bool:
    triggers = question.get("triggers") or []
    if not triggers:
        return False
    for trigger in triggers:
        if not isinstance(trigger, dict):
            continue
        condition = trigger.get("condition", "")
        if condition and _eval_condition(condition, ctx):
            return True
    return False


def select_questions_for_resume(db: Session, resume_id: int) -> list[OnboardingQuestionOut]:
    from app.core.config import settings

    profile_row = db.scalar(select(ResumeProfile).where(ResumeProfile.resume_id == resume_id))
    if profile_row is None:
        return []

    profile = profile_row.profile or {}

    # answered question ids
    answered_ids: set[str] = set()
    for row in db.scalars(
        select(ResumeClarification).where(ResumeClarification.resume_id == resume_id)
    ).all():
        answered_ids.add(row.question_id)

    questions = _load_questions()
    ctx = _build_context(profile)

    if settings.feature_onboarding_llm_classifier_enabled:
        selected = _select_via_llm(profile_row.canonical_text, questions, ctx, profile_row)
    else:
        selected = _select_via_rules(questions, ctx, answered_ids)

    return selected[:5]


def _select_via_rules(
    questions: list[dict],
    ctx: dict,
    answered_ids: set[str],
) -> list[OnboardingQuestionOut]:
    result: list[OnboardingQuestionOut] = []
    for q in questions:
        qid = q["id"]
        if qid in answered_ids:
            continue
        if _question_triggered(q, ctx):
            result.append(
                OnboardingQuestionOut(
                    id=qid,
                    text=q.get("text", ""),
                    answer_type=q.get("answer_type", "choice"),
                    choices=q.get("choices") or [],
                )
            )
        if len(result) >= 5:
            break
    return result


def _select_via_llm(
    canonical_text: str,
    questions: list[dict],
    ctx: dict,
    profile_row: ResumeProfile,
) -> list[OnboardingQuestionOut]:
    """LLM-based classifier (Haiku) — behind feature flag, returns up to 5 question IDs."""
    import hashlib
    import json
    import time

    from openai import OpenAI

    from app.core.config import settings
    from app.services.openai_usage import record_responses_usage
    from app.services.pii_scrubber import scrub_pii

    scrubbed_text, _counters = scrub_pii(canonical_text)
    canon_hash = hashlib.sha256(scrubbed_text.encode()).hexdigest()[:16]
    cache_key = f"onboarding:{canon_hash}:{YAML_VERSION}"

    if cache_key in _LLM_SELECT_CACHE:
        ids = _LLM_SELECT_CACHE[cache_key]
    else:
        q_list = [{"id": q["id"], "triggers": q.get("triggers")} for q in questions]
        prompt = (
            "Given the resume text and the list of question triggers below, "
            "return a JSON array of up to 5 question IDs that are most relevant. "
            "Return ONLY the JSON array, no explanation.\n\n"
            f"Resume (truncated):\n{scrubbed_text[:2000]}\n\n"
            f"Questions: {json.dumps(q_list, ensure_ascii=False)}"
        )

        DEFAULT_BASE_URL = "https://api.openai.com/v1"
        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or DEFAULT_BASE_URL,
            timeout=30,
        )
        started = time.monotonic()
        try:
            resp = client.responses.create(
                model="gpt-4o-mini",
                input=[{"role": "user", "content": prompt}],
                text={"format": {"type": "text"}},
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            usage = getattr(resp, "usage", None)
            record_responses_usage(
                input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
                model="gpt-4o-mini",
                duration_ms=duration_ms,
            )
            text = resp.output_text.strip()
            ids = json.loads(text)
            if not isinstance(ids, list):
                ids = []
        except Exception as exc:
            logger.warning("onboarding LLM classifier failed: %s", exc)
            ids = []
        _LLM_SELECT_CACHE[cache_key] = ids

    # build output from selected IDs
    q_map = {q["id"]: q for q in questions}
    result: list[OnboardingQuestionOut] = []
    for qid in ids:
        if qid in q_map:
            q = q_map[qid]
            result.append(
                OnboardingQuestionOut(
                    id=qid,
                    text=q.get("text", ""),
                    answer_type=q.get("answer_type", "choice"),
                    choices=q.get("choices") or [],
                )
            )
    return result


# Simple in-process LLM result cache (no new DB table as specified)
_LLM_SELECT_CACHE: dict[str, list] = {}


def upsert_answer(db: Session, resume_id: int, question_id: str, answer_value: str) -> None:
    existing = db.scalar(
        select(ResumeClarification).where(
            ResumeClarification.resume_id == resume_id,
            ResumeClarification.question_id == question_id,
        )
    )
    if existing:
        existing.answer_value = answer_value
    else:
        db.add(
            ResumeClarification(
                resume_id=resume_id,
                question_id=question_id,
                answer_value=answer_value,
            )
        )
    db.commit()


def list_answers(db: Session, resume_id: int) -> list[ResumeClarification]:
    return list(
        db.scalars(
            select(ResumeClarification).where(ResumeClarification.resume_id == resume_id)
        ).all()
    )
