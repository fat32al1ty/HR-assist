"""Backfill stated-salary columns on existing ``vacancy_profiles``.

Phase 2.7. Iterates vacancies whose profile has ``salary_min`` /
``salary_max`` unset, pulls the stated salary from the raw payload
(and, as a fallback, from ``raw_text``), and writes it to the new
columns added in migration ``0021_salary_fields``.

Idempotent — re-running will not touch profiles that already have
salary values. Safe to run in prod; commits every batch so a partial
abort leaves earlier batches persisted.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Iterator

logger = logging.getLogger("backfill_vacancy_salary")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print stats without writing."
    )
    args = parser.parse_args()

    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.models.vacancy import Vacancy  # noqa: PLC0415
    from app.models.vacancy_profile import VacancyProfile  # noqa: PLC0415
    from app.services.salary_extract import extract_for_vacancy  # noqa: PLC0415

    db = SessionLocal()
    updated = 0
    scanned = 0
    try:
        ids = [
            row[0]
            for row in db.query(VacancyProfile.id)
            .filter(VacancyProfile.salary_min.is_(None))
            .filter(VacancyProfile.salary_max.is_(None))
            .all()
        ]
        logger.info("found %d profiles without stated salary", len(ids))
        for chunk in _chunks(ids, args.batch_size):
            rows = (
                db.query(VacancyProfile, Vacancy)
                .join(Vacancy, Vacancy.id == VacancyProfile.vacancy_id)
                .filter(VacancyProfile.id.in_(chunk))
                .all()
            )
            for vp, vac in rows:
                scanned += 1
                extracted = extract_for_vacancy(vac.source, vac.raw_payload, vac.raw_text)
                if not extracted.is_present():
                    continue
                vp.salary_min = extracted.salary_min
                vp.salary_max = extracted.salary_max
                vp.salary_currency = extracted.currency
                vp.salary_gross = extracted.gross
                updated += 1
            if not args.dry_run:
                db.commit()
            logger.info("progress: scanned=%d updated=%d", scanned, updated)
    finally:
        db.close()

    logger.info("done - scanned=%d updated=%d (dry_run=%s)", scanned, updated, args.dry_run)
    return 0


def _chunks(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


if __name__ == "__main__":
    sys.exit(main())
