# Phase 5 — Infra & data

**Goal:** keep the product reliable and cheap as traffic grows. Not a rewrite, not microservices — just closing the three or four holes that will show up first under load.

**When to tackle:** in parallel with Phase 3 and 4 tasks. None of these block features, but one bad night with a restarted prod container losing everyone's in-flight job will force the work anyway.

## Tasks

### 5.1 Persistent job queue across restarts
- [ ] `recommendation_jobs` already has `status` in DB. The orchestrator (`recommendation_jobs.py`) keeps jobs in an in-process `ThreadPoolExecutor`. A restart loses everything: `running` jobs stay `running` forever, users see a broken progress bar.
- [ ] On backend startup, run a reaper: any job in `running` or `queued` older than 60 s at boot → mark `failed` with reason `"worker_restarted"`. Add a user-visible message "подбор прерван перезапуском — запусти снова."
- [ ] Do NOT introduce Celery/RQ for this. The goal is to be resilient to restarts, not to scale to 100 workers. Single-process FastAPI + thread pool is fine for the current load.

**Files:** `backend/app/services/recommendation_jobs.py`, `backend/app/main.py` (startup hook), `backend/app/repositories/recommendation_jobs.py`.
**Acceptance:** start a job, `docker compose restart backend`, wait 30 s, job is `failed` with reason `worker_restarted`, UI shows the friendly message and re-enables the start button.
**Suggested commit:** `fix(jobs): reap zombie jobs on backend restart`

### 5.2 Cap `raw_text` on the vacancy model
- [ ] `vacancies.raw_text` is unlimited. A pathological 2 MB hh.ru page fills the row and slows every subsequent query. Cap at 500 000 chars at the source (`vacancy_sources.py`) — truncate with an ellipsis marker and log the truncation.
- [ ] Alembic migration: `alter column raw_text type varchar(500000)` (or keep TEXT but enforce the cap in the service layer — pick the latter to avoid a long table rewrite; TEXT + service-side guard is fine).
- [ ] Embeddings only need the vacancy summary anyway; raw_text is for the UI's "открыть источник" preview. Confirm nothing reads raw_text beyond display.

**Files:** `backend/app/services/vacancy_sources.py`, optionally `backend/alembic/versions/<new>_cap_raw_text.py`.
**Acceptance:** feed a fixture with a 2 MB page; the stored row is ≤ 500 010 chars (cap + marker) and embedding still works.
**Suggested commit:** `fix(vacancies): cap raw_text to keep row sizes sane`

### 5.3 Kill obvious N+1 in recommendations read path
- [ ] `GET /vacancies/recommend/{job_id}/results` currently loads matches then per-row loads the related vacancy. Use `selectinload(VacancyMatch.vacancy)` in the repository method.
- [ ] Audit each repository in `backend/app/repositories/` for the same pattern. Typical culprits: applications → vacancy, saved_searches → resume.
- [ ] Add a test that runs the endpoint with 50 matches and asserts `< 5` SQL queries using `sqlalchemy`'s `event.listens_for(Engine, "before_cursor_execute")` counter.

**Files:** `backend/app/repositories/recommendation_jobs.py`, `backend/app/repositories/applications.py`, `backend/app/repositories/saved_searches.py`, `backend/tests/test_query_count.py` (new).
**Acceptance:** query-count test passes for every read endpoint that returns a list with relations.
**Suggested commit:** `perf(repositories): eager-load relations to eliminate N+1`

### 5.4 Qdrant collection settings audit
- [ ] Current collection uses default HNSW params. For 3072-dim embeddings, `m=16, ef_construct=100` is fine but `on_disk_payload=true` + `quantization: scalar` cuts memory 4× with negligible quality loss. Benchmark before flipping.
- [ ] If we cross 100 k vacancies, the collection will need shard config. Document the current numbers in `backend/README.md` so we spot the threshold.
- [ ] Add a `/healthz/qdrant` endpoint returning `{count, dim, memory_mb}` for dashboards and the `?debug=1` panel from Phase 4.7.

**Files:** `backend/app/services/qdrant_client.py`, `backend/app/api/routes/health.py` (new), `backend/README.md`.
**Acceptance:** benchmark recall@10 before/after quantization on a held-out set; proceed only if recall drops ≤ 2 %.
**Suggested commit:** `perf(qdrant): scalar quantization + on-disk payload`

### 5.5 OpenAI call retries with jitter
- [ ] Today, a transient 429 from OpenAI fails the whole job. Wrap `client.responses.create` and `client.embeddings.create` in a retry helper: 3 attempts, exponential backoff with jitter (1 s, 2–4 s, 5–10 s), only retry on 429 / 5xx / ConnectionError.
- [ ] Structured log each retry attempt with `retry_attempt` field so we can see patterns in Phase 6.
- [ ] Budget interaction: a retried call still counts once against the daily budget (don't double-charge on network flakes).

**Files:** `backend/app/services/openai_usage.py` (new `with_retry()` wrapper), all four call sites from Phase 0.4.
**Acceptance:** inject a 429 on first call; job completes after retry and structured log shows `retry_attempt=1, retry_attempt=0` entries.
**Suggested commit:** `fix(openai): retry transient failures with jittered backoff`

### 5.6 Per-source vacancy dedup
- [ ] Today a single vacancy posted on hh.ru + Habr Career appears twice in the match list. Dedup key: `(normalised_title, company, city)` with a simple Jaccard similarity ≥ 0.9 check on the first 500 chars of raw_text.
- [ ] Dedup happens after scoring but before slice to top-N; we prefer the higher-scoring copy.
- [ ] Show the extra source URLs on the surviving card: "также на Хабр Карьере" link.

**Files:** `backend/app/services/matching_service.py`, `backend/app/schemas/vacancy.py`.
**Acceptance:** seed two vacancies with near-identical titles and companies from different sources; match list returns one entry with both source URLs.
**Suggested commit:** `feat(matching): dedup cross-source duplicates in match list`

## Definition of done

5.1, 5.2, 5.3, 5.5 merged and live. 5.4 and 5.6 are follow-ups that ship when they're ready.

After a prod restart mid-job: no frozen progress bars, no duplicate matches in the result page, no 2 MB `raw_text` rows.

Update `SKILL.md` phase status.
