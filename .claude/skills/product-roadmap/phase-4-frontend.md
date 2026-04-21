# Phase 4 — Frontend refactor

**Goal:** make the frontend maintainable and mobile-usable. After Phases 1–3, `page.tsx` is unmaintainable (it was already at the limit at 1318 lines before adding applications, tracker, interview-prep, gap analysis, etc.). This phase does not add product features; it makes further features cheap.

**Non-goal:** no framework change. We stay on Next.js App Router + React 19. No Redux, MobX, or other external state store.

## Tasks

### 4.1 Split `page.tsx` by route
- [ ] Adopt Next.js App Router with per-feature folders. Target structure:
  ```
  app/
    layout.tsx         # shell (nav, auth gate)
    page.tsx           # dashboard landing (resume + main CTA)
    resumes/page.tsx
    matches/page.tsx   # results view + feedback
    applications/page.tsx   # kanban
    settings/page.tsx
    public/matches/[token]/page.tsx
  ```
- [ ] Each route is < 300 lines by the end of this task. Extract presentational components into `components/` and feature-specific hooks into `lib/hooks/`.

**Files:** extensive; start from current `frontend/app/page.tsx`.
**Acceptance:** no file in `frontend/app/` or `frontend/components/` exceeds 300 lines. Navigation between routes preserves auth state.
**Suggested commit:** `refactor(frontend): route-based split of monolithic SPA`

### 4.2 Extract auth context
- [ ] Single `AuthProvider` in `layout.tsx` holding `{user, tokens, login, logout, isLoading}`.
- [ ] Protected routes check the context and redirect to `/login` if unauthenticated. Login state survives hard refresh via localStorage token hydration.
- [ ] Replace every direct `localStorage.getItem('jwt')` call in feature code with `useAuth()`.

**Files:** `frontend/app/providers/auth-context.tsx`, `frontend/app/layout.tsx`, everywhere tokens are currently read.
**Acceptance:** grep for `localStorage` in `frontend/app/` outside `auth-context.tsx` returns nothing token-related.
**Suggested commit:** `refactor(frontend): auth context replaces scattered token reads`

### 4.3 Replace scattered fetches with tanstack-query
- [ ] Add `@tanstack/react-query`. One query client in the root provider. Replace manual `useEffect`+`useState`+`fetch` triples with `useQuery` / `useMutation` hooks.
- [ ] Standardise error handling: hooks throw typed `ApiError` that the UI renders via a shared `<ErrorBoundary>` with Russian-friendly messages.
- [ ] Cache policy: vacancy matches 2 min, user profile 10 min, job status 2 s while running then invalidated on completion.

**Files:** `frontend/app/providers/query-client.tsx`, `frontend/lib/api-client.ts`, feature-level hooks `useMatches`, `useApplications`, `useJobStatus`, etc.
**Acceptance:** no feature component calls `fetch` directly; error toasts come from one place.
**Suggested commit:** `refactor(frontend): tanstack-query for all server state`

### 4.4 Job state reducer
- [ ] Replace the ~10 job-related useStates with a single reducer (`idle | queued | running | completed | cancelled | failed`). Live updates from the status endpoint feed the reducer; UI renders off it.
- [ ] LocalStorage restore rejects non-UUID job IDs and states older than 30 min → starts fresh instead of reviving a stale job.

**Files:** `frontend/lib/hooks/useRecommendationJob.ts`.
**Acceptance:** planting a malformed job id in localStorage, reload, app starts clean.
**Suggested commit:** `refactor(frontend): state machine for recommendation job lifecycle`

### 4.5 Mobile layout
- [ ] Breakpoints: mobile < 768, tablet 768-1024, desktop > 1024. Current layout stacks okay with CSS flex but is not readable on mobile.
- [ ] Specific fixes:
  - Sidebar collapses into a bottom tab bar on mobile.
  - Match cards: two-column layout on desktop, single column on mobile with "Открыть источник" + "Откликнуться" as full-width stacked buttons.
  - File input gets a custom styled button with file-name + size preview for all sizes.
  - Any four-button row stacks vertically under 480 px.
- [ ] Test on a real phone (not just devtools); iOS Safari and Android Chrome. Document any platform quirks in `frontend/README.md`.

**Files:** styles across new components.
**Acceptance:** manual dogfood on two real phones: login, upload, run a match, open application, cancel → none of the flows require horizontal scrolling or pinch-zoom.
**Suggested commit:** `feat(frontend): mobile-first responsive layout`

### 4.6 Empty states, skeletons, toasts
- [ ] Every list view has an explicit empty state with a CTA: "Пока нет откликов — загрузите резюме и начните подбор."
- [ ] Loading-skeleton components for match list, application kanban, digest cards.
- [ ] Single shared toast component for success/error/info. Use it after: cover letter copied, application status changed, digest preferences saved.

**Files:** `frontend/components/empty-state.tsx`, `frontend/components/skeleton/*.tsx`, `frontend/components/toast.tsx`.
**Acceptance:** every route has a non-empty UX when data is empty and a non-blocking UX when data is loading.
**Suggested commit:** `feat(frontend): empty states, skeletons, and shared toasts`

### 4.7 Hide engineer-facing details from users
- [ ] Remove the Qdrant status box and background-warmup section from the main view — keep them accessible at `/settings/debug` if a user appends `?debug=1`.
- [ ] Replace "job ID" visible strings with a friendly "поиск от 12:34" timestamp unless `?debug=1`.
- [ ] Replace "быстрый подбор / обновить базу" with one button **"Найти работу"** that auto-picks mode based on cache age.

**Files:** `frontend/app/page.tsx`, `frontend/app/settings/debug/page.tsx`.
**Acceptance:** a non-technical dogfooder walks through the app for 5 min without asking "what is Qdrant?"
**Suggested commit:** `refactor(frontend): hide infrastructure jargon from the main UI`

## Definition of done

All routes split, tanstack-query everywhere, auth context single source, mobile-tested on two real devices, no file > 300 lines. One non-technical person (not the builder) completes the full journey (signup → upload → match → apply → interview prep) on their phone without help.

Update `SKILL.md` phase status.
