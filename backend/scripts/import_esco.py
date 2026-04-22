"""One-shot import of the ESCO v1.1 CSV dump.

Downloads live at https://esco.ec.europa.eu/en/use-esco/download
(CC-BY 4.0). This script expects the extracted CSV directory and
loads four tables: occupations, skills, occupation-skill relations,
skill-skill broader/narrower relations.

Usage:
    docker compose exec backend python -m scripts.import_esco \\
        --csv-dir /path/to/ESCO-dataset-v1.1 [--languages ru,en]

Idempotency: rows are upserted on ``esco_uri``. Re-running after a
partial import picks up where it left off. Counts of inserted vs.
updated rows are logged per table.

The importer reads the following files, whose names match the
default ESCO release layout:

- ``occupations_<lang>.csv``  — per language, one row per occupation
- ``skills_<lang>.csv``       — per language, one row per skill
- ``occupationSkillRelations.csv`` — essential/optional links
- ``broaderRelationsSkillPillar.csv`` — broader/narrower skill tree

Only the languages in ``--languages`` are loaded. The English dump
is always loaded (required — preferred_label_en is NOT NULL). Other
languages populate alt_labels + preferred_label_xx if the column
exists (currently only ``ru`` has a dedicated column).
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

# Allow running from ``backend/`` as `python -m scripts.import_esco`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.models.esco import (  # noqa: E402
    EscoOccupation,
    EscoOccupationSkill,
    EscoSkill,
    EscoSkillRelation,
)

logger = logging.getLogger("import_esco")


def _read_occupation_rows(path: Path) -> dict[str, dict]:
    """Keyed by ``esco_uri`` so subsequent languages merge into the same row."""
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            uri = row.get("conceptUri") or row.get("uri")
            if not uri:
                continue
            rows[uri] = row
    return rows


def _import_occupations(db: Session, csv_dir: Path, languages: list[str]) -> None:
    english = _read_occupation_rows(csv_dir / "occupations_en.csv")
    if not english:
        raise RuntimeError("occupations_en.csv is required — preferred_label_en is NOT NULL")

    alt_by_uri: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"ru": [], "en": []})
    ru_label_by_uri: dict[str, str] = {}

    if "en" in languages:
        for uri, row in english.items():
            alt = _split_alt_labels(row.get("altLabels", ""))
            alt_by_uri[uri]["en"] = alt

    if "ru" in languages:
        ru_path = csv_dir / "occupations_ru.csv"
        if ru_path.exists():
            for uri, row in _read_occupation_rows(ru_path).items():
                ru_label_by_uri[uri] = row.get("preferredLabel", "")
                alt_by_uri[uri]["ru"] = _split_alt_labels(row.get("altLabels", ""))

    payload = []
    for uri, row in english.items():
        payload.append(
            {
                "esco_uri": uri,
                "preferred_label_en": row.get("preferredLabel", ""),
                "preferred_label_ru": ru_label_by_uri.get(uri) or None,
                "alt_labels_en": alt_by_uri[uri]["en"],
                "alt_labels_ru": alt_by_uri[uri]["ru"],
                "description": row.get("description", "") or None,
                "isco_group": row.get("iscoGroup", "") or None,
            }
        )

    inserted = _upsert_batch(db, EscoOccupation.__table__, payload, key="esco_uri")
    logger.info("occupations: %d rows processed (%d new)", len(payload), inserted)


def _read_skill_rows(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            uri = row.get("conceptUri") or row.get("uri")
            if uri:
                rows[uri] = row
    return rows


def _import_skills(db: Session, csv_dir: Path, languages: list[str]) -> None:
    english = _read_skill_rows(csv_dir / "skills_en.csv")
    if not english:
        raise RuntimeError("skills_en.csv is required")

    ru_label_by_uri: dict[str, str] = {}
    alt_labels_by_uri: dict[str, list[str]] = defaultdict(list)

    if "en" in languages:
        for uri, row in english.items():
            alt_labels_by_uri[uri].extend(_split_alt_labels(row.get("altLabels", "")))

    if "ru" in languages:
        for uri, row in _read_skill_rows(csv_dir / "skills_ru.csv").items():
            ru_label_by_uri[uri] = row.get("preferredLabel", "")
            alt_labels_by_uri[uri].extend(_split_alt_labels(row.get("altLabels", "")))

    payload = []
    for uri, row in english.items():
        payload.append(
            {
                "esco_uri": uri,
                "preferred_label_en": row.get("preferredLabel", ""),
                "preferred_label_ru": ru_label_by_uri.get(uri) or None,
                "alt_labels": alt_labels_by_uri[uri],
                "reuse_level": row.get("reuseLevel", "") or None,
                "skill_type": row.get("skillType", "") or None,
            }
        )

    inserted = _upsert_batch(db, EscoSkill.__table__, payload, key="esco_uri")
    logger.info("skills: %d rows processed (%d new)", len(payload), inserted)


def _import_occupation_skill_relations(db: Session, csv_dir: Path) -> None:
    path = csv_dir / "occupationSkillRelations.csv"
    if not path.exists():
        logger.warning("occupationSkillRelations.csv missing — skipping")
        return

    occ_id_by_uri = {uri: oid for uri, oid in db.query(EscoOccupation.esco_uri, EscoOccupation.id)}
    skill_id_by_uri = {uri: sid for uri, sid in db.query(EscoSkill.esco_uri, EscoSkill.id)}

    payload = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            occ_uri = row.get("occupationUri")
            skill_uri = row.get("skillUri")
            relation = (row.get("relationType") or "").strip().lower()
            if relation not in {"essential", "optional"}:
                continue
            occ_id = occ_id_by_uri.get(occ_uri)
            skill_id = skill_id_by_uri.get(skill_uri)
            if occ_id is None or skill_id is None:
                continue
            payload.append({"occupation_id": occ_id, "skill_id": skill_id, "relation": relation})

    if payload:
        db.execute(
            pg_insert(EscoOccupationSkill.__table__)
            .values(payload)
            .on_conflict_do_nothing(index_elements=["occupation_id", "skill_id", "relation"])
        )
        db.commit()
    logger.info("occupation_skill: %d rows processed", len(payload))


def _import_skill_broader_relations(db: Session, csv_dir: Path) -> None:
    path = csv_dir / "broaderRelationsSkillPillar.csv"
    if not path.exists():
        logger.warning("broaderRelationsSkillPillar.csv missing — skipping")
        return

    skill_id_by_uri = {uri: sid for uri, sid in db.query(EscoSkill.esco_uri, EscoSkill.id)}

    payload = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            child_uri = row.get("conceptUri") or row.get("narrowerUri")
            parent_uri = row.get("broaderUri")
            child_id = skill_id_by_uri.get(child_uri)
            parent_id = skill_id_by_uri.get(parent_uri)
            if child_id is None or parent_id is None:
                continue
            payload.append({"from_id": child_id, "to_id": parent_id, "relation": "broader"})
            payload.append({"from_id": parent_id, "to_id": child_id, "relation": "narrower"})

    if payload:
        db.execute(
            pg_insert(EscoSkillRelation.__table__)
            .values(payload)
            .on_conflict_do_nothing(index_elements=["from_id", "to_id", "relation"])
        )
        db.commit()
    logger.info("skill_relations: %d rows processed", len(payload))


def _split_alt_labels(value: str) -> list[str]:
    if not value:
        return []
    # ESCO uses ``\n`` (literal) in altLabels; CSV reader yields actual newlines.
    parts = (p.strip() for p in value.replace("\r", "\n").split("\n"))
    return [p for p in parts if p]


def _upsert_batch(db: Session, table, rows: list[dict], *, key: str, batch_size: int = 1000) -> int:
    if not rows:
        return 0
    existing_keys = {k for (k,) in db.execute(db.query(getattr(table.c, key)).statement)}
    inserted = 0
    for start in range(0, len(rows), batch_size):
        chunk = rows[start : start + batch_size]
        stmt = pg_insert(table).values(chunk)
        update_cols = {
            col.name: stmt.excluded[col.name]
            for col in table.c
            if col.name != key and col.name != "id"
        }
        stmt = stmt.on_conflict_do_update(index_elements=[key], set_=update_cols)
        db.execute(stmt)
        for row in chunk:
            if row[key] not in existing_keys:
                inserted += 1
    db.commit()
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Import ESCO CSV dump into Postgres")
    parser.add_argument("--csv-dir", type=Path, required=True, help="ESCO v1.1 CSV directory")
    parser.add_argument(
        "--languages",
        default="ru,en",
        help="Comma-separated language codes to load (default: ru,en)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    csv_dir = args.csv_dir
    if not csv_dir.exists():
        logger.error("csv dir %s does not exist", csv_dir)
        return 2

    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    if "en" not in languages:
        languages.insert(0, "en")

    with SessionLocal() as db:
        _import_occupations(db, csv_dir, languages)
        _import_skills(db, csv_dir, languages)
        _import_occupation_skill_relations(db, csv_dir)
        _import_skill_broader_relations(db, csv_dir)
    logger.info("ESCO import complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
