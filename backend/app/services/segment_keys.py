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
