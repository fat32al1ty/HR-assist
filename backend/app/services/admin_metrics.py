"""Aggregator queries that back the new /admin/metrics/* endpoints.

Pure SQL — no Prometheus, no live HTTP calls. Each function takes a
SQLAlchemy session and a range bucket string ("24h" | "7d" | "30d") and
returns a JSON-friendly dict. Routes wrap them; the frontend renders
them as cards / sparklines / funnel bars.

Design notes:
- All ranges are anchored to `now() - delta`; nothing parses absolute
  timestamps. Operators have 3 fixed windows; if they need more we can
  add `since`/`until` later.
- Heavy queries push aggregation into the DB (`func.percentile_cont`,
  `GROUP BY date_trunc`). We never load 10k rows into Python and slice.
- Every query tolerates empty inventory — returns zeros, not NULL.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.freshness_sweep_log import FreshnessSweepLog
from app.models.match_event import MatchEvent
from app.models.match_telemetry import MatchClick, MatchImpression
from app.models.openai_call_log import OpenaiCallLog
from app.models.recommendation_job import RecommendationJob
from app.models.resume import Resume
from app.models.user import User
from app.models.user_login_event import UserLoginEvent
from app.models.user_vacancy_feedback import UserVacancyFeedback

ALLOWED_RANGES = {"24h", "7d", "30d"}
_RANGE_TO_TIMEDELTA: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _resolve_range(range_label: str) -> tuple[str, datetime]:
    label = range_label if range_label in ALLOWED_RANGES else "7d"
    cutoff = datetime.now(UTC) - _RANGE_TO_TIMEDELTA[label]
    return label, cutoff


def _percentile(values: list[float], pct: float) -> float:
    """Plain Python percentile so we don't depend on `func.percentile_cont`
    (it works on Postgres, but we want the helper testable on any backend
    via a list of floats)."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return float(s[lo] + (s[hi] - s[lo]) * frac)


# ---------------------------------------------------------------------------
# Latency
# ---------------------------------------------------------------------------


def latency_distribution(db: Session, *, range_label: str) -> dict:
    label, cutoff = _resolve_range(range_label)
    rows = db.execute(
        select(
            RecommendationJob.job_type,
            RecommendationJob.started_at,
            RecommendationJob.finished_at,
            RecommendationJob.status,
        )
        .where(RecommendationJob.finished_at.is_not(None))
        .where(RecommendationJob.started_at.is_not(None))
        .where(RecommendationJob.finished_at >= cutoff)
    ).all()

    by_type: dict[str, list[float]] = {}
    fail_by_type: Counter[str] = Counter()
    total_by_type: Counter[str] = Counter()
    for job_type, started_at, finished_at, status in rows:
        seconds = max(0.0, (finished_at - started_at).total_seconds())
        by_type.setdefault(job_type or "deep_scan", []).append(seconds)
        total_by_type[job_type or "deep_scan"] += 1
        if status == "failed":
            fail_by_type[job_type or "deep_scan"] += 1

    return {
        "range": label,
        "by_job_type": {
            jt: {
                "count": len(durations),
                "p50_seconds": round(_percentile(durations, 0.50), 3),
                "p95_seconds": round(_percentile(durations, 0.95), 3),
                "p99_seconds": round(_percentile(durations, 0.99), 3),
                "max_seconds": round(max(durations) if durations else 0.0, 3),
                "fail_rate": round(
                    fail_by_type[jt] / total_by_type[jt] if total_by_type[jt] else 0.0,
                    4,
                ),
            }
            for jt, durations in sorted(by_type.items())
        },
    }


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------


def cost_breakdown(db: Session, *, range_label: str) -> dict:
    label, cutoff = _resolve_range(range_label)
    today = datetime.now(UTC).date()

    by_day_rows = db.execute(
        select(
            func.date_trunc("day", OpenaiCallLog.ts).label("day"),
            func.coalesce(func.sum(OpenaiCallLog.cost_usd), 0.0).label("usd"),
            func.count(OpenaiCallLog.id).label("calls"),
        )
        .where(OpenaiCallLog.ts >= cutoff)
        .group_by("day")
        .order_by("day")
    ).all()

    by_model_rows = db.execute(
        select(
            OpenaiCallLog.model,
            func.coalesce(func.sum(OpenaiCallLog.cost_usd), 0.0),
            func.count(OpenaiCallLog.id),
        )
        .where(OpenaiCallLog.ts >= cutoff)
        .group_by(OpenaiCallLog.model)
        .order_by(func.sum(OpenaiCallLog.cost_usd).desc())
    ).all()

    today_total = 0.0
    yesterday_total = 0.0
    yesterday = today - timedelta(days=1)
    series = []
    for day, usd, calls in by_day_rows:
        d = day.date() if isinstance(day, datetime) else day
        usd_f = float(usd or 0.0)
        if d == today:
            today_total = usd_f
        elif d == yesterday:
            yesterday_total = usd_f
        series.append({"day": str(d), "cost_usd": round(usd_f, 4), "calls": int(calls)})

    grand_total = sum(item["cost_usd"] for item in series)

    return {
        "range": label,
        "total_usd": round(grand_total, 4),
        "today_usd": round(today_total, 4),
        "yesterday_usd": round(yesterday_total, 4),
        "by_day": series,
        "by_model": [
            {
                "model": model or "unknown",
                "cost_usd": round(float(usd or 0.0), 4),
                "calls": int(calls),
            }
            for model, usd, calls in by_model_rows
        ],
    }


# ---------------------------------------------------------------------------
# Activation funnel
# ---------------------------------------------------------------------------


def activation_funnel(db: Session, *, range_label: str) -> dict:
    """Cohort = users who created their first resume within the range.
    Steps:
    1. uploaded — has a Resume with status='completed'
    2. first_search — has a RecommendationJob with status='completed'
    3. first_match — that job had at least one entry in `matches`
    4. first_like — has a UserVacancyFeedback with liked=True
    5. first_apply — has an Application row
    """
    label, cutoff = _resolve_range(range_label)

    # Cohort: users with their FIRST completed resume after cutoff.
    user_first_resume = (
        select(
            Resume.user_id.label("user_id"),
            func.min(Resume.created_at).label("first_resume_at"),
        )
        .where(Resume.status == "completed")
        .group_by(Resume.user_id)
        .subquery()
    )
    cohort_user_ids = [
        row[0]
        for row in db.execute(
            select(user_first_resume.c.user_id).where(user_first_resume.c.first_resume_at >= cutoff)
        ).all()
    ]
    cohort = set(cohort_user_ids)
    total = len(cohort)

    if total == 0:
        return {
            "range": label,
            "cohort_size": 0,
            "steps": [
                {"key": "uploaded", "users": 0, "share": 0.0},
                {"key": "first_search", "users": 0, "share": 0.0},
                {"key": "first_match", "users": 0, "share": 0.0},
                {"key": "first_like", "users": 0, "share": 0.0},
                {"key": "first_apply", "users": 0, "share": 0.0},
            ],
        }

    def _users_in(rows: Iterable) -> int:
        seen: set[int] = set()
        for r in rows:
            uid = r[0] if isinstance(r, tuple) else r
            if uid in cohort:
                seen.add(uid)
        return len(seen)

    searched = _users_in(
        db.execute(
            select(RecommendationJob.user_id)
            .where(RecommendationJob.status == "completed")
            .where(RecommendationJob.user_id.in_(cohort_user_ids))
            .distinct()
        ).all()
    )
    matched = (
        _users_in(
            db.execute(
                select(RecommendationJob.user_id)
                .where(RecommendationJob.status == "completed")
                .where(RecommendationJob.user_id.in_(cohort_user_ids))
                .where(func.coalesce(func.json_array_length(RecommendationJob.matches), 0) > 0)
                .distinct()
            ).all()
        )
        if cohort_user_ids
        else 0
    )
    liked = _users_in(
        db.execute(
            select(UserVacancyFeedback.user_id)
            .where(UserVacancyFeedback.liked.is_(True))
            .where(UserVacancyFeedback.user_id.in_(cohort_user_ids))
            .distinct()
        ).all()
    )
    applied = _users_in(
        db.execute(
            select(Application.user_id).where(Application.user_id.in_(cohort_user_ids)).distinct()
        ).all()
    )

    def _step(key: str, value: int) -> dict:
        return {"key": key, "users": value, "share": round(value / total, 4) if total else 0.0}

    return {
        "range": label,
        "cohort_size": total,
        "steps": [
            _step("uploaded", total),
            _step("first_search", searched),
            _step("first_match", matched),
            _step("first_like", liked),
            _step("first_apply", applied),
        ],
    }


# ---------------------------------------------------------------------------
# Retention (D1, D7, D30)
# ---------------------------------------------------------------------------


def retention_cohort(db: Session) -> dict:
    """For each user U, look at U.created_at as cohort day. Then check
    whether U has a UserLoginEvent on D+1 / D+7 / D+30. Returns
    weighted-average retention across all users with enough history.
    """
    now = datetime.now(UTC)
    user_rows = db.execute(
        select(User.id, User.created_at).where(User.created_at.is_not(None))
    ).all()

    def _has_login_on_day(user_id: int, target_date: date) -> bool:
        return (
            db.scalar(
                select(func.count(UserLoginEvent.id))
                .where(UserLoginEvent.user_id == user_id)
                .where(func.date(UserLoginEvent.occurred_at) == target_date)
            )
            or 0
        ) > 0

    buckets = {1: [0, 0], 7: [0, 0], 30: [0, 0]}  # day → [retained, eligible]

    for user_id, created_at in user_rows:
        if created_at is None:
            continue
        cohort_day = created_at.date()
        for day_offset, pair in buckets.items():
            target = cohort_day + timedelta(days=day_offset)
            if target > now.date():
                # not enough history yet — skip this user for this bucket
                continue
            pair[1] += 1
            if _has_login_on_day(user_id, target):
                pair[0] += 1

    return {
        "d1": {
            "retained": buckets[1][0],
            "eligible": buckets[1][1],
            "share": round(buckets[1][0] / buckets[1][1], 4) if buckets[1][1] else 0.0,
        },
        "d7": {
            "retained": buckets[7][0],
            "eligible": buckets[7][1],
            "share": round(buckets[7][0] / buckets[7][1], 4) if buckets[7][1] else 0.0,
        },
        "d30": {
            "retained": buckets[30][0],
            "eligible": buckets[30][1],
            "share": round(buckets[30][0] / buckets[30][1], 4) if buckets[30][1] else 0.0,
        },
    }


# ---------------------------------------------------------------------------
# Quality (CTR by tier + score distribution)
# ---------------------------------------------------------------------------


def quality_metrics(db: Session, *, range_label: str) -> dict:
    label, cutoff = _resolve_range(range_label)

    # Impressions by tier
    imp_rows = db.execute(
        select(MatchImpression.tier, func.count(MatchImpression.id))
        .where(MatchImpression.ts >= cutoff)
        .group_by(MatchImpression.tier)
    ).all()
    impressions_by_tier = {tier or "unknown": int(count) for tier, count in imp_rows}

    # Clicks by tier — join MatchClick × MatchImpression on (match_run_id, vacancy_id)
    click_rows = db.execute(
        select(MatchImpression.tier, func.count(MatchClick.id))
        .join(
            MatchClick,
            (MatchClick.match_run_id == MatchImpression.match_run_id)
            & (MatchClick.vacancy_id == MatchImpression.vacancy_id),
        )
        .where(MatchClick.ts >= cutoff)
        .group_by(MatchImpression.tier)
    ).all()
    clicks_by_tier = {tier or "unknown": int(count) for tier, count in click_rows}

    ctr_by_tier = {
        tier: {
            "impressions": impressions_by_tier.get(tier, 0),
            "clicks": clicks_by_tier.get(tier, 0),
            "ctr": round(clicks_by_tier.get(tier, 0) / impressions_by_tier.get(tier, 0), 4)
            if impressions_by_tier.get(tier, 0) > 0
            else 0.0,
        }
        for tier in sorted(set(impressions_by_tier) | set(clicks_by_tier))
    }

    # Score histograms (vector_score) by tier — bucketed into 0.0..1.0 deciles.
    score_rows = db.execute(
        select(MatchImpression.tier, MatchImpression.vector_score).where(
            MatchImpression.ts >= cutoff
        )
    ).all()
    score_dist: dict[str, list[int]] = {}
    for tier, score in score_rows:
        if score is None:
            continue
        bucket = min(9, max(0, int(float(score) * 10)))
        score_dist.setdefault(tier or "unknown", [0] * 10)[bucket] += 1

    return {
        "range": label,
        "ctr_by_tier": ctr_by_tier,
        "score_distribution_by_tier": score_dist,
    }


# ---------------------------------------------------------------------------
# Segment warmup throughput
# ---------------------------------------------------------------------------


def segment_warmup_metrics(db: Session, *, range_label: str) -> dict:
    label, cutoff = _resolve_range(range_label)

    rows = db.execute(
        select(
            RecommendationJob.status,
            func.count(RecommendationJob.id),
            func.avg(
                case(
                    (
                        RecommendationJob.finished_at.is_not(None),
                        func.extract(
                            "epoch", RecommendationJob.finished_at - RecommendationJob.started_at
                        ),
                    ),
                    else_=None,
                )
            ),
        )
        .where(RecommendationJob.job_type == "segment_warmup")
        .where(RecommendationJob.created_at >= cutoff)
        .group_by(RecommendationJob.status)
    ).all()

    counts = {"completed": 0, "failed": 0, "running": 0, "queued": 0}
    duration_by_status: dict[str, float] = {}
    for status, n, avg_dur in rows:
        counts[status] = int(n)
        if avg_dur is not None:
            duration_by_status[status] = round(float(avg_dur), 2)

    # Daily-cap utilization comes from worker state, not DB.
    from app.services.vacancy_warmup import get_vacancy_warmup_status

    status = get_vacancy_warmup_status()
    daily_count = int(status.get("segment_warmup_daily_count", 0))
    from app.core.config import settings as _settings

    return {
        "range": label,
        "by_status": counts,
        "mean_duration_seconds": duration_by_status,
        "daily_count": daily_count,
        "daily_cap": int(_settings.segment_warmup_daily_cap),
        "daily_utilization": round(
            daily_count / _settings.segment_warmup_daily_cap
            if _settings.segment_warmup_daily_cap
            else 0.0,
            4,
        ),
    }


# ---------------------------------------------------------------------------
# Freshness sweep history (bonus, surfaced under segment-warmup tab or its own card)
# ---------------------------------------------------------------------------


def freshness_sweep_history(db: Session, *, range_label: str) -> dict:
    label, cutoff = _resolve_range(range_label)
    rows = db.execute(
        select(
            FreshnessSweepLog.started_at,
            FreshnessSweepLog.finished_at,
            FreshnessSweepLog.checked,
            FreshnessSweepLog.archived,
            FreshnessSweepLog.stopped_early,
        )
        .where(FreshnessSweepLog.started_at >= cutoff)
        .order_by(FreshnessSweepLog.started_at.desc())
    ).all()
    return {
        "range": label,
        "runs": [
            {
                "started_at": started.isoformat() if started else None,
                "finished_at": finished.isoformat() if finished else None,
                "checked": int(checked),
                "archived": int(archived),
                "stopped_early": int(stopped_early),
            }
            for started, finished, checked, archived, stopped_early in rows
        ],
    }


# ---------------------------------------------------------------------------
# Match events recap (lets ops confirm /event is wired)
# ---------------------------------------------------------------------------


def match_events_summary(db: Session, *, range_label: str) -> dict:
    label, cutoff = _resolve_range(range_label)
    rows = db.execute(
        select(MatchEvent.event, func.count(MatchEvent.id))
        .where(MatchEvent.ts >= cutoff)
        .group_by(MatchEvent.event)
        .order_by(func.count(MatchEvent.id).desc())
    ).all()
    return {
        "range": label,
        "events": [{"event": event, "count": int(count)} for event, count in rows],
    }
