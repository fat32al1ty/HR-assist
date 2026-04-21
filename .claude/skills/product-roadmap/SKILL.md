---
name: product-roadmap
description: The staged delivery plan for HR-Assist — a jobseeker-facing AI assistant that replaces paid services like hh.ru Premium and career coaches. Six phases (Foundation → Actionability → Retention → Value-Add → Frontend → Infra → Quality), each stored as its own file with tasks, files-to-touch, and acceptance criteria. Consult this skill at the start of any work session touching product scope, architecture, or prioritisation. Update the checkboxes as work lands.
---

# HR-Assist product roadmap

This skill captures the long-form plan for HR-Assist. The conversation that produced it happens rarely; we lean on this file instead of re-discovering scope.

**Audience of the product:** the jobseeker. The user loads a resume, we find and rank vacancies across hh.ru / SuperJob / Habr Career / Brave, the user applies and prepares for interviews. We compete with hh.ru Premium (~5 k ₽/mo), career coaches (10–30 k ₽/one-off), and getmatch-style AI aggregators.

**What this plan is NOT:**
- Not a monetization plan — billing, paywalls, and tiers are out of scope.
- Not a marketing plan — we are not covering SEO, ads, referrals here.
- Not an infra migration — we do not chase microservices, Celery, or K8s.

## How to work with this skill

1. **Starting a work session?** Read the relevant phase file. Each phase file is self-contained: context, tasks, files touched, acceptance criteria, suggested commit message.
2. **Making a product decision that affects multiple phases?** Record it in `DECISIONS.md` as a short entry so the next session sees the reason, not just the outcome.
3. **Landing a task?** Flip its checkbox in the phase file (`- [ ]` → `- [x]`) and, when a phase is fully done, move that phase into a "completed" marker at the top of the phase file. Do NOT delete completed tasks — we need them as history.
4. **Phases are ordered but not strictly serial** — Phase 0 must happen first (it closes real holes). After that, Phases 1 → 3 are the product story; Phase 4 (frontend refactor) can start in parallel once Phase 1 tasks push page.tsx past the complexity cliff; Phases 5 and 6 are ongoing.

## Phase index

| Phase | File | Status | One-line goal |
|---|---|---|---|
| 0 — Foundation | [phase-0-foundation.md](phase-0-foundation.md) | completed 2026-04-21 | Close security / cost / audit gaps before any new feature. |
| 1 — Actionability | [phase-1-actionability.md](phase-1-actionability.md) | not started | Turn "view 20 matches" into "apply, track, and understand." |
| 2 — Retention | [phase-2-retention.md](phase-2-retention.md) | not started | Make the user come back without being reminded by us manually. |
| 3 — Value-add | [phase-3-value-add.md](phase-3-value-add.md) | not started | Features a career coach would charge 10 k ₽ for: interview prep, gap analysis, salary insight. |
| 4 — Frontend refactor | [phase-4-frontend.md](phase-4-frontend.md) | not started | Break `page.tsx` (1318 lines, 30+ useStates) into routable, testable pieces; add mobile layout. |
| 5 — Infra & data | [phase-5-infra.md](phase-5-infra.md) | not started | Kill N+1 queries, bound large fields, persist the job queue across restarts. |
| 6 — Quality & observability | [phase-6-quality.md](phase-6-quality.md) | ongoing | Integration tests for end-to-end flows; structured logs for every OpenAI call and every user action that spends budget. |

[DECISIONS.md](DECISIONS.md) — running log of cross-phase choices and why we made them.

## Cross-cutting principles

- **Tests use real Postgres + Qdrant, not mocks.** That's already the convention. Adding tests that mock the DB breaks the convention — don't.
- **No backwards-compat shims.** Beta means we change shapes freely; update the frontend in the same PR.
- **One PR = one phase step.** Don't bundle "rate-limit + cover-letter + mobile layout" — review cost explodes and rollback is painful.
- **Fail loudly.** If a task says "add structured logging," the logs must be queryable (`grep OPENAI_CALL`), not wrapped in a try/except that swallows them.
- **Don't touch the OpenAI antizapret proxy from feature code.** All calls already go through `OPENAI_BASE_URL`; that's the only coupling. If you need to change that, use the `antizapret-openai-proxy` skill.

## When the plan is wrong

The plan is a living document. If a task is no longer relevant (product pivot, external change, learning from Phase N−1), mark it `- [~]` with a one-line note on why it was dropped. Record the reasoning in `DECISIONS.md`.
