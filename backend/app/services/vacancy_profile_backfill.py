from __future__ import annotations

import re
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vacancy import Vacancy
from app.services.vacancy_analyzer import analyze_vacancy_text
from app.services.vacancy_profile_pipeline import persist_vacancy_profile


def _build_vacancy_analysis_input(
    *, title: str, source_url: str, raw_text: str | None, company: str | None
) -> str:
    parts = [
        f"Vacancy title: {title}",
        f"Company: {company or 'unknown'}",
        f"Source URL: {source_url}",
        "Vacancy text:",
        raw_text or "",
    ]
    return "\n".join(parts)


def _is_backfill_candidate(vacancy: Vacancy) -> bool:
    source_url = (vacancy.source_url or "").strip().lower()
    title = (vacancy.title or "").strip().lower()
    path = (urlparse(source_url).path or "").lower()

    if title.startswith("работа ") or " свежих ваканс" in title:
        return False
    if title in {"hh", "hh |", "superjob", "habr career", "vacancies", "jobs", "вакансии"}:
        return False

    if "hh.ru" in source_url:
        return "/vacancy/" in path and bool(re.search(r"\d", path))
    if "career.habr.com" in source_url:
        return path.startswith("/vacancies/") and bool(re.search(r"\d", path))
    if "superjob.ru" in source_url:
        return "/vakansii/" in path and bool(re.search(r"\d", path))
    return False


def backfill_missing_vacancy_profiles(db: Session, *, limit: int) -> dict[str, int]:
    stats = {"considered": 0, "profiled": 0, "filtered": 0, "failed": 0}
    if limit <= 0:
        return stats

    vacancies = db.scalars(
        select(Vacancy)
        .where(Vacancy.status == "indexed")
        .where(~Vacancy.profile.has())
        .order_by(Vacancy.updated_at.desc())
        .limit(limit)
    ).all()

    for vacancy in vacancies:
        if not _is_backfill_candidate(vacancy):
            continue
        stats["considered"] += 1
        try:
            analysis_input = _build_vacancy_analysis_input(
                title=vacancy.title,
                source_url=vacancy.source_url,
                raw_text=vacancy.raw_text,
                company=vacancy.company,
            )
            profile = analyze_vacancy_text(analysis_input)
            is_vacancy = bool(profile.get("is_vacancy"))
            confidence = float(profile.get("vacancy_confidence") or 0.0)
            if not is_vacancy or confidence < 0.55:
                vacancy.status = "filtered"
                vacancy.error_message = str(
                    profile.get("rejection_reason") or "Filtered during profile backfill"
                )
                db.add(vacancy)
                db.commit()
                db.refresh(vacancy)
                stats["filtered"] += 1
                continue

            persist_vacancy_profile(
                db,
                vacancy_id=vacancy.id,
                source_url=vacancy.source_url,
                title=vacancy.title,
                company=vacancy.company,
                profile=profile,
            )
            stats["profiled"] += 1
        except Exception as error:
            vacancy.error_message = f"Profile backfill failed: {error}"
            db.add(vacancy)
            db.commit()
            db.refresh(vacancy)
            stats["failed"] += 1

    return stats
