from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.resume_profile import ResumeProfile
from app.models.user import User
from app.repositories.resumes import get_resume_for_user
from app.schemas.track_gap import TrackGapAnalysisOut, TrackGapBlock, TrackGapItem
from app.services import track_gap_analysis

router = APIRouter()


@router.get("/resumes/{resume_id}/track-gaps", response_model=TrackGapAnalysisOut)
def get_track_gaps(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackGapAnalysisOut:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    resume_profile = (
        db.query(ResumeProfile).filter(ResumeProfile.resume_id == resume_id).one_or_none()
    )
    profile_json: dict = (
        resume_profile.profile
        if resume_profile and isinstance(resume_profile.profile, dict)
        else {}
    )
    skills_list: list = profile_json.get("skills") or []
    hard_skills_list: list = profile_json.get("hard_skills") or []
    resume_skills: set[str] = {s for s in (skills_list + hard_skills_list) if isinstance(s, str)}

    result = track_gap_analysis.compute_for_resume(
        db, resume_id=resume_id, resume_skills=resume_skills
    )

    def _to_block(track: str) -> TrackGapBlock:
        r = result[track]
        return TrackGapBlock(
            track=track,
            vacancies_count=r.vacancies_count,
            top_gaps=[
                TrackGapItem(
                    skill=g.skill,
                    fraction=g.fraction,
                    vacancies_with_gap_count=g.vacancies_with_gap_count,
                )
                for g in r.top_gaps
            ],
            softer_subset_count=r.softer_subset_count,
        )

    return TrackGapAnalysisOut(
        match=_to_block("match"),
        grow=_to_block("grow"),
        stretch=_to_block("stretch"),
    )
