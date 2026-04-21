from typing import Any

from sqlalchemy.orm import Session

from app.repositories.resume_profiles import create_or_update_resume_profile
from app.services.embeddings import create_embedding
from app.services.vector_store import get_vector_store


def build_resume_profile_text(profile: dict[str, Any]) -> str:
    parts = [
        f"Candidate: {profile.get('candidate_name') or 'unknown'}",
        f"Target role: {profile.get('target_role') or 'unknown'}",
        f"Specialization: {profile.get('specialization') or 'unknown'}",
        f"Seniority: {profile.get('seniority') or 'unknown'}",
        f"Total experience years: {profile.get('total_experience_years') or 'unknown'}",
        f"Summary: {profile.get('summary') or ''}",
        f"Hard skills: {', '.join(profile.get('hard_skills') or profile.get('skills') or [])}",
        f"Soft skills: {', '.join(profile.get('soft_skills') or [])}",
        f"Tools: {', '.join(profile.get('tools') or [])}",
        f"Domains: {', '.join(profile.get('domains') or [])}",
        f"Languages: {', '.join(profile.get('languages') or [])}",
        f"Strengths: {', '.join(profile.get('strengths') or [])}",
        f"Weaknesses: {', '.join(profile.get('weaknesses') or [])}",
        f"Risk flags: {', '.join(profile.get('risk_flags') or [])}",
        f"Matching keywords: {', '.join(profile.get('matching_keywords') or [])}",
    ]
    return "\n".join(parts)


def build_resume_vector_payload(profile: dict[str, Any], *, canonical_text: str) -> dict[str, Any]:
    return {
        "type": "resume_profile",
        "candidate_name": profile.get("candidate_name"),
        "target_role": profile.get("target_role"),
        "specialization": profile.get("specialization"),
        "seniority": profile.get("seniority"),
        "seniority_confidence": profile.get("seniority_confidence"),
        "total_experience_years": profile.get("total_experience_years"),
        "hard_skills": profile.get("hard_skills") or profile.get("skills") or [],
        "tools": profile.get("tools") or [],
        "domains": profile.get("domains") or [],
        "languages": profile.get("languages") or [],
        "matching_keywords": profile.get("matching_keywords") or [],
        "canonical_text": canonical_text,
    }


def persist_resume_profile(
    db: Session, *, resume_id: int, user_id: int, profile: dict[str, Any]
) -> None:
    canonical_text = build_resume_profile_text(profile)
    vector = create_embedding(canonical_text)
    payload = build_resume_vector_payload(profile, canonical_text=canonical_text)
    collection_name, point_id = get_vector_store().upsert_resume_profile(
        resume_id=resume_id,
        user_id=user_id,
        vector=vector,
        payload=payload,
    )
    create_or_update_resume_profile(
        db,
        resume_id=resume_id,
        user_id=user_id,
        profile=profile,
        canonical_text=canonical_text,
        qdrant_collection=collection_name,
        qdrant_point_id=point_id,
    )


def delete_resume_profile_vector(*, resume_id: int) -> None:
    get_vector_store().delete_resume_profile(resume_id=resume_id)
