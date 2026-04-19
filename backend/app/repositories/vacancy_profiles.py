from sqlalchemy.orm import Session

from app.models.vacancy_profile import VacancyProfile


def create_or_update_vacancy_profile(
    db: Session,
    *,
    vacancy_id: int,
    profile: dict,
    canonical_text: str,
    qdrant_collection: str,
    qdrant_point_id: str,
) -> VacancyProfile:
    vacancy_profile = db.query(VacancyProfile).filter(VacancyProfile.vacancy_id == vacancy_id).one_or_none()
    if vacancy_profile is None:
        vacancy_profile = VacancyProfile(
            vacancy_id=vacancy_id,
            profile=profile,
            canonical_text=canonical_text,
            qdrant_collection=qdrant_collection,
            qdrant_point_id=qdrant_point_id,
        )
    else:
        vacancy_profile.profile = profile
        vacancy_profile.canonical_text = canonical_text
        vacancy_profile.qdrant_collection = qdrant_collection
        vacancy_profile.qdrant_point_id = qdrant_point_id

    db.add(vacancy_profile)
    db.commit()
    db.refresh(vacancy_profile)
    return vacancy_profile
