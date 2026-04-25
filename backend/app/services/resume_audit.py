"""Phase 5.0.1 — Resume audit engine.

Computes a 4-block structured audit for a resume:
  1. Role read (from existing ESCO profile)
  2. Market salary band (salary_predictor + baseline)
  3. Skill gaps top-5 (vacancy corpus frequency)
  4. Resume signal quality (pure rule-based)

Results are cached in resume_audits table keyed by (resume_hash, prompt_version).
TTL = settings.resume_audit_cache_ttl_days (default 7 days).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.resume import Resume
from app.models.resume_audit import ResumeAudit
from app.models.resume_profile import ResumeProfile
from app.models.vacancy_profile import VacancyProfile
from app.schemas.resume_audit import (
    AltRole,
    MarketSalaryBand,
    ResumeAuditOut,
    ResumeQualityIssue,
    RoleRead,
    SkillGap,
)
from app.services import salary_predictor
from app.services.openai_usage import record_responses_usage
from app.services.skill_taxonomy import expand_concept

logger = logging.getLogger(__name__)

PROMPT_VERSION = "audit-v1"

# Seniority year bands for quality rule
_SENIORITY_BANDS: dict[str, tuple[float, float]] = {
    "junior": (0.0, 2.0),
    "middle": (2.0, 5.0),
    "senior": (5.0, 999.0),
    "lead": (5.0, 999.0),
    "staff": (7.0, 999.0),
    "principal": (10.0, 999.0),
}

_METRICS_RE = re.compile(
    r"\b\d+(\.\d+)?\s*(%|млн|тыс|k\b|m\b|x\b|раз\b)",
    re.IGNORECASE,
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")


# ---------------------------------------------------------------------------
# LLM normalization (skill synonym batching) — cached in-process
# ---------------------------------------------------------------------------


# Process-local cache: cache_key -> (mapping_json, cost_usd_at_first_call).
# Cost is 0 on hit so callers attribute the spend only to the request that
# actually paid for it. Bounded by manual eviction in _LLM_CACHE_MAX.
_LLM_CACHE_MAX = 256
_LLM_CACHE: dict[str, tuple[str, float]] = {}


def _llm_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Apply the same per-1M pricing the rest of the app uses (config-driven)."""
    safety = settings.openai_cost_safety_multiplier
    in_cost = (input_tokens / 1_000_000.0) * settings.openai_responses_input_usd_per_1m
    out_cost = (output_tokens / 1_000_000.0) * settings.openai_responses_output_usd_per_1m
    return (in_cost + out_cost) * safety


def _normalize_via_llm_cached(cache_key: str, skills_json: str) -> tuple[str, float]:
    """Return (mapping_json, cost_usd_for_this_call). Cost is 0 on cache hit."""
    cached = _LLM_CACHE.get(cache_key)
    if cached is not None:
        return cached[0], 0.0

    from openai import OpenAI

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    client_opts: dict = {
        "api_key": settings.openai_api_key,
        "timeout": 30,
    }
    client_opts["base_url"] = settings.openai_base_url or DEFAULT_BASE_URL
    client = OpenAI(**client_opts)

    skills = json.loads(skills_json)
    prompt = (
        "Normalize the following skill names to their canonical English form. "
        "Return ONLY a JSON object mapping each input string to its canonical name. "
        "Examples: 'k8s' -> 'Kubernetes', 'js' -> 'JavaScript', 'py' -> 'Python'. "
        "If already canonical, return as-is.\n\n"
        f"Skills: {json.dumps(skills, ensure_ascii=False)}"
    )

    started = time.monotonic()
    response = client.responses.create(
        model="gpt-4o-mini",
        input=[{"role": "user", "content": prompt}],
        text={"format": {"type": "text"}},
    )
    duration_ms = int((time.monotonic() - started) * 1000)

    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    record_responses_usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model="gpt-4o-mini",
        duration_ms=duration_ms,
    )
    cost = _llm_cost_usd(input_tokens, output_tokens)

    try:
        text = response.output_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
    except Exception:
        text = skills_json

    if len(_LLM_CACHE) >= _LLM_CACHE_MAX:
        _LLM_CACHE.pop(next(iter(_LLM_CACHE)))
    _LLM_CACHE[cache_key] = (text, cost)
    return text, cost


def _normalize_skills(
    skills: list[str],
    *,
    role_family: str | None,
    seniority: str | None,
    use_llm: bool,
) -> tuple[dict[str, str], float]:
    """Return ({raw_skill: canonical_skill}, llm_cost_usd_for_this_call)."""
    if not skills:
        return {}, 0.0

    result: dict[str, str] = {}
    unresolved: list[str] = []
    for skill in skills:
        forms = expand_concept(skill)
        canonical = sorted(forms)[0] if forms else skill.lower().strip()
        result[skill] = canonical
        if canonical == skill.lower().strip():
            unresolved.append(skill)

    if not use_llm or not settings.openai_api_key or not unresolved:
        return result, 0.0

    cost = 0.0
    try:
        skills_sorted = sorted({s.lower().strip() for s in unresolved})
        skills_hash = hashlib.sha256(json.dumps(skills_sorted).encode()).hexdigest()[:16]
        cache_key = f"{role_family or ''}:{seniority or ''}:{skills_hash}"
        mapping_json, cost = _normalize_via_llm_cached(cache_key, json.dumps(skills_sorted))
        mapping = json.loads(mapping_json)
        for skill in unresolved:
            key = skill.lower().strip()
            if key in mapping:
                result[skill] = mapping[key]
    except Exception as exc:
        logger.warning("LLM skill normalization failed: %s", exc)

    return result, cost


# ---------------------------------------------------------------------------
# Daily cost helper
# ---------------------------------------------------------------------------


def _audit_daily_cost_for_user(db: Session, user_id: int) -> float:
    """Sum cost_usd from resume_audits rows (via user's resumes) created today UTC."""
    from app.models.resume import Resume as ResumeModel

    today_utc = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    result = db.scalar(
        select(func.coalesce(func.sum(ResumeAudit.cost_usd), 0.0))
        .join(ResumeModel, ResumeModel.id == ResumeAudit.resume_id)
        .where(
            ResumeModel.user_id == user_id,
            ResumeAudit.computed_at >= today_utc,
        )
    )
    return float(result or 0.0)


# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------


def _build_role_read(profile: dict) -> RoleRead:
    role_family = profile.get("role_family") or "unknown"
    seniority = profile.get("seniority")
    confidence = float(profile.get("seniority_confidence") or 1.0)

    primary = {"role_family": role_family, "seniority": seniority, "confidence": confidence}

    alts: list[AltRole] = []
    for alt in (profile.get("role_alternatives") or [])[:2]:
        if isinstance(alt, dict):
            alts.append(
                AltRole(
                    role_family=str(alt.get("role_family") or "unknown"),
                    seniority=alt.get("seniority"),
                    confidence=float(alt.get("confidence") or 0.5),
                )
            )
    return RoleRead(primary=primary, alt=alts)


def _build_market_salary(
    db: Session,
    profile: dict,
    role_family: str | None,
    seniority: str | None,
) -> MarketSalaryBand | None:
    city = profile.get("location") or profile.get("city") or profile.get("home_city")
    band = salary_predictor.predict(
        role_family=role_family,
        seniority=seniority,
        city=city,
    )
    if band is None:
        return None

    user_expectation: int | None = None
    raw_exp = profile.get("salary_expectation")
    if raw_exp is not None:
        try:
            user_expectation = int(raw_exp)
        except (ValueError, TypeError):
            pass

    gap_pct: float | None = None
    if user_expectation is not None and band.p50 > 0:
        gap_pct = round((user_expectation - band.p50) / band.p50 * 100.0, 1)

    # count vacancy_profiles in same (role_family, seniority) bucket
    sample_size: int | None = None
    try:
        count_q = select(func.count(VacancyProfile.id))
        rows = db.execute(count_q).all()
        # approximate: count all profiles (we can't filter by JSON role_family cheaply)
        sample_size = int(rows[0][0]) if rows else None
    except Exception:
        pass

    return MarketSalaryBand(
        p25=band.p25,
        p50=band.p50,
        p75=band.p75,
        currency="RUB",
        model_version=band.model_version,
        user_expectation=user_expectation,
        gap_to_median_pct=gap_pct,
        sample_size=sample_size,
    )


def _build_skill_gaps(
    db: Session,
    profile: dict,
    role_family: str | None,
    seniority: str | None,
    *,
    use_llm: bool,
) -> tuple[list[SkillGap], float]:
    """Return (gaps, llm_cost_usd_for_this_call)."""
    TOP_N = 50

    # Gather market skills from vacancy_profiles
    vp_rows = db.scalars(select(VacancyProfile).limit(500)).all()

    market_skill_counts: dict[str, int] = {}
    total_profiles = len(vp_rows)

    for vp in vp_rows:
        vp_profile = vp.profile or {}
        # filter by role_family / seniority if available
        vp_role = vp_profile.get("role_family")
        if role_family and vp_role and vp_role != role_family:
            continue
        req_skills = vp_profile.get("required_skills") or vp_profile.get("skills") or []
        if not isinstance(req_skills, list):
            req_skills = []
        seen_in_this_vp: set[str] = set()
        for skill in req_skills:
            if not isinstance(skill, str):
                continue
            key = skill.lower().strip()
            if key and key not in seen_in_this_vp:
                market_skill_counts[key] = market_skill_counts.get(key, 0) + 1
                seen_in_this_vp.add(key)

    # top-N market skills
    sorted_market = sorted(market_skill_counts.items(), key=lambda x: -x[1])[:TOP_N]
    if not sorted_market:
        return [], 0.0

    segment_count = max(total_profiles, 1)

    # user skills
    user_skills_raw = profile.get("skills") or profile.get("hard_skills") or []
    if not isinstance(user_skills_raw, list):
        user_skills_raw = []

    all_skills_to_normalize = [s for s, _ in sorted_market] + [
        s for s in user_skills_raw if isinstance(s, str)
    ]
    norm_map, llm_cost = _normalize_skills(
        all_skills_to_normalize,
        role_family=role_family,
        seniority=seniority,
        use_llm=use_llm,
    )

    # user skill canonical set
    user_canonical: set[str] = set()
    for s in user_skills_raw:
        if isinstance(s, str):
            canonical = norm_map.get(s.lower().strip(), s.lower().strip())
            user_canonical.add(canonical)
            # also expand via taxonomy
            for form in expand_concept(s):
                user_canonical.add(form)

    gaps: list[SkillGap] = []
    for raw_skill, count in sorted_market:
        canonical = norm_map.get(raw_skill, raw_skill)
        owned = canonical in user_canonical or raw_skill in user_canonical
        if not owned:
            pct = round(count / segment_count * 100.0, 1)
            gaps.append(
                SkillGap(
                    skill=canonical,
                    vacancies_with_skill_pct=pct,
                    vacancies_count_in_segment=count,
                    owned=False,
                )
            )
        if len(gaps) >= 5:
            break

    return gaps[:5], llm_cost


def _build_quality_issues(profile: dict) -> list[ResumeQualityIssue]:
    issues: list[ResumeQualityIssue] = []

    # Rule 1: years_match_seniority
    seniority = (profile.get("seniority") or "").lower()
    total_years = profile.get("total_experience_years")
    if seniority and total_years is not None:
        band = _SENIORITY_BANDS.get(seniority)
        if band is not None:
            lo, hi = band
            try:
                yrs = float(total_years)
            except (ValueError, TypeError):
                yrs = None
            if yrs is not None and not (lo <= yrs <= hi):
                issues.append(
                    ResumeQualityIssue(
                        rule_id="years_match_seniority",
                        severity="warn",
                        message=(
                            f"Опыт {yrs:.1f} лет не соответствует уровню {seniority} "
                            f"(ожидается {lo}–{hi} лет)."
                        ),
                    )
                )

    # Rule 2: experiences_have_stack
    experiences = profile.get("experience") or []
    if isinstance(experiences, list):
        missing_stack = any(
            isinstance(exp, dict)
            and not (exp.get("stack") or exp.get("tools") or exp.get("skills"))
            for exp in experiences
        )
        if missing_stack and experiences:
            issues.append(
                ResumeQualityIssue(
                    rule_id="experiences_have_stack",
                    severity="info",
                    message="В некоторых позициях опыта не указан технический стек.",
                )
            )

    # Rule 3: experiences_have_metrics
    all_highlights: list[str] = []
    if isinstance(experiences, list):
        for exp in experiences:
            if isinstance(exp, dict):
                for h in exp.get("highlights") or []:
                    if isinstance(h, str):
                        all_highlights.append(h)
    combined_text = " ".join(all_highlights)
    if combined_text and not _METRICS_RE.search(combined_text):
        issues.append(
            ResumeQualityIssue(
                rule_id="experiences_have_metrics",
                severity="info",
                message=(
                    "В описании опыта не найдено измеримых результатов (числа, проценты, объёмы)."
                ),
            )
        )

    # Rule 4: contact_minimalism (privacy check)
    canonical_text_sample = str(profile)
    has_email = bool(_EMAIL_RE.search(canonical_text_sample))
    has_phone = bool(_PHONE_RE.search(canonical_text_sample))
    if has_email or has_phone:
        issues.append(
            ResumeQualityIssue(
                rule_id="contact_minimalism",
                severity="error",
                message=(
                    "В профиле обнаружены контактные данные (email/телефон). "
                    "Privacy Level A: контакты не должны попадать в профиль."
                ),
            )
        )

    return issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_audit(
    db: Session,
    resume_id: int,
    user_id: int,
    *,
    force: bool = False,
) -> ResumeAuditOut:
    if not settings.feature_resume_audit_enabled:
        raise RuntimeError("resume_audit_disabled")

    # Load resume + profile
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise LookupError(f"Resume {resume_id} not found")

    profile_row = db.scalar(select(ResumeProfile).where(ResumeProfile.resume_id == resume_id))
    if profile_row is None:
        raise ValueError("no_profile")

    profile = profile_row.profile or {}
    canonical_text = profile_row.canonical_text or ""

    # Cache key
    resume_hash = hashlib.sha256(f"{canonical_text}{PROMPT_VERSION}".encode()).hexdigest()

    # Check cache
    existing = db.scalar(select(ResumeAudit).where(ResumeAudit.resume_id == resume_id))
    if existing and not force:
        cached_json = existing.audit_json or {}
        if cached_json.get("resume_hash") == resume_hash:
            ttl_days = settings.resume_audit_cache_ttl_days
            age = datetime.now(UTC) - existing.computed_at.replace(tzinfo=UTC)
            if age < timedelta(days=ttl_days):
                return _deserialize(existing, resume_id)

    # Determine template mode
    template_mode = settings.feature_resume_audit_template_mode_enabled
    if not template_mode:
        daily_cost = _audit_daily_cost_for_user(db, user_id)
        if daily_cost > settings.resume_audit_cost_cap_usd_per_day:
            template_mode = True

    use_llm = not template_mode

    # Build blocks
    role_family = profile.get("role_family")
    seniority = profile.get("seniority")

    role_read = _build_role_read(profile)
    market_salary = _build_market_salary(db, profile, role_family, seniority)
    skill_gaps, skill_gaps_cost = _build_skill_gaps(
        db, profile, role_family, seniority, use_llm=use_llm
    )
    quality_issues = _build_quality_issues(profile)

    # triggered_question_ids — filled by onboarding service, stub here
    triggered_ids: list[str] = []

    audit_data: dict = {
        "resume_hash": resume_hash,
        "role_read": role_read.model_dump(),
        "market_salary": market_salary.model_dump() if market_salary else None,
        "skill_gaps": [sg.model_dump() for sg in skill_gaps],
        "quality_issues": [qi.model_dump() for qi in quality_issues],
        "triggered_question_ids": triggered_ids,
        "template_mode_active": template_mode,
    }

    now = datetime.now(UTC)
    cost_usd: float | None = skill_gaps_cost if skill_gaps_cost > 0 else None

    if existing:
        existing.audit_json = audit_data
        existing.prompt_version = PROMPT_VERSION
        existing.computed_at = now
        existing.cost_usd = cost_usd
        db.flush()
    else:
        new_row = ResumeAudit(
            resume_id=resume_id,
            audit_json=audit_data,
            prompt_version=PROMPT_VERSION,
            computed_at=now,
            cost_usd=cost_usd,
        )
        db.add(new_row)
        db.flush()

    db.commit()

    return ResumeAuditOut(
        resume_id=resume_id,
        computed_at=now,
        prompt_version=PROMPT_VERSION,
        role_read=role_read,
        market_salary=market_salary,
        skill_gaps=skill_gaps,
        quality_issues=quality_issues,
        triggered_question_ids=triggered_ids,
        template_mode_active=template_mode,
    )


def _deserialize(row: ResumeAudit, resume_id: int) -> ResumeAuditOut:
    data = row.audit_json or {}
    role_read_raw = data.get("role_read") or {}
    market_raw = data.get("market_salary")
    skill_gaps_raw = data.get("skill_gaps") or []
    quality_raw = data.get("quality_issues") or []

    role_read = RoleRead(
        primary=role_read_raw.get("primary") or {},
        alt=[AltRole(**a) for a in (role_read_raw.get("alt") or [])],
    )
    market = MarketSalaryBand(**market_raw) if market_raw else None
    skill_gaps = [SkillGap(**sg) for sg in skill_gaps_raw]
    quality_issues = [ResumeQualityIssue(**qi) for qi in quality_raw]

    return ResumeAuditOut(
        resume_id=resume_id,
        computed_at=row.computed_at,
        prompt_version=row.prompt_version,
        role_read=role_read,
        market_salary=market,
        skill_gaps=skill_gaps,
        quality_issues=quality_issues,
        triggered_question_ids=data.get("triggered_question_ids") or [],
        template_mode_active=bool(data.get("template_mode_active", False)),
    )
