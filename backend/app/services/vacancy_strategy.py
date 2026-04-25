"""Phase 5.2.1 — Vacancy-specific strategy + cover letter draft.

Produces 3 blocks for a (resume, vacancy) pair:
  1. match_highlights — top-3 experience items that match vacancy requirements.
  2. gap_mitigations — top-2 vacancy requirements the user lacks + compensation hint.
  3. cover_letter_draft — 3-paragraph draft ≤ 1200 chars.

Two paths:
  LLM path  — one gpt-4o-mini-class call, response_format JSON, PII-scrubbed input.
  Template  — rule-based skill overlap, static cover letter skeleton; no LLM.

Cache: vacancy_strategies table keyed by (resume_id, vacancy_id, prompt_version),
       TTL = settings.vacancy_strategy_cache_ttl_days (default 30 days).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.resume import Resume
from app.models.resume_profile import ResumeProfile
from app.models.vacancy import Vacancy
from app.models.vacancy_profile import VacancyProfile
from app.models.vacancy_strategy import VacancyStrategy
from app.schemas.vacancy_strategy import GapMitigation, MatchHighlight, VacancyStrategyOut
from app.services.llm_cost_accounting import daily_user_llm_cost_usd
from app.services.openai_usage import record_responses_usage
from app.services.pii_scrubber import scrub_pii

logger = logging.getLogger(__name__)

PROMPT_VERSION = "strategy-v1"

_EMAIL_STRIP_RE = re.compile(r"[\w.+\-]+@[\w.\-]+", re.IGNORECASE)
_PHONE_STRIP_RE = re.compile(
    r"(?:\+7|8)[\s\-()\*]*\d{3}[\s\-()\*]*\d{3}[\s\-()\*]*\d{2}[\s\-()\*]*\d{2}",
    re.IGNORECASE,
)
_SENTENCE_END_RE = re.compile(r"[.!?]\s")


# ---------------------------------------------------------------------------
# Output sanitizer
# ---------------------------------------------------------------------------


def _sanitize_cover_letter(text: str, max_chars: int = 1200) -> str:
    text = _EMAIL_STRIP_RE.sub("", text)
    text = _PHONE_STRIP_RE.sub("", text)
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_end = None
    for m in _SENTENCE_END_RE.finditer(truncated):
        last_end = m.start() + 1
    if last_end and last_end > max_chars // 2:
        return truncated[:last_end].rstrip()
    return truncated.rstrip()


# ---------------------------------------------------------------------------
# Skill overlap (template path)
# ---------------------------------------------------------------------------


def _skill_overlap(highlights: list[str], vacancy_skills: list[str]) -> int:
    if not highlights or not vacancy_skills:
        return 0
    lower_req = {s.lower().strip() for s in vacancy_skills if isinstance(s, str)}
    combined = " ".join(str(h) for h in highlights).lower()
    return sum(1 for sk in lower_req if sk and sk in combined)


# ---------------------------------------------------------------------------
# Template path
# ---------------------------------------------------------------------------


def _template_strategy(
    resume_id: int,
    vacancy_id: int,
    profile: dict,
    vacancy_profile_data: dict,
) -> tuple[list[MatchHighlight], list[GapMitigation], str]:
    experiences = profile.get("experience") or []
    must_haves = vacancy_profile_data.get("must_have_skills") or []
    vacancy_title = vacancy_profile_data.get("title") or "данная вакансия"

    # match highlights: top-3 by skill overlap
    scored: list[tuple[int, int, str | None, str]] = []
    for idx, exp in enumerate(experiences):
        if not isinstance(exp, dict):
            continue
        highlights = exp.get("highlights") or []
        overlap = _skill_overlap(highlights, must_haves)
        company = exp.get("company") or exp.get("employer")
        quote = highlights[0] if highlights else (exp.get("title") or "Опыт работы")
        if isinstance(quote, list):
            quote = str(quote[0]) if quote else "Опыт работы"
        scored.append((overlap, idx, company, str(quote)))

    scored.sort(key=lambda x: -x[0])
    match_highlights = [
        MatchHighlight(experience_index=idx, company=company, quote=quote)
        for _, idx, company, quote in scored[:3]
    ]

    # gap mitigations: top-2 must_haves not found in any experience
    user_skills_raw = profile.get("skills") or profile.get("hard_skills") or []
    user_lower = {s.lower().strip() for s in user_skills_raw if isinstance(s, str)}
    all_exp_text = " ".join(
        " ".join(str(h) for h in (e.get("highlights") or []))
        for e in experiences
        if isinstance(e, dict)
    ).lower()

    gap_mitigations: list[GapMitigation] = []
    for req in must_haves:
        if not isinstance(req, str):
            continue
        req_lower = req.lower().strip()
        if req_lower in user_lower or req_lower in all_exp_text:
            continue
        adjacent = next((s for s in user_skills_raw if isinstance(s, str)), None)
        if adjacent:
            mitigation = (
                f"Прямого опыта с {req} нет, но смежный навык «{adjacent}» "
                "позволяет быстро войти в тему — укажите это в сопроводительном письме."
            )
        else:
            mitigation = (
                f"Опыта с {req} нет в резюме — сделайте акцент на готовности "
                "быстро обучиться в сопроводительном письме."
            )
        gap_mitigations.append(
            GapMitigation(requirement=req, user_signal=adjacent, mitigation_text=mitigation)
        )
        if len(gap_mitigations) >= 2:
            break

    # cover letter skeleton
    h1_quote = match_highlights[0].quote if match_highlights else "мой опыт"
    h2_quote = match_highlights[1].quote if len(match_highlights) > 1 else ""
    h3_quote = match_highlights[2].quote if len(match_highlights) > 2 else ""
    gap_hint = gap_mitigations[0].mitigation_text if gap_mitigations else ""

    cover = (
        f"Меня привлекает позиция {vacancy_title}, потому что она совпадает с моим опытом: "
        f"{h1_quote}.\n\n"
        f"{'В своей работе я также ' + h2_quote + '.' if h2_quote else ''} "
        f"{gap_hint}\n\n"
        f"{'Кроме того, ' + h3_quote + '.' if h3_quote else ''} "
        "Буду рад обсудить детали на интервью."
    )

    return match_highlights, gap_mitigations, _sanitize_cover_letter(cover.strip())


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------


def _llm_strategy(
    resume_id: int,
    vacancy_id: int,
    scrubbed_resume_text: str,
    vacancy_canonical_text: str,
    vacancy_profile_data: dict,
) -> tuple[list[MatchHighlight], list[GapMitigation], str, float]:
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or "https://api.openai.com/v1",
        timeout=settings.openai_analysis_timeout_seconds,
    )

    system_prompt = (
        "You are an expert career consultant. "
        "Given a scrubbed resume profile and a job vacancy, produce a structured JSON strategy. "
        "The strategy must contain:\n"
        '  "match_highlights": array of exactly 3 objects with keys '
        '"experience_index" (int, 0-based index into the resume experience array), '
        '"company" (string or null), "quote" (1-line citation from experience highlights).\n'
        '  "gap_mitigations": array of exactly 2 objects with keys '
        '"requirement" (vacancy requirement string), '
        '"user_signal" (adjacent skill the user has, or null), '
        '"mitigation_text" (1 sentence on how to address in cover letter).\n'
        '  "cover_letter_draft": string, 3 paragraphs, ≤ 1200 characters, structured as: '
        "hook using match highlight #1 → body using match highlight #2 + gap mitigation → "
        "close using match highlight #3. Write in Russian. "
        "Do NOT include any email address, phone number, or personal name.\n"
        "Return ONLY valid JSON, no markdown fences."
    )

    user_prompt = (
        f"RESUME (PII-scrubbed):\n{scrubbed_resume_text}\n\n"
        f"VACANCY:\n{vacancy_canonical_text}\n\n"
        f"VACANCY REQUIREMENTS (must_have_skills): "
        f"{json.dumps(vacancy_profile_data.get('must_have_skills') or [], ensure_ascii=False)}"
    )

    started = time.monotonic()
    response = client.responses.create(
        model=settings.openai_matching_model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={"format": {"type": "json_object"}},
        max_output_tokens=1500,
    )
    duration_ms = int((time.monotonic() - started) * 1000)

    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    record_responses_usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=settings.openai_matching_model,
        duration_ms=duration_ms,
    )

    safety = settings.openai_cost_safety_multiplier
    in_cost = (input_tokens / 1_000_000.0) * settings.openai_responses_input_usd_per_1m
    out_cost = (output_tokens / 1_000_000.0) * settings.openai_responses_output_usd_per_1m
    cost_usd = (in_cost + out_cost) * safety

    raw_text = response.output_text.strip()
    data = json.loads(raw_text)

    match_highlights: list[MatchHighlight] = []
    for item in (data.get("match_highlights") or [])[:3]:
        if not isinstance(item, dict):
            continue
        match_highlights.append(
            MatchHighlight(
                experience_index=int(item.get("experience_index") or 0),
                company=item.get("company"),
                quote=str(item.get("quote") or ""),
            )
        )

    gap_mitigations: list[GapMitigation] = []
    for item in (data.get("gap_mitigations") or [])[:2]:
        if not isinstance(item, dict):
            continue
        gap_mitigations.append(
            GapMitigation(
                requirement=str(item.get("requirement") or ""),
                user_signal=item.get("user_signal"),
                mitigation_text=str(item.get("mitigation_text") or ""),
            )
        )

    cover_letter = _sanitize_cover_letter(str(data.get("cover_letter_draft") or ""))

    return match_highlights, gap_mitigations, cover_letter, cost_usd


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _resume_hash(canonical_text: str) -> str:
    return hashlib.sha256(canonical_text.encode()).hexdigest()[:32]


def _vacancy_hash(canonical_text: str) -> str:
    return hashlib.sha256(canonical_text.encode()).hexdigest()[:32]


def _fetch_cached(db: Session, resume_id: int, vacancy_id: int) -> VacancyStrategy | None:
    return db.scalar(
        select(VacancyStrategy).where(
            VacancyStrategy.resume_id == resume_id,
            VacancyStrategy.vacancy_id == vacancy_id,
            VacancyStrategy.prompt_version == PROMPT_VERSION,
        )
    )


def _is_fresh(row: VacancyStrategy) -> bool:
    ttl_days = settings.vacancy_strategy_cache_ttl_days
    age = datetime.now(UTC) - row.computed_at.replace(tzinfo=UTC)
    return age < timedelta(days=ttl_days)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_strategy(
    db: Session,
    resume_id: int,
    vacancy_id: int,
    user_id: int,
    *,
    force: bool = False,
) -> VacancyStrategyOut:
    if not settings.feature_vacancy_strategy_enabled:
        raise RuntimeError("vacancy_strategy_disabled")

    resume = db.get(Resume, resume_id)
    if resume is None:
        raise LookupError(f"Resume {resume_id} not found")

    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise LookupError(f"Vacancy {vacancy_id} not found")

    profile_row = db.scalar(select(ResumeProfile).where(ResumeProfile.resume_id == resume_id))
    if profile_row is None:
        raise ValueError("no_resume_profile")

    vp_row = db.scalar(select(VacancyProfile).where(VacancyProfile.vacancy_id == vacancy_id))
    if vp_row is None:
        raise ValueError("no_vacancy_profile")

    profile = profile_row.profile or {}
    canonical_text = profile_row.canonical_text or ""
    vp_data = vp_row.profile or {}
    vp_canonical = vp_row.canonical_text or ""

    # Cache check
    cached = _fetch_cached(db, resume_id, vacancy_id)
    if cached and not force and _is_fresh(cached):
        return _deserialize(cached)

    # Determine template mode
    template_mode = settings.feature_vacancy_strategy_template_mode_enabled
    if not template_mode:
        daily_cost = daily_user_llm_cost_usd(db, user_id)
        if daily_cost >= settings.vacancy_strategy_cost_cap_usd_per_day:
            template_mode = True

    cost_usd: float | None = None

    if template_mode or not settings.openai_api_key:
        match_highlights, gap_mitigations, cover_letter = _template_strategy(
            resume_id, vacancy_id, profile, vp_data
        )
    else:
        scrubbed_text, _ = scrub_pii(canonical_text)
        try:
            match_highlights, gap_mitigations, cover_letter, cost_usd = _llm_strategy(
                resume_id, vacancy_id, scrubbed_text, vp_canonical, vp_data
            )
        except Exception as exc:
            logger.warning("LLM strategy failed, falling back to template: %s", exc)
            template_mode = True
            match_highlights, gap_mitigations, cover_letter = _template_strategy(
                resume_id, vacancy_id, profile, vp_data
            )

    strategy_json = {
        "match_highlights": [mh.model_dump() for mh in match_highlights],
        "gap_mitigations": [gm.model_dump() for gm in gap_mitigations],
        "cover_letter_draft": cover_letter,
        "resume_hash": _resume_hash(canonical_text),
        "vacancy_hash": _vacancy_hash(vp_canonical),
    }

    now = datetime.now(UTC)

    if cached:
        cached.strategy_json = strategy_json
        cached.cost_usd = cost_usd
        cached.template_mode = template_mode
        cached.computed_at = now
        db.flush()
    else:
        row = VacancyStrategy(
            resume_id=resume_id,
            vacancy_id=vacancy_id,
            prompt_version=PROMPT_VERSION,
            strategy_json=strategy_json,
            cost_usd=cost_usd,
            template_mode=template_mode,
            computed_at=now,
        )
        db.add(row)
        db.flush()

    db.commit()

    return VacancyStrategyOut(
        resume_id=resume_id,
        vacancy_id=vacancy_id,
        match_highlights=match_highlights,
        gap_mitigations=gap_mitigations,
        cover_letter_draft=cover_letter,
        template_mode=template_mode,
        prompt_version=PROMPT_VERSION,
        computed_at=now.isoformat(),
    )


def _deserialize(row: VacancyStrategy) -> VacancyStrategyOut:
    data = row.strategy_json or {}
    match_highlights = [MatchHighlight(**mh) for mh in (data.get("match_highlights") or [])]
    gap_mitigations = [GapMitigation(**gm) for gm in (data.get("gap_mitigations") or [])]
    return VacancyStrategyOut(
        resume_id=row.resume_id,
        vacancy_id=row.vacancy_id,
        match_highlights=match_highlights,
        gap_mitigations=gap_mitigations,
        cover_letter_draft=data.get("cover_letter_draft") or "",
        template_mode=row.template_mode,
        prompt_version=row.prompt_version,
        computed_at=row.computed_at.isoformat(),
    )
