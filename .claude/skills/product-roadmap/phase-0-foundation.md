# Phase 0 — Foundation

**Status:** completed 2026-04-21.

**Goal:** close real security, cost, and audit gaps that are cheap to fix now and expensive once user traffic grows. Everything here is <1 day each. Must happen before Phase 1, because shipping features on top of these holes amplifies every one of them.

**Why first:** beta users are forgiving about missing features but not about account security or opaque cost explosions. Also, most of these prevent later tasks from being testable (you can't write a budget test if there is no budget counter).

## Tasks

### 0.1 Auth rate limiting + user-enumeration fix
- [x] Add `slowapi` (or equivalent) middleware on `/auth/login`, `/auth/register`, `/auth/password/reset`. Recommend 10/min/IP for register+reset, 20/min/IP for login.
- [x] Unify the error shape of `/auth/register`: return 403 `"Invalid credentials or beta key"` for *both* wrong beta key and "email already exists." Current code at `backend/app/api/routes/auth.py:64-96` distinguishes them → user-enumeration.
- [x] Add a test asserting that register with "wrong key" and register with "existing email" return structurally identical responses.

**Files:** `backend/app/api/routes/auth.py`, `backend/requirements.txt` (add slowapi), `backend/tests/test_auth_hardening_flow.py`.
**Acceptance:** 10 rapid registration attempts with the same IP → the 11th returns 429. Email enumeration test passes.
**Suggested commit:** `feat(auth): rate-limit sensitive endpoints and suppress user enumeration`

### 0.2 Input length caps on all user-supplied strings
- [x] Audit every Pydantic schema in `backend/app/schemas/` with `str` fields that come from the client (resume filename, vacancy query, recommendation prompt). Add `Field(max_length=N)` with sensible N.
- [x] Minimum caps to set: filename 255, free-text query 500, beta_key 64, email 254, password 128, full_name 200, preferences prompt 1000.
- [x] Add one regression test per schema that a payload above the cap returns 422.

**Files:** `backend/app/schemas/*.py`, one new `backend/tests/test_schema_limits.py`.
**Acceptance:** posting a 1 MB string to any endpoint returns 422, not 500 and not a silent OpenAI call.
**Suggested commit:** `fix(schemas): cap user-supplied string lengths to prevent quota waste`

### 0.3 Daily per-user OpenAI budget
- [x] New `user_daily_spend` table: `user_id`, `date`, `spend_usd`, `updated_at`. Unique on `(user_id, date)`.
- [x] Before `start_recommendation_job`, check `sum(spend_usd) where user_id=X and date=today()` against `OPENAI_USER_DAILY_BUDGET_USD` (new setting, default $1.00).
- [x] After each OpenAI call inside the job, increment the counter in the same transaction that commits the match results.
- [x] Over-budget → fail the job early with a structured error; surface it to the user as "дневной лимит OpenAI исчерпан, попробуйте завтра."

**Files:** `backend/alembic/versions/<new>_user_daily_spend.py`, `backend/app/models/user_daily_spend.py`, `backend/app/services/openai_usage.py`, `backend/app/services/recommendation_jobs.py`, `backend/app/core/config.py`.
**Acceptance:** integration test that runs 3 jobs back-to-back for the same user exceeding the daily cap returns the friendly error on job 3.
**Suggested commit:** `feat(openai): daily per-user budget with friendly over-limit error`

### 0.4 Structured logging on OpenAI calls
- [x] Introduce a single helper `log_openai_call(event, model, prompt_tokens, completion_tokens, cost_usd, user_id, duration_ms)` that emits one JSON line per call via the stdlib `logging` module.
- [x] Call it around every `client.responses.create(...)` / `client.embeddings.create(...)` invocation in `resume_analyzer.py`, `vacancy_analyzer.py`, `embeddings.py`, `recommendation_jobs.py`.
- [x] `docker logs resume_backend | grep OPENAI_CALL` must produce one JSON line per call.

**Files:** `backend/app/services/openai_usage.py` (helper), the four callers listed above.
**Acceptance:** manual: run a recommendation job, grep logs, see ≥3 `OPENAI_CALL` lines with non-zero token counts and a cost.
**Suggested commit:** `feat(logging): structured OPENAI_CALL events for audit and cost attribution`

### 0.5 Fix HTML decode fallback in vacancy sources
- [x] `backend/app/services/vacancy_sources.py` silently falls back to `.text` on UTF-8 decode failure, polluting embeddings with garbage. Change: log the failing source+URL, skip the record, and increment a failure counter in the job.
- [x] Surface the counter in the job-progress endpoint so the frontend can tell users "2 vacancies skipped due to parse errors."

**Files:** `backend/app/services/vacancy_sources.py`, `backend/app/schemas/recommendation_job.py`, `backend/app/repositories/recommendation_jobs.py`.
**Acceptance:** feed a fixture URL that returns Windows-1251-encoded HTML; job completes with `skipped_count=1` and none of that text reaches Qdrant.
**Suggested commit:** `fix(vacancies): skip malformed HTML instead of poisoning embeddings`

### 0.6 Remove debug-level console print from email delivery
- [x] `backend/app/services/email_delivery.py:17` uses `print()` to emit OTP codes in "console" mode. Replace with `logger.info(..., extra={"to": to_email, "subject": subject})` with body redacted; raw body behind DEBUG level only.
- [x] Production `.env` must have `AUTH_EMAIL_DELIVERY_MODE=disabled` or `smtp`, never `console`.

**Files:** `backend/app/services/email_delivery.py`.
**Acceptance:** `grep -r "print(" backend/app/services/` returns nothing for auth code paths.
**Suggested commit:** `fix(auth): redact OTP bodies in logs, remove raw print()`

## Definition of done

All six tasks merged to master, CI green, one manual smoke test run on prod where:
1. `/auth/register` with wrong beta key 11× in a minute → 11th is 429.
2. `/vacancies/recommend` with a 2 KB `preferences` returns 422 (cap at 1000).
3. `docker logs resume_backend | grep OPENAI_CALL | wc -l` > 0 after one run.
4. `/auth/register` error bodies for bad-key vs. existing-email are byte-identical except for a trace id.

When done, update the status line in `SKILL.md` to "completed YYYY-MM-DD" and move on to Phase 1.
