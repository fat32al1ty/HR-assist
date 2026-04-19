# Resume Intelligence Platform

Enterprise-oriented resume analysis platform.

## Stage 1 scope

- FastAPI backend
- PostgreSQL persistence
- JWT authentication
- PDF and DOCX resume uploads
- Text extraction
- OpenAI-powered structured resume analysis
- Qdrant vector database for semantic resume and vacancy matching
- Next.js personal dashboard
- Docker Compose local runtime

## Run with Docker

Create a local secrets file first:

```powershell
Copy-Item .env.example .env.local
```

Then fill `.env.local`. For resume analysis, set:

```env
OPENAI_API_KEY=sk-...
OPENAI_ANALYSIS_MODEL=gpt-5.4-mini
OPENAI_MATCHING_MODEL=gpt-5.4
OPENAI_REASONING_EFFORT=none

# Vacancy sources (API-first)
SUPERJOB_API_KEY=...
SUPERJOB_VACANCIES_URL=https://api.superjob.ru/2.0/vacancies/
HABR_CAREER_API_URL=https://career.habr.com/api/v1/vacancies
```

By default vacancy discovery now works in tokenless mode from public vacancy pages (HH/Habr/SuperJob parsing).
If source API keys are configured later, the backend will also use official API endpoints.

Start the stack:

```powershell
docker compose up -d --build
```

Frontend: http://localhost:3000

Backend API: http://localhost:8000/docs

Health: http://localhost:8000/health

Config check: http://localhost:8000/api/system/config-check

Qdrant dashboard: http://localhost:6333/dashboard

## Secrets

Local secrets are stored in `.env.local`. This file is intentionally ignored by Git.

Public configuration contract lives in `.env.example`.

Do not store real API keys, database passwords, JWT secrets, or deploy tokens in the repository.

## Model roles

`OPENAI_ANALYSIS_MODEL` is used for resume parsing and structured profile extraction.

`OPENAI_MATCHING_MODEL` is reserved for the next vacancy matching stage, where deeper fit/gap reasoning will be needed.

## Vector search

Qdrant is the primary vector database for the platform.

The backend creates these local collections on startup:

- `hr_assistant_resume_profiles`
- `hr_assistant_vacancy_profiles`

PostgreSQL remains the source of truth for users, resumes, vacancies, and matching metadata. Qdrant stores embeddings for semantic search and matching.
