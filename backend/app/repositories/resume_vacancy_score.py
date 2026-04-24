from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.resume_vacancy_score import ResumeVacancyScore


def get_cached_scores(
    db: Session,
    *,
    resume_id: int,
    vacancy_ids: list[int],
    pipeline_version: str,
    ttl_days: int,
) -> dict[int, ResumeVacancyScore]:
    """Return map vacancy_id -> cached score, only entries newer than ttl_days."""
    if not vacancy_ids:
        return {}
    threshold = datetime.now(UTC) - timedelta(days=ttl_days)
    rows = db.scalars(
        select(ResumeVacancyScore).where(
            ResumeVacancyScore.resume_id == resume_id,
            ResumeVacancyScore.vacancy_id.in_(vacancy_ids),
            ResumeVacancyScore.pipeline_version == pipeline_version,
            ResumeVacancyScore.computed_at >= threshold,
        )
    ).all()
    return {r.vacancy_id: r for r in rows}


def upsert_scores(
    db: Session,
    *,
    resume_id: int,
    pipeline_version: str,
    scores: list[dict],
) -> None:
    """Postgres INSERT ... ON CONFLICT DO UPDATE for each scored pair.

    ``scores`` is a list of dicts with keys:
      - vacancy_id (int, required)
      - similarity_score (float, required)
      - vector_score (float, optional)
      - scores_json (dict, optional)
    """
    if not scores:
        return
    now = datetime.now(UTC)
    rows = [
        {
            "resume_id": resume_id,
            "vacancy_id": s["vacancy_id"],
            "pipeline_version": pipeline_version,
            "similarity_score": s["similarity_score"],
            "vector_score": s.get("vector_score"),
            "scores_json": s.get("scores_json"),
            "computed_at": now,
        }
        for s in scores
    ]
    stmt = insert(ResumeVacancyScore).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_rvs_resume_vacancy_pipeline",
        set_={
            "similarity_score": stmt.excluded.similarity_score,
            "vector_score": stmt.excluded.vector_score,
            "scores_json": stmt.excluded.scores_json,
            "computed_at": stmt.excluded.computed_at,
        },
    )
    db.execute(stmt)
    db.commit()


def delete_scores_for_resume(db: Session, *, resume_id: int) -> int:
    """Called on resume re-analysis. Return rows deleted."""
    result = db.execute(delete(ResumeVacancyScore).where(ResumeVacancyScore.resume_id == resume_id))
    db.commit()
    return result.rowcount
