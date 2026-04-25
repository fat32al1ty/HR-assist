"""Aggregate skill gaps across vacancies grouped by track.

For each track (match/grow/stretch), look at the top N vacancies in
that track for the user's resume, count which must_have_skills appear
most frequently AND aren't in the user's resume. Return a per-track
list with fraction (% of vacancies in this track that require it).

Pure rule-based aggregation — no LLM. Cached in track_gap_analyses
table with TTL 24h.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.resume_vacancy_score import ResumeVacancyScore
from app.models.track_gap_analysis import TrackGapAnalysis
from app.models.vacancy_profile import VacancyProfile

Track = Literal["match", "grow", "stretch"]

GAP_ANALYSIS_TTL_HOURS = 24
TOP_N_VACANCIES_PER_TRACK = 50
TOP_N_GAPS_REPORTED = 5
SOFTER_GAP_THRESHOLD = 2  # vacancies with <=2 missing skills count as "softer subset"


@dataclass(frozen=True)
class TrackGap:
    skill: str
    fraction: float  # 0..1 — % of vacancies in this track that require it
    vacancies_with_gap_count: int


@dataclass(frozen=True)
class TrackGapResult:
    track: Track
    vacancies_count: int
    top_gaps: list[TrackGap]
    softer_subset_count: int


def compute_for_resume(
    db: Session,
    *,
    resume_id: int,
    resume_skills: set[str],
) -> dict[Track, TrackGapResult]:
    """Compute gap analysis for all 3 tracks. Read-through cache."""
    cached = db.query(TrackGapAnalysis).filter(TrackGapAnalysis.resume_id == resume_id).first()
    if cached and cached.computed_at >= datetime.now(UTC) - timedelta(hours=GAP_ANALYSIS_TTL_HOURS):
        return _from_cached(cached.analysis_json)

    # Recompute
    result: dict[Track, TrackGapResult] = {}
    for track in ("match", "grow", "stretch"):
        result[track] = _compute_one(
            db, resume_id=resume_id, resume_skills=resume_skills, track=track
        )

    # Persist
    if cached:
        cached.analysis_json = _to_json(result)
        cached.computed_at = datetime.now(UTC)
    else:
        db.add(
            TrackGapAnalysis(
                resume_id=resume_id,
                analysis_json=_to_json(result),
                computed_at=datetime.now(UTC),
            )
        )
    db.commit()
    return result


def _compute_one(
    db: Session,
    *,
    resume_id: int,
    resume_skills: set[str],
    track: Track,
) -> TrackGapResult:
    # Pull top N vacancies in this track from the score cache
    rows = db.execute(
        select(ResumeVacancyScore.vacancy_id)
        .where(ResumeVacancyScore.resume_id == resume_id)
        .where(ResumeVacancyScore.track == track)
        .order_by(ResumeVacancyScore.similarity_score.desc())
        .limit(TOP_N_VACANCIES_PER_TRACK)
    ).all()
    vacancy_ids = [r[0] for r in rows]
    if not vacancy_ids:
        return TrackGapResult(track=track, vacancies_count=0, top_gaps=[], softer_subset_count=0)

    # Pull their profiles
    vp_rows = db.execute(
        select(VacancyProfile.profile).where(VacancyProfile.vacancy_id.in_(vacancy_ids))
    ).all()

    user_lower = {s.lower().strip() for s in resume_skills if isinstance(s, str)}
    skill_counts: dict[str, int] = {}
    softer_subset = 0

    for (profile_json,) in vp_rows:
        if not isinstance(profile_json, dict):
            continue
        must = profile_json.get("must_have_skills") or []
        if not isinstance(must, list):
            continue
        missing_for_this_vp: set[str] = set()
        for s in must:
            if not isinstance(s, str):
                continue
            key = s.strip().lower()
            if not key or key in user_lower:
                continue
            missing_for_this_vp.add(key)
        for k in missing_for_this_vp:
            skill_counts[k] = skill_counts.get(k, 0) + 1
        if 0 < len(missing_for_this_vp) <= SOFTER_GAP_THRESHOLD:
            softer_subset += 1

    total = len(vp_rows)
    top = sorted(skill_counts.items(), key=lambda x: -x[1])[:TOP_N_GAPS_REPORTED]
    gaps = [
        TrackGap(skill=k, fraction=c / max(total, 1), vacancies_with_gap_count=c) for k, c in top
    ]
    return TrackGapResult(
        track=track,
        vacancies_count=total,
        top_gaps=gaps,
        softer_subset_count=softer_subset,
    )


def _to_json(result: dict[Track, TrackGapResult]) -> dict:
    return {
        track: {
            "vacancies_count": r.vacancies_count,
            "softer_subset_count": r.softer_subset_count,
            "top_gaps": [
                {
                    "skill": g.skill,
                    "fraction": g.fraction,
                    "vacancies_with_gap_count": g.vacancies_with_gap_count,
                }
                for g in r.top_gaps
            ],
        }
        for track, r in result.items()
    }


def _from_cached(blob: dict | None) -> dict[Track, TrackGapResult]:
    out: dict[Track, TrackGapResult] = {}
    if not isinstance(blob, dict):
        return {
            t: TrackGapResult(track=t, vacancies_count=0, top_gaps=[], softer_subset_count=0)
            for t in ("match", "grow", "stretch")
        }
    for track in ("match", "grow", "stretch"):
        v = blob.get(track) or {}
        gaps_raw = v.get("top_gaps") or []
        gaps = [
            TrackGap(
                skill=g["skill"],
                fraction=float(g.get("fraction", 0.0)),
                vacancies_with_gap_count=int(g.get("vacancies_with_gap_count", 0)),
            )
            for g in gaps_raw
            if isinstance(g, dict)
        ]
        out[track] = TrackGapResult(
            track=track,
            vacancies_count=int(v.get("vacancies_count", 0)),
            top_gaps=gaps,
            softer_subset_count=int(v.get("softer_subset_count", 0)),
        )
    return out
