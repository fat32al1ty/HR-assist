# Phase 3 — Value-Add

**Goal:** ship the three features career coaches and hh.ru Premium are charging people for. Each one stands alone; pick in priority order but don't let any block the others.

## Tasks

### 3.1 Interview prep per vacancy
- [ ] Endpoint `POST /vacancies/{id}/interview-prep`. Returns a structured pack: `expected_questions: list[str]` (10 items, mixed behavioural + technical), `weak_points: list[{topic, why, mitigation}]` (3-5), `salary_range_note: str` (short positioning advice). All generated in one OpenAI call with strict JSON schema.
- [ ] Inputs: vacancy analysis + resume analysis + user's self-assessed strengths (from Phase 1.2 self-check).
- [ ] Cached for 7 days per `(user_id, vacancy_id)`. Budget: hard cap $0.05 per pack.
- [ ] Frontend: in the application detail view, a "Подготовка к собеседованию" tab. Collapsible question list with a textarea under each to save the user's own answer draft.

**Files:** new `backend/app/services/interview_prep.py`, `backend/app/api/routes/vacancies.py`, `frontend/app/page.tsx`.
**Acceptance:** generate a pack for a real Python developer vacancy; questions reference technologies from the vacancy, weak_points cite gaps from the resume analysis, total cost < $0.05.
**Suggested commit:** `feat(vacancies): AI interview prep per vacancy`

### 3.2 Career gap analysis
- [ ] New endpoint `GET /users/me/gap-analysis`. Aggregates `missing_requirements` across the user's entire match history for the active saved search, ranks skills by frequency and by average match-score delta (i.e. "if you learned X, your average match would rise by Y%").
- [ ] Returns top 5 suggested skills, each with: skill name, count of vacancies where missing, estimated match-score lift, optional learning link (editable by admin later; MVP returns placeholder links).
- [ ] Runs entirely from existing data — no new OpenAI calls. This is pure aggregation.
- [ ] Frontend: "Твой план развития" card on the main page showing the 5 skills as a ranked list.

**Files:** `backend/app/services/gap_analysis.py`, `backend/app/api/routes/users.py`, `frontend/app/page.tsx`.
**Acceptance:** for a user with ≥ 20 matches, gap-analysis returns 5 non-empty, relevant skills with numeric lift estimates.
**Suggested commit:** `feat(users): aggregated career gap analysis`

### 3.3 Salary insight
- [ ] `GET /users/me/salary-insight`. Computes: median, p25, p75, p90 of salary fields across matches in the active saved search. Filters out vacancies where salary is missing (common) before computing.
- [ ] Returns per-source breakdown: hh median separately from sj median; this is a quality signal (hh tends to over-report, sj to under-report) that a sophisticated user appreciates.
- [ ] If fewer than 10 matches have salary data, return a "недостаточно данных" state — don't invent numbers.
- [ ] Frontend: salary-insight card on the main page; side-by-side bar chart of the user's expected salary (self-reported in resume) vs. p25/p75/p90 of the market.

**Files:** `backend/app/services/salary_insight.py`, `backend/app/api/routes/users.py`, `frontend/app/page.tsx` (consider using `recharts` if it's not already in — keep charts minimal).
**Acceptance:** card shows at least p25/p50/p75 for an established search with > 20 salaried vacancies; shows insufficient-data state for a new user.
**Suggested commit:** `feat(users): market salary insight from match corpus`

### 3.4 Resume quality hints
- [ ] Cross-reference the user's resume analysis against the aggregated top-N keywords from matched vacancies. If a keyword appears in ≥ 40% of matches but not in the resume, flag it: "в резюме нет упоминания CI/CD — в 12 из 20 вакансий это ключевое требование."
- [ ] Offer short rewrite suggestions via OpenAI for the two top gaps only (budget-aware). Suggestion output = rewritten bullet + original bullet, user picks.
- [ ] Frontend: section in the resume detail view "Подсказки по резюме" with the 2 rewrites and 3 keyword hints.

**Files:** `backend/app/services/resume_quality.py`, `backend/app/api/routes/resumes.py`, `frontend/app/page.tsx`.
**Acceptance:** given a resume missing common keywords ("Docker", "REST"), the service returns both as hints with concrete rewrite suggestions.
**Suggested commit:** `feat(resume): keyword gap hints vs. active market`

### 3.5 Share a match report (read-only)
- [ ] `POST /matches/share` creates a token, returns a URL `/public/matches/{token}`. Default expiry 7 days, revocable.
- [ ] `GET /public/matches/{token}` returns a sanitised snapshot: top 5 matches, no user personal data beyond first name, no resume text.
- [ ] Frontend: "Поделиться подборкой" button in results; the resulting URL opens a read-only public page.

**Files:** `backend/app/models/match_share.py`, `backend/app/api/routes/public.py`, new `frontend/app/public/matches/[token]/page.tsx`.
**Acceptance:** create a share link, open in incognito, see the 5 matches but no resume text or email; revoke the link, link shows "недоступно."
**Suggested commit:** `feat(sharing): read-only public link to a match shortlist`

## Definition of done

3.1, 3.2, 3.3 shipped and dogfooded on a real user journey: run a recommendation, look at gap-analysis, check salary insight, open interview-prep for two vacancies, edit resume based on hints. 3.4 and 3.5 are nice-to-have; don't block the phase on them but schedule them before Phase 4 if bandwidth allows.

Update `SKILL.md` phase status.
