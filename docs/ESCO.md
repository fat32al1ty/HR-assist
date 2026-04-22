# ESCO taxonomy in HR-Assist

Phase 2.4 replaces hand-curated skill-alias groups with the EU's
[ESCO](https://esco.ec.europa.eu/) taxonomy. ESCO v1.1 covers ~3000
occupations and ~13,500 skills across 27 EU languages (including
Russian), with essential/optional skill links per occupation and
broader/narrower relations in the skill hierarchy.

## Data source + licence

- **Dataset:** ESCO v1.1 CSV download,
  https://esco.ec.europa.eu/en/use-esco/download
- **Format:** Choose the CSV dump — JSON-LD is fine but slower to load.
- **Size:** ~40 MB compressed, ~250 MB extracted (multi-language).
- **Licence:** Creative Commons BY 4.0. Attribution belongs in any
  user-facing surface that directly exposes ESCO preferred labels. We
  use ESCO as an internal lookup — attribution lives here + in the
  import script header.

## Refresh cadence

ESCO ships a new release roughly once a year. Re-import is safe
because the importer upserts on ``esco_uri`` — URIs are stable across
minor versions. Major version bumps (v2.0) may re-number ISCO groups;
schedule a dry run before running in prod.

## Tables (migration 0019)

| Table | PK | Purpose |
|---|---|---|
| ``esco_occupation`` | ``id`` (``esco_uri`` UNIQUE) | Job roles, with preferred + alt labels in EN and RU, ISCO group, self-FK to broader occupation. |
| ``esco_skill`` | ``id`` (``esco_uri`` UNIQUE) | Skills with preferred + alt labels, reuse-level, skill type. |
| ``esco_occupation_skill`` | (occ, skill, relation) | Essential/optional skill links per occupation. |
| ``esco_skill_relation`` | (from, to, relation) | Broader/narrower skill hierarchy. |

All four tables are read-only at request time; only the importer writes.

## One-shot import

```bash
# Download + extract ESCO v1.1 CSV under .tmp/ (gitignored):
mkdir -p .tmp/esco && curl -sL https://.../ESCO-dataset-v1.1.zip -o .tmp/esco.zip
unzip .tmp/esco.zip -d .tmp/esco

# Run the importer in the backend container:
docker compose exec backend python -m scripts.import_esco \
    --csv-dir /app/.tmp/esco/ESCO-dataset-v1.1 \
    --languages ru,en
```

The importer is idempotent — re-running updates preferred labels + alt
labels on existing URIs without creating duplicates.

Expected row counts for v1.1 (for smoke-testing the load):

- ``esco_occupation``: ~3000
- ``esco_skill``: ~13,500
- ``esco_occupation_skill``: ~130,000
- ``esco_skill_relation``: ~9,000 (pairs, so 2× broader/narrower inserts)

## Lookup helpers

``app.services.esco`` exposes:

- ``lookup_skill(db, text, lang, top_k)`` — returns top-k ``EscoSkillHit`` by
  exact match + token-Jaccard on preferred + alt labels.
- ``lookup_occupation(db, text, lang, top_k)`` — same shape for occupations.
- ``skills_for_occupation(db, occ_id, relation)`` — essential/optional/any.
- ``role_distance(occ_a, occ_b)`` — ``[0, 1]`` distance from shared ISCO
  prefix. See the function docstring for the bucket table.

These are used by ``RoleFamilyGateStage`` (Phase 2.4b) and incrementally
replace the hand-curated ``SKILL_ALIAS_GROUPS`` in ``matching_service``.
