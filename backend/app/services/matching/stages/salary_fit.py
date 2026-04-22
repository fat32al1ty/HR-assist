"""Salary-fit stage — match vacancy salary against user expectation.

Phase 2.7. Reads the stated-salary columns on ``vacancy_profiles``
(populated by the backfill or the analyser) plus the predicted band if
present, then annotates each candidate with

- ``salary_min`` / ``salary_max`` / ``salary_currency`` (what the card
  will display),
- ``salary_source`` — ``stated`` when we have real numbers,
  ``predicted`` when the model filled them in, else absent,
- ``salary_fit`` — one of ``match`` / ``below`` / ``above`` /
  ``unknown``.

A soft penalty is applied to ``hybrid_score`` when ``fit == 'below'``
or ``above``: we never hard-drop, the user may be undervaluing
themselves or intentionally looking at a higher band.

The stage slots in after ``LLMRerankStage`` so the money gap can
re-shuffle the top slots without wasting a rerank call on cards we
were going to penalise anyway. It ignores candidates with no
expectation configured (``salary_fit = unknown``, zero penalty).
"""

from __future__ import annotations

from app.services.salary_extract import classify_fit

from ..state import MatchingState
from .base import BaseStage


class SalaryFitStage(BaseStage):
    name = "salary_fit"

    def run(self, state: MatchingState) -> MatchingState:
        prefs = state.resume_context.preferences or {}
        expected_min = _int_or_none(prefs.get("expected_salary_min"))
        expected_max = _int_or_none(prefs.get("expected_salary_max"))
        expected_currency = (prefs.get("expected_salary_currency") or "RUB").upper()

        adjusted = 0
        for cand in state.candidates:
            profile = cand.vacancy.profile if hasattr(cand.vacancy, "profile") else None
            if profile is None:
                continue
            stated_min = getattr(profile, "salary_min", None)
            stated_max = getattr(profile, "salary_max", None)
            currency = getattr(profile, "salary_currency", None)
            source = "stated"

            if stated_min is None and stated_max is None:
                predicted_p50 = getattr(profile, "predicted_salary_p50", None)
                if predicted_p50 is not None:
                    stated_min = getattr(profile, "predicted_salary_p25", None) or predicted_p50
                    stated_max = getattr(profile, "predicted_salary_p75", None) or predicted_p50
                    currency = currency or "RUB"
                    source = "predicted"

            mid = _midpoint(stated_min, stated_max)
            fit, penalty = classify_fit(
                mid,
                expected_min=expected_min,
                expected_max=expected_max,
                currency=currency,
                expected_currency=expected_currency,
            )

            if stated_min is not None or stated_max is not None:
                cand.annotations["salary_min"] = stated_min
                cand.annotations["salary_max"] = stated_max
                cand.annotations["salary_currency"] = currency
                cand.annotations["salary_source"] = source
            cand.annotations["salary_fit"] = fit
            if penalty > 0:
                cand.hybrid_score = max(0.0, cand.hybrid_score - penalty)
                adjusted += 1

        if adjusted:
            state.diagnostics.custom["salary_fit_penalty_applied"] = (
                state.diagnostics.custom.get("salary_fit_penalty_applied", 0) + adjusted
            )
        return state


def _int_or_none(value) -> int | None:
    if value is None:
        return None
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return None
    return ivalue if ivalue > 0 else None


def _midpoint(low: int | None, high: int | None) -> int | None:
    if low is not None and high is not None:
        return (low + high) // 2
    return low or high
