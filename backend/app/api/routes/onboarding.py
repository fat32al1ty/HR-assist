from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.resumes import get_resume_for_user
from app.schemas.onboarding import OnboardingAnswerIn, OnboardingQuestionOut
from app.services.onboarding_questions import (
    list_answers,
    select_questions_for_resume,
    upsert_answer,
)

router = APIRouter()


@router.get("/{resume_id}/onboarding/questions", response_model=list[OnboardingQuestionOut])
def get_onboarding_questions(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OnboardingQuestionOut]:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    return select_questions_for_resume(db, resume_id)


@router.post("/{resume_id}/onboarding/answer", status_code=status.HTTP_204_NO_CONTENT)
def post_onboarding_answer(
    resume_id: int,
    payload: OnboardingAnswerIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    # Store answer_value as-is (JSON-encoded for complex types)
    upsert_answer(db, resume_id, payload.question_id, payload.answer_value)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{resume_id}/onboarding/answers")
def get_onboarding_answers(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    resume = get_resume_for_user(db, resume_id=resume_id, user_id=current_user.id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    rows = list_answers(db, resume_id)
    return [
        {
            "question_id": r.question_id,
            "answer_value": r.answer_value,
            "answered_at": r.answered_at.isoformat(),
        }
        for r in rows
    ]
