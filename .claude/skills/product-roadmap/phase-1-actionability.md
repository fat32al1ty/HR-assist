# Phase 1 — Actionability

**Goal:** turn the product from "view 20 matches, then leave" into "find, apply, track." This is the single biggest lever because every competitor's paid tier is built on the things we're adding here.

**User story that must work end-to-end at the end of this phase:** "I uploaded my resume on Monday, the system found 18 vacancies, I applied to 4 of them with AI-drafted cover letters, and on Thursday I can see which ones have been viewed, replied to, or ignored — all without leaving the site."

## Tasks

### 1.1 Show what matched, not only what's missing
- [ ] Backend: `matching_service.py` already computes which resume skills align with a vacancy; surface them as `matched_skills: list[str]` and `matched_requirements: list[str]` in `VacancyMatchRead`. Limit to top 10 each to keep the payload reasonable.
- [ ] Frontend: in the match card, show two columns: **"Ты подходишь"** (checkmark, green) lists matched_skills, **"Чего не хватает"** (dash, amber) lists missing_requirements. Never show an empty "Ты подходишь" — if empty, show "совпадение по ключевым словам в описании" as a fallback explanation.

**Files:** `backend/app/services/matching_service.py`, `backend/app/schemas/vacancy.py`, `frontend/app/page.tsx` (or new match-card component).
**Acceptance:** the UI visibly renders 2+ "matched" items on the first match in a fresh run; screenshotable before/after.
**Suggested commit:** `feat(matching): show matched skills alongside gaps for trust`

### 1.2 Self-check after resume parsing
- [ ] After a resume upload is analysed, show a summary card: "мы распознали тебя как: **Senior Python backend / 5 лет / финтех**. Всё верно? [Подтвердить] [Подправить]."
- [ ] Editing opens a minimal form over the main analysis (role title, years, top 3 skills, seniority). Saving writes back to `resumes.analysis` JSONB.
- [ ] Until the user confirms OR edits, the "найти работу" button is disabled. This prevents bad parses from triggering a 5-minute search.

**Files:** `backend/app/api/routes/resumes.py` (PATCH endpoint for analysis overrides), `frontend/app/page.tsx`.
**Acceptance:** uploading a garbage PDF surfaces "roles: -, years: 0" and the user can correct it in one step.
**Suggested commit:** `feat(resume): self-check gate before first search`

### 1.3 Cancel a running recommendation job
- [ ] Backend endpoint `DELETE /vacancies/recommend/{job_id}`. Atomically transitions `queued`/`running` → `cancelled`. Running worker polls a flag once per stage and exits cleanly; partial results are discarded.
- [ ] Frontend: show a "Отменить" button next to the progress bar. After click, button becomes disabled and progress label reads "Останавливаем..." until the worker confirms cancellation.

**Files:** `backend/app/api/routes/vacancies.py`, `backend/app/services/recommendation_jobs.py`, `backend/app/models/recommendation_job.py`, `frontend/app/page.tsx`.
**Acceptance:** click cancel at the 10% mark → within 30s job status is `cancelled`, UI returns to the "запустить подбор" state.
**Suggested commit:** `feat(jobs): allow cancelling a running recommendation job`

### 1.4 Application tracker
- [ ] New tables: `applications(id, user_id, vacancy_id, status, cover_letter_text, source_url, applied_at, last_status_change_at, notes)`. Status enum: `draft`, `applied`, `viewed`, `replied`, `rejected`, `interview`, `offer`, `declined`.
- [ ] Endpoints: `POST /applications` (creates), `PATCH /applications/{id}/status`, `GET /applications?status=...`.
- [ ] Frontend: new "Мои отклики" tab with a four-column kanban (`applied → viewed → interview → offer`). Cards show vacancy title, company, applied_at, latest note. Drag-and-drop not required for MVP — use a status dropdown.
- [ ] Status changes can be manual (user says "мне ответили" / "отказали"). Automatic detection is Phase 3+ if hh.ru scraping is cheap.

**Files:** new `backend/alembic/versions/<new>_applications.py`, `backend/app/models/application.py`, `backend/app/repositories/applications.py`, `backend/app/api/routes/applications.py`, `backend/app/schemas/application.py`, `frontend/app/page.tsx` (or new route).
**Acceptance:** apply to 2 vacancies from the match list, both appear in "Мои отклики" under "Отправлено"; change one to "Отказали", kanban updates, refresh persists.
**Suggested commit:** `feat(applications): kanban tracker for jobseeker follow-up`

### 1.5 AI-generated cover letter
- [ ] New endpoint `POST /applications/{id}/cover-letter` that calls OpenAI with (resume analysis + vacancy description + user tone preference: formal / casual). Returns a draft the user can edit before sending.
- [ ] System prompt must forbid inventing experience; wrap user/vacancy text with `llm_guard.wrap_untrusted_text`.
- [ ] Budget: 1 call per application per 24 h (cache the last draft). Count against the Phase 0.3 daily budget.
- [ ] Frontend: "Сгенерировать сопроводительное" button in the application detail. Show the draft in a textarea, let user edit, "Скопировать" to clipboard. No automatic sending for MVP — the user pastes it into hh.ru themselves. Direct hh.ru API integration is Phase 3+.

**Files:** `backend/app/services/cover_letter.py` (new), `backend/app/api/routes/applications.py`, `frontend/app/page.tsx`.
**Acceptance:** generate a cover letter for a real vacancy; the result mentions 2+ concrete requirements from the vacancy and 2+ concrete facts from the resume; it is ≤ 250 words; it costs < $0.02.
**Suggested commit:** `feat(applications): AI-drafted cover letter per vacancy`

### 1.6 Quick "apply" shortcut from match card
- [ ] Under each match card, alongside "Открыть источник", add a **"Откликнуться"** button. Click:
  1. Creates an `application` with status=`draft`, linked to that vacancy.
  2. Opens the application detail view focused on the cover-letter step.
- [ ] After user copies the letter and clicks "Я откликнулся на hh", the status transitions to `applied` and the card gets a small "✓ отклик отправлен" pill.

**Files:** `frontend/app/page.tsx`, no backend changes beyond Phase 1.4.
**Acceptance:** one-click from match to draft cover letter, two clicks to the "applied" state.
**Suggested commit:** `feat(ui): apply shortcut from match card`

## Definition of done

All six tasks merged, CI green. Dogfood on prod:
1. Upload a real CV, self-check surfaces and can be edited.
2. Run recommendations, cancel mid-job, confirm state returns cleanly.
3. From 3 match cards, generate cover letters and move each application through the kanban.
4. All three cover letters cost under $0.05 combined and none hallucinate experience.

When all done, flip the phase status in `SKILL.md`.
