# Phase 6 — Quality & observability

**Goal:** make regressions visible and short-loop. Today the test suite catches unit-level breakage but lets end-to-end flow breakage through (upload resume → run match → apply → cover letter). We also have no aggregate view of OpenAI spend or job failure rate.

**Style:** this phase is ongoing. Each other phase should land its own tests; this phase captures the shared scaffolding and the end-to-end flow tests that live outside any single feature.

## Tasks

### 6.1 End-to-end flow tests against real services
- [ ] One pytest module `backend/tests/e2e/test_full_journey.py`. Uses a real Postgres + real Qdrant (the existing convention) and a seeded fake OpenAI via `OPENAI_BASE_URL=http://localhost:PORT` pointing at a stub server in `backend/tests/fixtures/openai_stub.py`.
- [ ] Scenarios:
  1. Signup → confirm email (console mode) → upload resume → self-check → run match → cancel.
  2. Signup → upload resume → run match → apply → generate cover letter → move kanban to "interview."
  3. Two users, each with a saved search; digest worker runs and sends one email each.
- [ ] Stub OpenAI returns canned responses keyed on prompt hash. Running the stub deterministic so CI is stable.

**Files:** `backend/tests/e2e/test_full_journey.py`, `backend/tests/fixtures/openai_stub.py`, `backend/tests/conftest.py` (boot the stub server).
**Acceptance:** `pytest backend/tests/e2e/` green in CI; the three flows take < 60 s combined.
**Suggested commit:** `test(e2e): three happy-path journeys against real Postgres + stubbed OpenAI`

### 6.2 Contract test for `OPENAI_CALL` log lines
- [ ] After Phase 0.4 ships, every OpenAI call must emit one JSON log line. Add a pytest that captures stdout while running a match and asserts: ≥ 3 lines with `event=OPENAI_CALL`, each with `model`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `user_id`, `duration_ms`.
- [ ] Also asserts `sum(cost_usd)` equals the delta written to `user_daily_spend` for that test run (catches the double-charge class of bug).

**Files:** `backend/tests/test_openai_logging_contract.py`.
**Acceptance:** deleting one structured-log call site makes the test fail with a clear message.
**Suggested commit:** `test(logging): contract test for OPENAI_CALL events`

### 6.3 Query-count regression guard
- [ ] Generalisation of Phase 5.3 test: a fixture `assert_max_queries(n)` context manager that counts SQL statements during a block. Use it on every read endpoint that returns a list.
- [ ] Threshold per endpoint is documented in the test file, not hidden in a constant.

**Files:** `backend/tests/fixtures/query_counter.py`, `backend/tests/test_query_counts.py`.
**Acceptance:** accidentally removing `selectinload` in any repository fails this test.
**Suggested commit:** `test(perf): lock in N+1 fixes with query-count assertions`

### 6.4 Structured logs for user actions that spend money
- [ ] Every OpenAI-spending endpoint logs a `USER_SPEND` event: `{user_id, feature, cost_usd, total_today_usd}`. Features: match, cover_letter, interview_prep, resume_rewrite.
- [ ] Test asserts one `USER_SPEND` per endpoint call.

**Files:** `backend/app/services/openai_usage.py`, tests per feature.
**Acceptance:** one-liner `docker logs resume_backend | grep USER_SPEND` gives a per-user spend timeline.
**Suggested commit:** `feat(logging): USER_SPEND events for every budget-consuming action`

### 6.5 Basic metrics endpoint for dashboards
- [ ] `GET /admin/metrics` (behind an admin token, not public) returns JSON with: total users (active last 7d), jobs run today, jobs failed today, total OpenAI cost today, median job duration, avg matches per successful job.
- [ ] No Prometheus / Grafana integration in this phase — just a JSON endpoint the operator curls. If we later want scraping, we add one wrapper.

**Files:** `backend/app/api/routes/admin.py`.
**Acceptance:** `curl -H 'X-Admin-Token: ...' /admin/metrics` returns a non-empty JSON body after a few jobs ran.
**Suggested commit:** `feat(observability): lightweight admin metrics JSON`

### 6.6 Frontend error reporting
- [ ] Install `@sentry/nextjs` OR, to keep dependencies minimal, send a `POST /api/client-errors` call with `{message, stack, url, user_id}` from a global error boundary. Backend stores last 100 in memory, returns them via `/admin/metrics`.
- [ ] Rate-limit on the server side: 60 client-error POSTs per IP per minute.

**Files:** `frontend/app/providers/error-boundary.tsx`, `backend/app/api/routes/client_errors.py`.
**Acceptance:** force a frontend render error (throw in a component); after reload, `/admin/metrics` lists it.
**Suggested commit:** `feat(observability): minimal client-error pipeline`

### 6.7 Regression pack for matching quality
- [ ] Golden set: 5 resume samples × 10 vacancies each, hand-labelled `good / ok / bad` match. Store as JSON fixtures. After any change to `matching_service.py` or the prompt, run the golden set and fail if any previously-good match dropped out of top-3 or any previously-bad match entered top-3.
- [ ] This is the only way to tell if an innocent "prompt cleanup" just broke relevance.

**Files:** `backend/tests/fixtures/matching_golden/*.json`, `backend/tests/test_matching_quality.py`.
**Acceptance:** edit `matching_service.py` to break scoring; test fails and names which pair regressed.
**Suggested commit:** `test(matching): golden-set regression pack for match quality`

## Definition of done

This phase is never fully done — it grows with every other phase. A reasonable checkpoint:
- 6.1 in CI.
- 6.2 and 6.3 in CI.
- 6.4 logs observable in prod.
- 6.5 JSON endpoint used at least weekly for ops.
- 6.7 golden set with at least 3 resume samples.

Update `SKILL.md` phase status to "in progress / last checkpoint YYYY-MM-DD."
