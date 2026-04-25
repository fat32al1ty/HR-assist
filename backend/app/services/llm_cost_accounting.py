"""Shared helper: sum LLM spend for a user across all subsystems today."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def daily_user_llm_cost_usd(db: Session, user_id: int, today: datetime | None = None) -> float:
    """Return total LLM cost_usd across resume_audits + vacancy_strategies for *user_id* today.

    *today* must be a UTC-aware datetime representing midnight UTC of the day to
    query; defaults to the current UTC date at midnight.
    """
    from app.models.resume import Resume
    from app.models.resume_audit import ResumeAudit
    from app.models.vacancy_strategy import VacancyStrategy

    if today is None:
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    audit_cost = db.scalar(
        select(func.coalesce(func.sum(ResumeAudit.cost_usd), 0.0))
        .join(Resume, Resume.id == ResumeAudit.resume_id)
        .where(
            Resume.user_id == user_id,
            ResumeAudit.computed_at >= today,
        )
    )

    strategy_cost = db.scalar(
        select(func.coalesce(func.sum(VacancyStrategy.cost_usd), 0.0))
        .join(Resume, Resume.id == VacancyStrategy.resume_id)
        .where(
            Resume.user_id == user_id,
            VacancyStrategy.computed_at >= today,
        )
    )

    return float(audit_cost or 0.0) + float(strategy_cost or 0.0)
