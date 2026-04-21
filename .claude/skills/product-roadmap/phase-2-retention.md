# Phase 2 — Retention

**Goal:** make a user who got value in Phase 1 come back next week without us nudging them manually. A jobseeker may not feel like visiting the site every day, but they will click an email that says "3 new matches at 90%+."

**Prerequisite:** Phase 1 is live — we need applications and match cards before "new match for you" is meaningful.

## Tasks

### 2.1 Saved search / persistent profile
- [ ] Add `saved_searches(id, user_id, name, resume_id, filters_json, created_at)`. Filters = the user's preferences from Phase 1 (salary floor, location, remote, seniority hints).
- [ ] Every recommendation run records which saved_search it ran against. A user can have up to 3 saved searches on free tier.
- [ ] Minimal UI: "Сохранить как поиск" button at the top of results. A dropdown in the header selects active search; swapping re-runs against cached matches (no OpenAI cost) and only opens a fresh job on explicit "Обновить."

**Files:** new migration, `backend/app/models/saved_search.py`, `backend/app/repositories/saved_searches.py`, `backend/app/api/routes/recommendations.py` (or vacancies), `frontend/app/page.tsx`.
**Acceptance:** save a search, log out, log back in, find the same search + same cached match list ready to view.
**Suggested commit:** `feat(search): saved searches and named profiles`

### 2.2 Shortlist ("подумать потом")
- [ ] Three-way feedback: keep `like`/`dislike`, add `shortlist`. Store in the existing `vacancy_feedback` table; migrate the enum.
- [ ] Frontend: bookmark icon on each match card → moves to a "Избранное" section visible from the sidebar. Reminder: shortlist items are excluded from the "new matches" counter so the user isn't re-prompted about them.

**Files:** migration for enum, `backend/app/models/vacancy_feedback.py`, `backend/app/schemas/vacancy.py`, `frontend/app/page.tsx`.
**Acceptance:** shortlist 3 items, switch tab, return, list is intact. Like/dislike flows remain unchanged.
**Suggested commit:** `feat(feedback): shortlist as third feedback state`

### 2.3 Email digest of new matches
- [ ] New scheduled worker (one more thread in `recommendation_jobs.py`'s executor, or a separate module using `schedule` library or a bare `asyncio.create_task` loop). Default cadence: daily at 09:00 Europe/Moscow.
- [ ] For each active user with at least one saved search: re-run the vacancy discovery in a lightweight mode (no Brave search, only re-query hh/sj/habr for new vacancies since last digest). Score new vacancies against the user's resume. If ≥1 match at ≥85%, send digest.
- [ ] Digest email content: top 5 new matches with title, company, short "почему подходит" (matched_skills summary, reuse Phase 1.1 output). CTA links back to the site with `?utm_source=digest&job=<match_id>`.
- [ ] Frequency cap: never more than one digest per user per 24 h. Unsubscribe link in every email.
- [ ] Budget: this flow counts against the daily per-user OpenAI budget (Phase 0.3). If the user has already spent their budget today via manual searches, the digest is skipped.

**Files:** new `backend/app/services/email_digest.py`, `backend/app/services/scheduler.py` (if needed), `backend/app/api/routes/users.py` for unsubscribe, alembic for `users.digest_opt_out` boolean.
**Acceptance:** trigger the digest worker manually, a real user receives an email with ≥1 match, clicking the unsubscribe link stops further digests.
**Suggested commit:** `feat(notifications): daily digest of new high-match vacancies`

### 2.4 In-app "what's new" since last visit
- [ ] Cheap parallel to email: on login, if new matches arrived since the user's last session, show a banner: "За последние X дней найдено N новых вакансий с совпадением ≥ 85%."
- [ ] Track `users.last_seen_at`; compute "new since" server-side so the frontend is presentational.

**Files:** `backend/app/api/routes/auth.py` (update last_seen_at on login), `backend/app/api/routes/users.py` (`GET /users/me/whats-new`), `frontend/app/page.tsx`.
**Acceptance:** log in after a digest ran, see the banner with the correct count.
**Suggested commit:** `feat(retention): what's-new banner on login`

### 2.5 Lightweight notification preferences
- [ ] `users.notification_prefs_json` with: `digest_enabled`, `digest_frequency` (daily/weekly), `min_match_threshold` (default 85).
- [ ] Settings page with three controls. Server-side default is digest enabled, daily, 85%.

**Files:** alembic, `backend/app/api/routes/users.py`, `frontend/app/page.tsx` (or new settings route).
**Acceptance:** user sets weekly + 90% threshold, next digest run respects both.
**Suggested commit:** `feat(retention): notification preferences`

## Definition of done

All tasks merged. Dogfood over 3 days on prod:
1. Two users saved distinct searches.
2. At least one user received a real email digest with ≥1 vacancy that matched ≥ 85%.
3. Unsubscribe link works; preferences page changes behaviour on the next digest cycle.
4. "What's new" banner appears on re-login and shows the right count.

Update `SKILL.md` phase status to "completed YYYY-MM-DD."
