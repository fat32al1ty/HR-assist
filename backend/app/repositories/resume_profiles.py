from sqlalchemy.orm import Session

from app.models.resume_profile import ResumeProfile


def create_or_update_resume_profile(
    db: Session,
    *,
    resume_id: int,
    user_id: int,
    profile: dict,
    canonical_text: str,
    qdrant_collection: str,
    qdrant_point_id: str,
) -> ResumeProfile:
    resume_profile = (
        db.query(ResumeProfile).filter(ResumeProfile.resume_id == resume_id).one_or_none()
    )
    if resume_profile is None:
        resume_profile = ResumeProfile(
            resume_id=resume_id,
            user_id=user_id,
            profile=profile,
            canonical_text=canonical_text,
            qdrant_collection=qdrant_collection,
            qdrant_point_id=qdrant_point_id,
        )
    else:
        resume_profile.profile = profile
        resume_profile.canonical_text = canonical_text
        resume_profile.qdrant_collection = qdrant_collection
        resume_profile.qdrant_point_id = qdrant_point_id

    db.add(resume_profile)
    db.commit()
    db.refresh(resume_profile)
    return resume_profile
