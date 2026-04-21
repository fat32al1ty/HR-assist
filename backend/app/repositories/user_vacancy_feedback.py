from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_vacancy_feedback import UserVacancyFeedback
from app.models.vacancy import Vacancy


def set_vacancy_disliked(
    db: Session,
    *,
    user_id: int,
    vacancy_id: int,
    disliked: bool = True,
) -> UserVacancyFeedback:
    feedback = db.scalar(
        select(UserVacancyFeedback).where(
            UserVacancyFeedback.user_id == user_id,
            UserVacancyFeedback.vacancy_id == vacancy_id,
        )
    )
    if feedback is None:
        feedback = UserVacancyFeedback(
            user_id=user_id,
            vacancy_id=vacancy_id,
            disliked=disliked,
        )
    else:
        feedback.disliked = disliked
    if disliked:
        feedback.liked = False

    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def set_vacancy_liked(
    db: Session,
    *,
    user_id: int,
    vacancy_id: int,
    liked: bool = True,
) -> UserVacancyFeedback:
    feedback = db.scalar(
        select(UserVacancyFeedback).where(
            UserVacancyFeedback.user_id == user_id,
            UserVacancyFeedback.vacancy_id == vacancy_id,
        )
    )
    if feedback is None:
        feedback = UserVacancyFeedback(
            user_id=user_id,
            vacancy_id=vacancy_id,
            disliked=False,
            liked=liked,
        )
    else:
        feedback.liked = liked
        if liked:
            feedback.disliked = False

    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def list_disliked_vacancy_ids(
    db: Session,
    *,
    user_id: int,
) -> set[int]:
    rows = db.scalars(
        select(UserVacancyFeedback.vacancy_id).where(
            UserVacancyFeedback.user_id == user_id,
            UserVacancyFeedback.disliked.is_(True),
        )
    ).all()
    return {int(row) for row in rows}


def list_liked_vacancy_ids(
    db: Session,
    *,
    user_id: int,
) -> set[int]:
    rows = db.scalars(
        select(UserVacancyFeedback.vacancy_id).where(
            UserVacancyFeedback.user_id == user_id,
            UserVacancyFeedback.liked.is_(True),
        )
    ).all()
    return {int(row) for row in rows}


def list_liked_vacancy_feedback_ages(
    db: Session,
    *,
    user_id: int,
) -> list[tuple[int, datetime]]:
    rows = db.execute(
        select(UserVacancyFeedback.vacancy_id, UserVacancyFeedback.updated_at).where(
            UserVacancyFeedback.user_id == user_id,
            UserVacancyFeedback.liked.is_(True),
        )
    ).all()
    return [(int(row[0]), row[1]) for row in rows]


def list_disliked_vacancy_feedback_ages(
    db: Session,
    *,
    user_id: int,
) -> list[tuple[int, datetime]]:
    rows = db.execute(
        select(UserVacancyFeedback.vacancy_id, UserVacancyFeedback.updated_at).where(
            UserVacancyFeedback.user_id == user_id,
            UserVacancyFeedback.disliked.is_(True),
        )
    ).all()
    return [(int(row[0]), row[1]) for row in rows]


def list_liked_vacancies(
    db: Session,
    *,
    user_id: int,
    limit: int = 100,
) -> list[Vacancy]:
    stmt = (
        select(Vacancy)
        .join(UserVacancyFeedback, UserVacancyFeedback.vacancy_id == Vacancy.id)
        .where(
            UserVacancyFeedback.user_id == user_id,
            UserVacancyFeedback.liked.is_(True),
        )
        .order_by(UserVacancyFeedback.updated_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def list_disliked_vacancies(
    db: Session,
    *,
    user_id: int,
    limit: int = 100,
) -> list[Vacancy]:
    stmt = (
        select(Vacancy)
        .join(UserVacancyFeedback, UserVacancyFeedback.vacancy_id == Vacancy.id)
        .where(
            UserVacancyFeedback.user_id == user_id,
            UserVacancyFeedback.disliked.is_(True),
        )
        .order_by(UserVacancyFeedback.updated_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
