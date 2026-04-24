# HR Assist

**AI-assisted resume intelligence and job matching platform.**

> Upload a resume — get a structured candidate profile, a ranked shortlist of real vacancies, a per-vacancy "why shown" explanation, and a gap analysis of the skills you are missing. Feedback on each vacancy (shortlist / blacklist / like / dislike) is time-decayed and fed back into ranking.

> Russian version: [README.ru.md](README.ru.md).

---

## Overview

HR Assist is an end-to-end system for jobseekers. A user uploads a PDF or DOCX resume; the platform extracts text, runs a structured LLM analysis, infers an approximate seniority grade, pulls live vacancies from the hh.ru API, embeds both sides into Qdrant, and ranks the results with a multi-stage semantic matcher. For every vacancy the user sees why it was recommended and which skills are missing to reach the bar. Shortlist, blacklist, like and dislike signals are weighted by time decay and feed back into future ranking.

The platform runs locally on Docker Compose and is deployed to a dedicated server for closed-beta use.

## Value proposition

- **For the jobseeker:** turns a raw resume into a ranked, explained shortlist of real vacancies — instead of keyword search on job boards.
- **For the hiring manager reading this repo:** a full-stack AI product that treats matching as a search / retrieval problem with an eval bar in CI, not a single embedding-similarity call behind a UI.

## Key features

| | |
|---|---|
| **Resume parsing** | PDF/DOCX → plain text → structured profile (role, grade, hard/soft skills, domains, experience). |
| **AI resume analysis** | LLM breakdown: strengths, growth zones, risks, concrete improvement suggestions. |
| **Skill extraction & grade inference** | Normalised against an RU↔EN skill taxonomy with ESCO-based role classification. |
| **Semantic vacancy matching** | Qdrant vector index plus a multi-stage matcher: pre-filter, domain gate, skill-overlap floor, MMR diversity, cross-encoder / LLM rerank. |
| **Gap analysis** | Per-vacancy "why shown" and the exact skills the user is missing. |
| **Feedback loop** | Shortlist / blacklist / like / dislike, weighted by time decay, influence future ranking. |
| **Application tracker** | Kanban flow (Applied → Replied → Interviewing → Rejected) with AI-generated cover letters. |
| **Vacancy sourcing** | Live hh.ru API fetch into an internal vacancy index, parallelised with LLM parsing. Additional source adapters (SuperJob, Habr Career) are present in the code but off by default. |
| **Preference profile** | Work format, relocation, target roles, salary — stored per user and factored into ranking. |
| **Admin panel** | User management, funnel telemetry, technical statistics. |

## How it works

```
Upload resume (PDF/DOCX)
        ↓
Extract text (pypdf / python-docx)
        ↓
Structured LLM analysis (role, grade, skills, domains)
        ↓
Embed resume profile → Qdrant
        ↓
Fetch live vacancies (hh.ru API) → embed → Qdrant
        ↓
Multi-stage semantic matching (domain gate, skill floor, MMR, rerank)
        ↓
Ranked shortlist with "why shown" + missing-skills explanation
        ↓
User feedback (shortlist / blacklist / like / dislike)
        ↓
Feedback decayed over time, fed back into ranking
```

## Architecture

```mermaid
flowchart LR
  UI["Next.js UI"] --> API["FastAPI"]
  API --> PG[("PostgreSQL")]
  API --> QD[("Qdrant")]
  API --> OAI["OpenAI API"]
  API --> HH["hh.ru API"]
```

Three stateful stores, one application boundary:

- **PostgreSQL** — source of truth for users, resumes, vacancies, applications, feedback, telemetry.
- **Qdrant** — dense vector store for resume and vacancy embeddings.
- **OpenAI** — LLM analysis and embeddings; a local cross-encoder handles rerank.
- **FastAPI** owns all business logic; the Next.js frontend is a thin UI layer over the REST API.

Deeper dive: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Rerank notes: [`docs/RERANK.md`](docs/RERANK.md). ESCO role classification: [`docs/ESCO.md`](docs/ESCO.md).

## Tech stack

- **Backend:** FastAPI, SQLAlchemy 2, Alembic, Pydantic, slowapi
- **AI layer:** OpenAI (analysis + embeddings), sentence-transformers (local cross-encoder rerank)
- **Data:** PostgreSQL 16, Qdrant 1.13
- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind v4, shadcn/ui, Radix
- **Infra:** Docker Compose, GitHub Actions CI, SSH-based CD
- **Auth:** JWT + email OTP + beta-key gate

## Running locally

```bash
cp .env.example .env.local
# Fill in at least OPENAI_API_KEY, JWT_SECRET_KEY, BETA_TESTER_KEYS
# Leave AUTH_EMAIL_DELIVERY_MODE=console to read OTP codes from backend logs.

docker compose up -d --build
```

Services:

- UI — http://localhost:3000
- API docs — http://localhost:8000/docs
- Health — http://localhost:8000/health
- Qdrant dashboard — http://localhost:6333/dashboard

Alembic migrations run automatically when the backend container starts.

## Environment variables

Full reference: [`.env.example`](.env.example). Minimum to run:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | LLM + embeddings |
| `OPENAI_ANALYSIS_MODEL` | Model used for resume / vacancy analysis |
| `OPENAI_MATCHING_MODEL` | Model used for detailed matching + rerank |
| `OPENAI_EMBEDDING_MODEL` | Embedding model (defaults to `text-embedding-3-large`) |
| `JWT_SECRET_KEY` | JWT signing secret |
| `BETA_TESTER_KEYS` | Comma-separated list of accepted beta keys |
| `AUTH_EMAIL_DELIVERY_MODE` | `console` for local dev, `smtp` for production |
| `DATABASE_URL` | PostgreSQL connection string |
| `QDRANT_URL` | Qdrant endpoint |
| `OPENAI_REQUEST_BUDGET_USD` | Per-request spend cap (enforced when `OPENAI_ENFORCE_REQUEST_BUDGET=true`) |

Optional source adapters (`HH_API_TOKEN`, `SUPERJOB_API_KEY`, `HABR_CAREER_API_TOKEN`, `BRAVE_API_KEY`) can be left empty — the platform works against public hh.ru endpoints without them.

## API / system notes

- **Auth flow:** register → verify email → `POST /api/auth/login/start` (email + password) → `POST /api/auth/login/verify` (OTP + challenge). Protected endpoints require a verified email.
- **Rate limiting:** slowapi on auth endpoints to contain brute-force.
- **Prompt-injection guard:** untrusted resume and vacancy text is sanitised before being handed to the LLM (`app/services/llm_guard.py`).
- **Cost guard:** per-user daily OpenAI spend budget stops runaway usage (`app/models/user_daily_spend.py`).
- **Observability:** structured logs, impression / click / dwell telemetry on matching results (`app/services/match_telemetry.py`).
- **Matching eval harness:** labelled gold pairs with NDCG / MAP / MRR floors enforced in CI (`backend/tests/test_matching_eval_*`).

## Current status

Closed-beta MVP. The end-to-end flow runs in production on a dedicated server.

### What works now

- Registration + email-OTP auth behind a beta-key gate
- PDF / DOCX upload, parse, structured LLM analysis, skill and grade extraction
- Live hh.ru fetch, embed, Qdrant index
- Multi-stage semantic matching with "why shown" and missing-skills explanation
- Shortlist / blacklist / like / dislike with time-decayed influence on ranking
- Application tracker (Kanban) with AI-generated cover letters
- Admin panel, user preference profile, funnel telemetry
- Docker Compose local stack, GitHub Actions CI, SSH-based CD to production

### Planned next

- Salary predictor (field and badge are wired; predictor activates once the vacancy corpus grows)
- Additional vacancy source adapters switched on in production
- Public launch (sub-1.0 version is intentional while in closed beta)

## Roadmap

Full release log: [`docs/ROADMAP.md`](docs/ROADMAP.md). Recent highlights:

- `v0.9.1` — Admin overview: users/resumes/vacancies totals, last-24h active users, top searched roles, live active-jobs list with admin cancel for any user
- `v0.9.0` — Privacy minimization (Level A): PII scrubber, no raw resume text persisted, uploaded file deleted after analysis, no identifiers in Qdrant payload — see [`PRIVACY.md`](PRIVACY.md)
- `v0.8.x` — Design-system rewrite (Tailwind v4 + shadcn), admin panel, linear workspace flow, UI/UX polish
- `v0.7.0` — Matching quality overhaul: multi-stage matcher, MMR diversity, ESCO role gate, cross-encoder rerank, eval harness with CI floors
- `v0.6.0` — First-run rescue: bigger cold index, parallel HH fetch + LLM parse, strong / maybe tier split
- `v0.5.0` — HH cursor for freshness, skill taxonomy, user override controls
- `v0.1.0 – v0.4.0` — Foundation, actionability, multi-profile + time decay, IT / non-IT domain gate

## Demo

Live demo: **https://aijobmatch.ru** — closed beta, access gated by beta-key.

## Repository structure

```
backend/
  app/
    api/            FastAPI routes
    services/       Business logic (matching, analysis, sourcing, embeddings, guard, telemetry)
    models/         SQLAlchemy models
    repositories/   Persistence layer
    schemas/        Pydantic DTOs
    core/           Config, security, logging
  alembic/          DB migrations
  tests/            Pytest suite (unit + integration)
frontend/
  app/              Next.js routes (home, applications, admin, vacancies, resume-analysis, funnel)
  components/       UI components
  lib/              API client, hooks
  styles/           Global styles + Tailwind config
  types/            Shared TS types
docs/               Architecture, roadmap, rerank, ESCO notes
.github/workflows/  CI (ci.yml) + CD (cd.yml)
docker-compose.yml
```

## Why this project matters

Most "AI resume" tools stop at surface-level feedback. HR Assist is built as a real search / retrieval system:

- A matcher that has to beat a measurable eval bar in CI, not just look plausible.
- Explicit handling of the ways semantic search breaks in practice — cross-domain leakage, noise floor, skill-overlap gate, grade mismatch, MMR for diversity.
- A feedback loop that actually changes ranking, with time decay so stale signals fade.
- Production concerns up front: prompt-injection guard, per-user cost budget, rate limiting, structured logs, health checks.

Full-stack AI product — retrieval, LLM orchestration, evaluation, UX, ops — not a notebook.

## Design decisions

- **Qdrant over pgvector** — vector and relational workloads scale independently.
- **Multi-stage matcher instead of a single embedding similarity call** — cosine alone is not enough; domain gates and skill floors kill cross-domain false positives before they reach the user.
- **Eval harness in CI** — matching quality is a regression surface, not a vibe check.
- **Time-decayed feedback** — last month's preferences should outweigh last year's; a linear aggregate does not.
- **Thin frontend, thick backend** — the UI holds no business logic; everything testable lives behind the FastAPI boundary.

## Privacy

HR Assist is built to persist the minimum amount of personal data. Resume text is PII-scrubbed before it reaches the LLM, the uploaded file is deleted immediately after analysis, and the vector store holds no identifiers — see [`PRIVACY.md`](PRIVACY.md) for the exhaustive list of what is and is not stored.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

See [`SECURITY.md`](SECURITY.md) for the disclosure process.

## License

No license has been published yet — the repository is shared for portfolio and hiring review. Please contact the author before reusing the code.
