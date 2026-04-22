from typing import Any

from sqlalchemy.orm import Session

from app.repositories.vacancy_profiles import create_or_update_vacancy_profile
from app.services.embeddings import create_embedding
from app.services.vector_store import get_vector_store


def build_vacancy_profile_text(profile: dict[str, Any], *, title: str, company: str | None) -> str:
    parts = [
        f"Role: {profile.get('role') or title}",
        f"Company: {company or 'unknown'}",
        f"Seniority: {profile.get('seniority') or 'unknown'}",
        f"Employment type: {profile.get('employment_type') or 'unknown'}",
        f"Location: {profile.get('location') or 'unknown'}",
        f"Remote policy: {profile.get('remote_policy') or 'unknown'}",
        f"Summary: {profile.get('summary') or ''}",
        f"Must have skills: {', '.join(profile.get('must_have_skills') or [])}",
        f"Nice to have skills: {', '.join(profile.get('nice_to_have_skills') or [])}",
        f"Tools: {', '.join(profile.get('tools') or [])}",
        f"Domains: {', '.join(profile.get('domains') or [])}",
        f"Responsibilities: {', '.join(profile.get('responsibilities') or [])}",
        f"Requirements: {', '.join(profile.get('requirements') or [])}",
        f"Red flags: {', '.join(profile.get('red_flags') or [])}",
        f"Matching keywords: {', '.join(profile.get('matching_keywords') or [])}",
    ]
    return "\n".join(parts)


def build_vacancy_vector_payload(
    profile: dict[str, Any], *, vacancy_id: int, source_url: str, title: str, company: str | None
) -> dict[str, Any]:
    return {
        "type": "vacancy_profile",
        "vacancy_id": vacancy_id,
        "source_url": source_url,
        "title": title,
        "company": company,
        "is_vacancy": profile.get("is_vacancy", True),
        "vacancy_confidence": profile.get("vacancy_confidence", 1.0),
        "rejection_reason": profile.get("rejection_reason"),
        "role": profile.get("role"),
        "seniority": profile.get("seniority"),
        "employment_type": profile.get("employment_type"),
        "location": profile.get("location"),
        "remote_policy": profile.get("remote_policy"),
        "must_have_skills": profile.get("must_have_skills") or [],
        "tools": profile.get("tools") or [],
        "domains": profile.get("domains") or [],
        "matching_keywords": profile.get("matching_keywords") or [],
        "summary": profile.get("summary") or "",
        "role_family": profile.get("role_family"),
        "role_is_technical": profile.get("role_is_technical"),
        "esco_occupation_uri": profile.get("esco_occupation_uri"),
    }


def persist_vacancy_profile(
    db: Session,
    *,
    vacancy_id: int,
    source_url: str,
    title: str,
    company: str | None,
    profile: dict[str, Any],
) -> None:
    canonical_text = build_vacancy_profile_text(profile, title=title, company=company)
    vector = create_embedding(canonical_text)
    payload = build_vacancy_vector_payload(
        profile,
        vacancy_id=vacancy_id,
        source_url=source_url,
        title=title,
        company=company,
    )
    collection_name, point_id = get_vector_store().upsert_vacancy_profile(
        vacancy_id=vacancy_id,
        vector=vector,
        payload=payload,
    )
    create_or_update_vacancy_profile(
        db,
        vacancy_id=vacancy_id,
        profile=profile,
        canonical_text=canonical_text,
        qdrant_collection=collection_name,
        qdrant_point_id=point_id,
    )
