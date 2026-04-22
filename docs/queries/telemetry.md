# Match telemetry — query cheatsheet

Phase 2.6. Three tables feed the LTR training prep and quality dashboards:

- `match_impression` — one row per card shown (server-side, at the tail of `match_vacancies_for_resume`).
- `match_click` — one row per user click (kinds: `open_card`, `open_source`, `apply`, `like`, `dislike`).
- `match_dwell` — `(match_run_id, vacancy_id)` PK, ms is summed on conflict.

All three are append-only and best-effort — insert failures are logged, not surfaced.

## CTR by tier (last 7 days)

```sql
SELECT
  i.tier,
  COUNT(*)                                              AS impressions,
  COUNT(c.id)                                           AS clicks,
  ROUND(100.0 * COUNT(c.id) / NULLIF(COUNT(*), 0), 2)  AS ctr_pct
FROM match_impression i
LEFT JOIN match_click c
  ON c.match_run_id = i.match_run_id
 AND c.vacancy_id   = i.vacancy_id
 AND c.click_kind IN ('open_source', 'apply')
WHERE i.ts >= now() - interval '7 days'
GROUP BY i.tier
ORDER BY i.tier;
```

Sanity: `strong` tier CTR should be meaningfully higher than `maybe`. If they converge, rerank isn't pulling its weight.

## Apply-rate by role_family (last 30 days)

```sql
SELECT
  i.role_family,
  COUNT(*)                                                             AS impressions,
  COUNT(*) FILTER (WHERE c.click_kind = 'apply')                       AS applies,
  ROUND(100.0 * COUNT(*) FILTER (WHERE c.click_kind = 'apply')
               / NULLIF(COUNT(*), 0), 2)                               AS apply_pct
FROM match_impression i
LEFT JOIN match_click c
  ON c.match_run_id = i.match_run_id
 AND c.vacancy_id   = i.vacancy_id
WHERE i.ts >= now() - interval '30 days'
  AND i.role_family IS NOT NULL
GROUP BY i.role_family
HAVING COUNT(*) >= 20
ORDER BY apply_pct DESC NULLS LAST;
```

Low-apply families might be overfiring — check against gold-set eval before loosening/tightening the gate.

## Dislikes concentrated on a role_family (possible mis-classification)

```sql
SELECT
  i.role_family,
  COUNT(*) FILTER (WHERE c.click_kind = 'dislike') AS dislikes,
  COUNT(*)                                         AS impressions,
  ROUND(100.0 * COUNT(*) FILTER (WHERE c.click_kind = 'dislike')
               / NULLIF(COUNT(*), 0), 2)          AS dislike_pct
FROM match_impression i
LEFT JOIN match_click c
  ON c.match_run_id = i.match_run_id
 AND c.vacancy_id   = i.vacancy_id
WHERE i.ts >= now() - interval '14 days'
  AND i.role_family IS NOT NULL
GROUP BY i.role_family
HAVING COUNT(*) FILTER (WHERE c.click_kind = 'dislike') >= 5
ORDER BY dislike_pct DESC;
```

Spikes here usually mean the role-family gate is letting adjacent families through (e.g. DevOps shown to backend resumes).

## Dwell vs click — who reads before acting

```sql
SELECT
  CASE
    WHEN d.ms IS NULL          THEN 'no_dwell'
    WHEN d.ms < 3000           THEN 'glance_<3s'
    WHEN d.ms < 10000          THEN 'read_3-10s'
    ELSE                            'deep_>10s'
  END AS dwell_bucket,
  COUNT(*)                                                   AS n,
  COUNT(*) FILTER (WHERE c.click_kind = 'apply')             AS applies,
  COUNT(*) FILTER (WHERE c.click_kind = 'dislike')           AS dislikes
FROM match_impression i
LEFT JOIN match_dwell d
  ON d.match_run_id = i.match_run_id
 AND d.vacancy_id   = i.vacancy_id
LEFT JOIN match_click c
  ON c.match_run_id = i.match_run_id
 AND c.vacancy_id   = i.vacancy_id
WHERE i.ts >= now() - interval '14 days'
GROUP BY 1
ORDER BY 1;
```

A healthy profile: applies concentrate in `read_3-10s` and `deep_>10s`, dislikes in `glance_<3s`.

## Position bias — does slot 0 dominate regardless of score

```sql
SELECT
  i.position,
  AVG(i.hybrid_score)                                          AS avg_hybrid,
  AVG(i.rerank_score)                                          AS avg_rerank,
  COUNT(*) FILTER (WHERE c.click_kind IN ('open_source','apply'))
    * 1.0 / NULLIF(COUNT(*), 0)                                AS ctr
FROM match_impression i
LEFT JOIN match_click c
  ON c.match_run_id = i.match_run_id
 AND c.vacancy_id   = i.vacancy_id
WHERE i.ts >= now() - interval '14 days'
  AND i.position < 10
GROUP BY i.position
ORDER BY i.position;
```

Monotonic CTR decline by position is expected; a hard cliff after position 0 suggests users never scroll.

## LLM rerank confidence vs actual outcome

```sql
SELECT
  width_bucket(i.llm_confidence, 0, 1, 5) AS conf_bucket,
  COUNT(*)                                                    AS n,
  COUNT(*) FILTER (WHERE c.click_kind = 'apply')              AS applies,
  ROUND(100.0 * COUNT(*) FILTER (WHERE c.click_kind = 'apply')
               / NULLIF(COUNT(*), 0), 2)                     AS apply_pct
FROM match_impression i
LEFT JOIN match_click c
  ON c.match_run_id = i.match_run_id
 AND c.vacancy_id   = i.vacancy_id
WHERE i.ts >= now() - interval '30 days'
  AND i.llm_confidence IS NOT NULL
GROUP BY 1
ORDER BY 1;
```

If high-confidence buckets don't produce higher apply rates, the prompt or the model is miscalibrated.
