# Roadmap decisions log

Append-only record of cross-phase decisions. Each entry = date, decision, reasoning, affected phases.

## Format

```
## YYYY-MM-DD — short decision title
**Decision:** one sentence.
**Why:** the motivation (incident, learning, external change).
**Affects:** which phases / tasks this reshapes.
**Supersedes:** (optional) previous decision this replaces.
```

---

## 2026-04-21 — roadmap scoped to jobseeker product, monetization out
**Decision:** roadmap covers product, architecture, UX, debugging, tests. Monetization, marketing, and infra migration are explicitly out of scope.
**Why:** user framed HR-Assist as a replacement for paid jobseeker services (hh.ru Premium, career coaches, getmatch). Mixing monetization into phase planning was slowing down product decisions.
**Affects:** all phases — none include billing, paywalls, tiers, ads, SEO.

## 2026-04-21 — six-phase structure with Phase 0 as gate
**Decision:** Phase 0 (foundation) must land before any Phase 1+ feature ships to prod. Phases 1→3 are the product story, Phase 4 parallelisable, Phases 5–6 ongoing.
**Why:** beta is forgiving about missing features but not about account security or opaque costs. Also, several later tasks (budget tests, structured log assertions) can't exist until the scaffolding in Phase 0 is there.
**Affects:** sequencing at the skill level.

## 2026-04-21 — real services in tests, not mocks
**Decision:** integration tests use real Postgres and real Qdrant; OpenAI is the only external dependency we stub (and only because it's rate-limited and expensive).
**Why:** existing convention in the repo; mocked DB tests pass when real migrations break. Phase 6.1 e2e tests, Phase 5.3 query-count tests, and Phase 0.3 budget tests all depend on this.
**Affects:** all phases' test tasks.

## 2026-04-21 — no backwards-compat shims during beta
**Decision:** API shapes and DB columns change freely within a single PR that updates frontend + backend together. No `v1/v2` paths, no deprecated columns kept "for a release or two."
**Why:** beta users tolerate breakage if we flag it; deprecation chains cost more engineer-time than the one-off migration would.
**Affects:** every PR that touches a shared schema.

## 2026-04-21 — Phase 0 landed as six commits of self-contained fixes
**Decision:** all six Phase 0 tasks shipped on master; Phase 0 status flipped to "completed 2026-04-21" in SKILL.md.
**Why:** each sub-task was small and independently testable. Gating Phase 1 on the whole phase being green was cheaper than any per-task rollback would have been.
**Affects:** unblocks Phase 1. New contracts that Phase 1+ code must respect:
  - `record_*_usage` emits exactly one JSON line per OpenAI call on logger `openai_call` (see `tests/test_openai_call_logging.py`).
  - `VacancyDiscoveryMetrics.skipped_parse_errors` is authoritative for "records we dropped because bytes were undecodable"; it flows into `job.metrics` via `asdict()`.
  - `_fetch_text` raises `VacancyFetchError` on decode failure — never silently returns garbled text.
  - `send_email` in console mode emits `auth_email_console` at INFO (redacted) and the raw body at DEBUG only. Never use `print()` for user data.
  - User-supplied strings are bounded by `Field(max_length=...)` module-level constants in `app/schemas/auth.py` (`EMAIL_MAX`, `PASSWORD_MAX`, `FULL_NAME_MAX`, `BETA_KEY_MAX`). Adding a new user field without a cap is a regression.
  - Auth routes require `Request` as first positional arg for slowapi; tests use keyword args + `limiter.enabled = False` fixture.
