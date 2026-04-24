"""Median-by-(role_family, seniority, city) baseline predictor.

Fallback when the LightGBM model has not been trained yet. Builds a
triple-keyed median table from stated RUB salaries on vacancy_profiles,
with progressively coarser fallbacks ((role, seniority) → (role,) → global).
Cached in-process for 1 hour.
"""

from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

BASELINE_REFRESH_TTL_SECONDS = 3600
MIN_BASELINE_SUPPORT = 5
MAX_BASELINE_CONFIDENCE = 0.6


@dataclass(frozen=True)
class BaselineBand:
    p25: int
    p50: int
    p75: int
    confidence: float
    support: int


class SalaryBaselineCache:
    def __init__(self) -> None:
        self._built_at: float = 0.0
        self._triple: dict[tuple[str, str, str], tuple[int, int, int, int]] = {}
        self._pair: dict[tuple[str, str], tuple[int, int, int, int]] = {}
        self._single: dict[tuple[str,], tuple[int, int, int, int]] = {}

    def _is_stale(self) -> bool:
        return (time.monotonic() - self._built_at) >= BASELINE_REFRESH_TTL_SECONDS

    def rebuild(self, db: Session) -> None:
        from app.models.vacancy_profile import VacancyProfile

        rows = db.execute(
            select(
                VacancyProfile.profile,
                VacancyProfile.salary_min,
                VacancyProfile.salary_max,
            ).where(
                VacancyProfile.salary_currency == "RUB",
                (VacancyProfile.salary_min.isnot(None)) | (VacancyProfile.salary_max.isnot(None)),
            )
        ).all()

        buckets_triple: dict[tuple[str, str, str], list[int]] = {}
        buckets_pair: dict[tuple[str, str], list[int]] = {}
        buckets_single: dict[tuple[str,], list[int]] = {}

        for profile_json, sal_min, sal_max in rows:
            mid = _midpoint(sal_min, sal_max)
            if mid is None or mid <= 0:
                continue
            role = _str_key(
                (profile_json or {}).get("role_family") if isinstance(profile_json, dict) else None
            )
            seniority = _str_key(
                (profile_json or {}).get("seniority") if isinstance(profile_json, dict) else None
            )
            city = _str_key(
                (profile_json or {}).get("location") if isinstance(profile_json, dict) else None
            )

            buckets_triple.setdefault((role, seniority, city), []).append(mid)
            buckets_pair.setdefault((role, seniority), []).append(mid)
            buckets_single.setdefault((role,), []).append(mid)

        self._triple = {
            k: _compute_band(v) for k, v in buckets_triple.items() if len(v) >= MIN_BASELINE_SUPPORT
        }
        self._pair = {
            k: _compute_band(v) for k, v in buckets_pair.items() if len(v) >= MIN_BASELINE_SUPPORT
        }
        self._single = {
            k: _compute_band(v) for k, v in buckets_single.items() if len(v) >= MIN_BASELINE_SUPPORT
        }
        self._built_at = time.monotonic()
        logger.info(
            "salary baseline rebuilt: triple=%d pair=%d single=%d",
            len(self._triple),
            len(self._pair),
            len(self._single),
        )

    def lookup(
        self,
        *,
        role_family: str | None,
        seniority: str | None,
        city: str | None,
        db: Session,
    ) -> BaselineBand | None:
        if self._is_stale():
            self.rebuild(db)

        role = _str_key(role_family)
        sen = _str_key(seniority)
        cit = _str_key(city)

        entry = self._triple.get((role, sen, cit))
        if entry is not None:
            return _to_band(entry)

        entry = self._pair.get((role, sen))
        if entry is not None:
            return _to_band(entry)

        entry = self._single.get((role,))
        if entry is not None:
            return _to_band(entry)

        return None


_cache = SalaryBaselineCache()


def get_baseline_band(
    *,
    role_family: str | None,
    seniority: str | None,
    city: str | None,
    db: Session,
) -> BaselineBand | None:
    """Return baseline band or None if no bucket has enough rows (MIN_BASELINE_SUPPORT=5).

    Drops from triple → pair → single key fallbacks.
    confidence = support/30 capped at MAX_BASELINE_CONFIDENCE (0.6).
    """
    return _cache.lookup(role_family=role_family, seniority=seniority, city=city, db=db)


def _str_key(value: str | None) -> str:
    return (value or "unknown").strip().lower()


def _midpoint(low: int | None, high: int | None) -> int | None:
    if low is not None and high is not None:
        return (low + high) // 2
    return low or high


def _compute_band(values: list[int]) -> tuple[int, int, int, int]:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    p25 = sorted_vals[max(0, int(n * 0.25))]
    p50 = sorted_vals[int(n * 0.50)] if n > 1 else sorted_vals[0]
    p75 = sorted_vals[min(n - 1, int(n * 0.75))]
    if n == 1:
        p50 = sorted_vals[0]
    else:
        p50 = int(statistics.median(sorted_vals))
    return p25, p50, p75, n


def _to_band(entry: tuple[int, int, int, int]) -> BaselineBand:
    p25, p50, p75, support = entry
    confidence = min(MAX_BASELINE_CONFIDENCE, support / 30.0)
    return BaselineBand(p25=p25, p50=p50, p75=p75, confidence=confidence, support=support)
