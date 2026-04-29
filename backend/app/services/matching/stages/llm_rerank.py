"""LLM rerank stage (Phase 2.5b).

Takes the top-K candidates after cross-encoder + MMR + tier labelling
and asks a cheap LLM to re-rank them and emit a ``requirements_check``
per card.  Runs after ``TierStage`` so the LLM only burns budget on
strong/maybe candidates — relaxed fallback cards skip the call.

Off by default (``llm_rerank_enabled=False``). When enabled:

1. Build a compact prompt with the resume profile + per-vacancy rows.
2. Hit ``openai.responses.create`` with a strict JSON schema.
3. Cache by ``(resume_id, sorted vacancy ids, model)`` — 24 h TTL.
4. Apply the returned order + write ``requirements_check`` onto each
   candidate's ``annotations`` so ``_candidate_to_match_dict`` surfaces
   it in the public match-result profile.

Budget guard: skip when daily spend + estimated cost >= user budget.
The matching request is still allowed through — the UI gets
``rerank_skipped=True``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import APIConnectionError, APIStatusError, OpenAI

from app.core.config import settings
from app.services.openai_usage import record_responses_usage
from app.services.resume_analyzer import DEFAULT_OPENAI_BASE_URL

from ..state import MatchingState
from .base import BaseStage

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You rerank vacancies for a jobseeker and produce a structured requirements checklist per vacancy. "
    "Input: a resume profile and up to 20 vacancies, each with must_have_skills, nice_to_have_skills, "
    "requirements, and summary. "
    "For every vacancy output a ranked entry with: "
    "(1) position (1-based), "
    "(2) confidence in [0,1], "
    "(3) requirements_check — an object with: "
    "  must_have: include EVERY item from the input must_have_skills AND every standalone requirement "
    "  from the input requirements list as a SEPARATE checklist entry. Do NOT merge, summarize, or "
    "  drop items. Cap at 12 only if input exceeds 12 — pick the 12 most critical. "
    "  Each entry is {text, status, evidence}. text is the requirement copied (or lightly normalized) "
    "  from input. "
    "  nice_to_have: include EVERY item from input nice_to_have_skills as a separate entry, same rules, "
    "  cap at 12. If input nice_to_have_skills is empty, return an empty list. "
    "  experience: {required_years, candidate_years, status} or null if no explicit year count is stated "
    "  in the requirements text. "
    "status must be exactly one of: ok, partial, missing, unknown. "
    "evidence is a short Russian phrase (5-10 words): for ok/partial/missing — what in the resume confirms it; "
    "for unknown — why the requirement is ambiguous. "
    "All text in Russian. Never invent requirements not present in the input."
)


class LLMRerankStage(BaseStage):
    name = "llm_rerank"

    def run(self, state: MatchingState) -> MatchingState:
        if not settings.llm_rerank_enabled:
            return state
        if not settings.openai_api_key:
            return state

        surviving = [c for c in state.candidates if not c.drop_reason]
        if not surviving:
            return state

        surviving.sort(key=lambda c: c.hybrid_score, reverse=True)
        top_k = min(settings.llm_rerank_top_k, len(surviving))
        head = surviving[:top_k]

        if not _budget_ok(state):
            state.diagnostics.custom["llm_rerank_skipped_budget"] = 1
            for cand in head:
                cand.annotations["rerank_skipped"] = True
            return state

        from app.services import rerank_cache  # noqa: PLC0415

        vacancy_ids = [c.vacancy_id for c in head]
        cached = rerank_cache.read(
            state.resume_context.resume_id, vacancy_ids, settings.llm_rerank_model
        )
        if cached is not None:
            state.diagnostics.custom["llm_rerank_cache_hit"] = 1
            reordered = _reorder_from_ranked(head, cached)
            _splice_head(state, reordered, size=len(head))
            return state

        try:
            result = _call_llm(state, head)
        except Exception as error:  # noqa: BLE001
            logger.exception("llm rerank failed, falling back: %s", error)
            state.diagnostics.custom["llm_rerank_fallback"] = 1
            for cand in head:
                cand.annotations["rerank_skipped"] = True
            return state

        rerank_cache.write(
            state.resume_context.resume_id, vacancy_ids, settings.llm_rerank_model, result
        )
        reordered = _reorder_from_ranked(head, result)
        _splice_head(state, reordered, size=len(head))
        state.diagnostics.custom["llm_rerank_applied"] = len(head)
        return state


def _budget_ok(state: MatchingState) -> bool:
    """Return True if we have budget headroom for one LLM rerank call."""
    user_id = getattr(state.resume_context, "user_id", None)
    if user_id is None:
        return True
    try:
        from datetime import date  # noqa: PLC0415

        from app.db.session import SessionLocal  # noqa: PLC0415
        from app.repositories.user_daily_spend import get_daily_spend_usd  # noqa: PLC0415

        with SessionLocal() as db:
            spend = get_daily_spend_usd(db, user_id=user_id, on_date=date.today())
    except Exception:  # noqa: BLE001
        return True

    headroom = settings.openai_user_daily_budget_usd - spend
    return headroom >= settings.llm_rerank_budget_floor_usd


def _call_llm(state: MatchingState, head: list) -> dict[str, Any]:
    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or DEFAULT_OPENAI_BASE_URL,
        timeout=settings.openai_analysis_timeout_seconds,
    )
    prompt_payload = _build_prompt_payload(state, head)
    response = client.responses.create(
        model=settings.llm_rerank_model,
        input=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "rerank_result",
                "schema": _RESULT_SCHEMA,
                "strict": True,
            }
        },
    )
    try:
        usage = getattr(response, "usage", None)
        record_responses_usage(
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            model=settings.llm_rerank_model,
            duration_ms=0,
        )
    except (APIStatusError, APIConnectionError):  # pragma: no cover
        pass
    return json.loads(response.output_text)


def _build_prompt_payload(state: MatchingState, head: list) -> dict[str, Any]:
    analysis = state.resume_context.analysis or {}
    resume = {
        "target_role": analysis.get("target_role"),
        "specialization": analysis.get("specialization"),
        "seniority": analysis.get("seniority"),
        "role_family": analysis.get("role_family"),
        "skills": state.resume_context.resume_hard_skills or [],
        "total_years": analysis.get("total_years"),
        "location": analysis.get("home_city"),
    }
    vacancies = []
    for cand in head:
        payload = cand.payload or {}
        vacancies.append(
            {
                "vacancy_id": cand.vacancy_id,
                "title": getattr(cand.vacancy, "title", "") or "",
                "company": getattr(cand.vacancy, "company", None),
                "role_family": payload.get("role_family"),
                "must_have_skills": payload.get("must_have_skills") or [],
                "nice_to_have_skills": payload.get("nice_to_have_skills") or [],
                "requirements": payload.get("requirements") or [],
                "summary": payload.get("summary") or "",
            }
        )
    return {"resume": resume, "vacancies": vacancies}


def _reorder_from_ranked(head: list, result: dict[str, Any]) -> list:
    """Return the reordered head with requirements_check annotations applied.

    Candidates the LLM didn't rank are kept at the end in their original
    order. Score is nudged so the LLM-chosen order survives any
    downstream re-sort by hybrid_score.
    """
    ranked = result.get("ranked") if isinstance(result, dict) else None
    if not isinstance(ranked, list):
        return list(head)
    by_id = {c.vacancy_id: c for c in head}
    new_order: list = []
    for entry in ranked:
        if not isinstance(entry, dict):
            continue
        cand = by_id.pop(entry.get("vacancy_id"), None)
        if cand is None:
            continue
        req_check = entry.get("requirements_check")
        confidence = entry.get("confidence")
        if isinstance(req_check, dict):
            # Enforce list length caps
            if isinstance(req_check.get("must_have"), list):
                req_check["must_have"] = req_check["must_have"][:12]
            if isinstance(req_check.get("nice_to_have"), list):
                req_check["nice_to_have"] = req_check["nice_to_have"][:12]
            cand.annotations["requirements_check"] = req_check
        if isinstance(confidence, (int, float)):
            cand.annotations["llm_confidence"] = float(confidence)
        new_order.append(cand)
    # Append leftovers — LLM may skip; never lose candidates.
    for cand in head:
        if cand.vacancy_id in by_id:
            new_order.append(cand)
    # Preserve real hybrid_score magnitudes — just redistribute existing scores
    # along the LLM-chosen order so the top vacancy keeps the top number, etc.
    # This stops the percentage in the UI from collapsing to 100%/99%/98%...
    # while still letting any downstream re-sort by hybrid_score honour the
    # rerank order.
    sorted_scores = sorted((c.hybrid_score for c in new_order), reverse=True)
    for i, cand in enumerate(new_order):
        if i < len(sorted_scores):
            cand.hybrid_score = sorted_scores[i]
        cand.annotations["llm_rerank_position"] = i + 1
    return new_order


def _splice_head(state: MatchingState, reordered: list, *, size: int) -> None:
    """Replace the top ``size`` surviving candidates in state.candidates.

    Preserves the position of dropped candidates and any tail beyond the
    reranked window.
    """
    surviving = [c for c in state.candidates if not c.drop_reason]
    dropped = [c for c in state.candidates if c.drop_reason]
    tail = surviving[size:]
    state.candidates = reordered + tail + dropped


_CHECKLIST_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "text": {"type": "string"},
        "status": {"type": "string", "enum": ["ok", "partial", "missing", "unknown"]},
        "evidence": {"type": "string"},
    },
    "required": ["text", "status", "evidence"],
}

_EXPERIENCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "required_years": {"type": "number"},
        "candidate_years": {"type": ["number", "null"]},
        "status": {"type": "string", "enum": ["ok", "partial", "missing", "unknown"]},
    },
    "required": ["required_years", "candidate_years", "status"],
}

_REQUIREMENTS_CHECK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "must_have": {"type": "array", "items": _CHECKLIST_ITEM_SCHEMA},
        "nice_to_have": {"type": "array", "items": _CHECKLIST_ITEM_SCHEMA},
        "experience": {"anyOf": [_EXPERIENCE_SCHEMA, {"type": "null"}]},
    },
    "required": ["must_have", "nice_to_have", "experience"],
}

_RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "ranked": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "vacancy_id": {"type": "integer"},
                    "position": {"type": "integer"},
                    "confidence": {"type": "number"},
                    "requirements_check": _REQUIREMENTS_CHECK_SCHEMA,
                },
                "required": ["vacancy_id", "position", "confidence", "requirements_check"],
            },
        }
    },
    "required": ["ranked"],
}
