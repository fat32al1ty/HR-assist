"""Wire salary prediction into the vacancy indexing pipeline."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.vacancy import Vacancy
from app.models.vacancy_profile import VacancyProfile
from app.services import salary_baseline, salary_predictor

logger = logging.getLogger(__name__)


def populate_predicted_salary(db: Session, *, profile: VacancyProfile, vacancy: Vacancy) -> None:
    if profile.salary_min or profile.salary_max:
        return

    profile_json = profile.profile if isinstance(profile.profile, dict) else {}
    role_family = profile_json.get("role_family")
    seniority = profile_json.get("seniority")
    city = vacancy.location

    band = salary_predictor.predict(role_family=role_family, seniority=seniority, city=city)

    if band is None and settings.feature_salary_baseline_enabled:
        baseline = salary_baseline.get_baseline_band(
            role_family=role_family, seniority=seniority, city=city, db=db
        )
        if baseline is not None:
            band = salary_predictor.SalaryBand(
                p25=baseline.p25,
                p50=baseline.p50,
                p75=baseline.p75,
                confidence=baseline.confidence,
                model_version="baseline-v0",
            )

    if band is None:
        return

    profile.predicted_salary_p25 = band.p25
    profile.predicted_salary_p50 = band.p50
    profile.predicted_salary_p75 = band.p75
    profile.predicted_salary_confidence = band.confidence
    profile.predicted_salary_model_version = band.model_version
