"""Re-analyse existing vacancies with the Phase 2.4b prompt.

Old ``VacancyProfile`` rows lack ``role_family`` / ``role_is_technical``.
This script walks rows whose ``schema_version`` is older than
``ROLE_FAMILY_SCHEMA_VERSION``, re-runs the analyzer, and persists the
updated profile (which re-embeds + upserts into Qdrant).

Idempotent: already-migrated rows are skipped on ``schema_version``.
Budget-capped: ``--limit`` bounds the run; ``--dry-run`` prints what
would change without touching the DB.

Usage:
    docker compose exec backend python -m scripts.backfill_role_family \\
        --limit 500

Run this incrementally — the analyzer is a paid OpenAI call, and
re-embedding touches Qdrant. A typical backfill window is ~500/day
against the budget guard in ``app.services.openai_usage``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.models.vacancy import Vacancy  # noqa: E402
from app.models.vacancy_profile import VacancyProfile  # noqa: E402
from app.services.vacancy_analyzer import (  # noqa: E402
    VacancyAnalysisUnavailable,
    analyze_vacancy_text,
)
from app.services.vacancy_profile_backfill import _build_vacancy_analysis_input  # noqa: E402
from app.services.vacancy_profile_pipeline import persist_vacancy_profile  # noqa: E402

logger = logging.getLogger("backfill_role_family")

ROLE_FAMILY_SCHEMA_VERSION = "2026-04-22-role-family"


def _pending_profiles(db: Session, *, limit: int) -> list[VacancyProfile]:
    return list(
        db.scalars(
            select(VacancyProfile)
            .where(VacancyProfile.schema_version != ROLE_FAMILY_SCHEMA_VERSION)
            .order_by(VacancyProfile.updated_at.desc())
            .limit(limit)
        ).all()
    )


def _run(db: Session, *, limit: int, dry_run: bool) -> dict[str, int]:
    stats = {"considered": 0, "updated": 0, "failed": 0, "skipped_no_vacancy": 0}
    profiles = _pending_profiles(db, limit=limit)
    logger.info("found %d profiles on older schema_version", len(profiles))

    for vp in profiles:
        stats["considered"] += 1
        vacancy = db.get(Vacancy, vp.vacancy_id)
        if vacancy is None or vacancy.status != "indexed":
            stats["skipped_no_vacancy"] += 1
            continue
        if dry_run:
            logger.info("DRY vacancy_id=%s title=%s", vacancy.id, vacancy.title)
            continue
        try:
            analysis_input = _build_vacancy_analysis_input(
                title=vacancy.title,
                source_url=vacancy.source_url,
                raw_text=vacancy.raw_text,
                company=vacancy.company,
            )
            profile = analyze_vacancy_text(analysis_input)
            persist_vacancy_profile(
                db,
                vacancy_id=vacancy.id,
                source_url=vacancy.source_url,
                title=vacancy.title,
                company=vacancy.company,
                profile=profile,
            )
            vp_refetched = (
                db.query(VacancyProfile).filter(VacancyProfile.vacancy_id == vacancy.id).one()
            )
            vp_refetched.schema_version = ROLE_FAMILY_SCHEMA_VERSION
            db.add(vp_refetched)
            db.commit()
            stats["updated"] += 1
        except VacancyAnalysisUnavailable as error:
            logger.warning("analyzer unavailable, aborting: %s", error)
            break
        except Exception as error:  # noqa: BLE001
            logger.exception("vacancy_id=%s failed: %s", vacancy.id, error)
            db.rollback()
            stats["failed"] += 1
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill role_family on vacancy profiles")
    parser.add_argument("--limit", type=int, default=100, help="Max profiles to process in one run")
    parser.add_argument(
        "--dry-run", action="store_true", help="List pending profiles without calling the analyzer"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    with SessionLocal() as db:
        stats = _run(db, limit=args.limit, dry_run=args.dry_run)
    logger.info("done: %s", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
