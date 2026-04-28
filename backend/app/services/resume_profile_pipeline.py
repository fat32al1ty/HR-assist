import logging
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.resume_profiles import create_or_update_resume_profile
from app.repositories.resume_vacancy_score import delete_scores_for_resume
from app.services.embeddings import create_embedding
from app.services.resume_analyzer import all_resume_skills
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def build_resume_profile_text(profile: dict[str, Any]) -> str:
    parts = [
        f"Target role: {profile.get('target_role') or 'unknown'}",
        f"Specialization: {profile.get('specialization') or 'unknown'}",
        f"Seniority: {profile.get('seniority') or 'unknown'}",
        f"Total experience years: {profile.get('total_experience_years') or 'unknown'}",
        f"Summary: {profile.get('summary') or ''}",
        # all_resume_skills unions all buckets so the embedding captures every mentioned skill
        f"Hard skills: {', '.join(all_resume_skills(profile) or profile.get('skills') or [])}",
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
        "target_role": profile.get("target_role"),
        "specialization": profile.get("specialization"),
        "seniority": profile.get("seniority"),
        "seniority_confidence": profile.get("seniority_confidence"),
        "total_experience_years": profile.get("total_experience_years"),
        # all_resume_skills unions all buckets for vector payload; narrows on re-query are done by matchers
        "hard_skills": all_resume_skills(profile) or profile.get("skills") or [],
        "tools": profile.get("tools") or [],
        "domains": profile.get("domains") or [],
        "languages": profile.get("languages") or [],
        "matching_keywords": profile.get("matching_keywords") or [],
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
    deleted = delete_scores_for_resume(db, resume_id=resume_id)
    logger.info("Invalidated %d resume_vacancy_scores for resume %d", deleted, resume_id)


def delete_resume_profile_vector(*, resume_id: int) -> None:
    get_vector_store().delete_resume_profile(resume_id=resume_id)
