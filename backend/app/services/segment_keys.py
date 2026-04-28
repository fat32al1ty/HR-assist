from __future__ import annotations

import hashlib


def derive_segment_key(
    *,
    role_family: str,
    seniority: str,
    domains: list[str],
) -> str:
    """Return a 16-char hex segment key from role/seniority/domain dimensions.

    Normalization: lowercase, stripped, domains sorted, top-3 taken.
    Pure function — no side effects.
    """
    normalized_role = role_family.strip().lower()
    normalized_seniority = seniority.strip().lower()
    normalized_domains = sorted(d.strip().lower() for d in domains if d.strip())[:3]
    payload = normalized_role + "|" + normalized_seniority + "|" + "|".join(normalized_domains)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def query_from_resume_analysis(analysis: dict | None) -> str | None:
    """Build a free-text discovery query from a resume analysis dict.

    Public re-export of the helper that used to live as `_query_from_resume_analysis`
    inside `vacancy_warmup`. The route layer needs it to seed the
    segment_warmup payload, and importing a private symbol from a service
    is a layering smell — keep this as the single source of truth and let
    `vacancy_warmup` re-import.
    """
    if not isinstance(analysis, dict):
        return None

    role = analysis.get("target_role")
    specialization = analysis.get("specialization")

    def _as_strings(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    result.append(text)
        return result

    keywords = _as_strings(analysis.get("matching_keywords"))
    hard_skills = _as_strings(analysis.get("hard_skills"))

    parts: list[str] = []
    if isinstance(role, str) and role.strip():
        parts.append(role.strip())
    if isinstance(specialization, str) and specialization.strip():
        parts.append(specialization.strip())
    parts.extend(keywords[:4])
    parts.extend(hard_skills[:4])

    seen: set[str] = set()
    compact: list[str] = []
    for item in parts:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        compact.append(item.strip())
    if not compact:
        return None
    return " ".join(compact[:10])


def segment_key_from_analysis(analysis: dict) -> str | None:
    """Derive a segment key from a resume analysis dict.

    Returns None when the analysis doesn't have enough fields to produce a
    meaningful key (e.g. role_family missing).
    """
    if not isinstance(analysis, dict):
        return None
    role_family = analysis.get("role_family") or ""
    if not isinstance(role_family, str) or not role_family.strip():
        return None
    seniority = analysis.get("seniority") or ""
    if not isinstance(seniority, str):
        seniority = ""
    domains_raw = analysis.get("domains") or []
    if not isinstance(domains_raw, list):
        domains_raw = []
    domains = [d for d in domains_raw if isinstance(d, str) and d.strip()]
    return derive_segment_key(
        role_family=role_family,
        seniority=seniority,
        domains=domains,
    )
