# GitHub metadata for HR Assist

Canonical copy-paste source for the public-facing strings used on GitHub, in the pinned repo card, and in resume / portfolio contexts. Update here first, then mirror to GitHub settings.

---

## Suggested repository display title

> **HR Assist — AI Resume Intelligence & Job Matching**

Rationale: the repo slug (`HR-assist`) is short and URL-friendly; the display title (shown in the pinned-repo card and on your profile) signals the category — AI + retrieval + jobseeker product — to a reader who sees it for two seconds.

---

## GitHub About (≤ 350 chars)

> End-to-end AI platform for jobseekers. Parses a resume, extracts skills and grade, fetches live vacancies from hh.ru, ranks them with a multi-stage semantic matcher on Qdrant, and explains what is missing. Shortlist / blacklist feedback is time-decayed and feeds back into ranking. Working MVP on Docker.

---

## GitHub Topics

Paste in order of priority (GitHub allows up to 20):

```
ai
llm
openai
semantic-search
vector-search
qdrant
fastapi
nextjs
typescript
postgresql
docker
resume-parser
resume-analysis
job-matching
recommender-system
rag
hr-tech
full-stack
python
react
```

---

## Pinned repository description

For the "Pinned" card on your GitHub profile. Short, punchy, factual:

> AI-assisted resume intelligence and job matching. Parses a resume, extracts skills and grade, fetches real vacancies, ranks them with a multi-stage semantic matcher, and explains the gap. Feedback loop feeds ranking. Working MVP.

---

## Tagline variants (pick one)

1. *Upload a resume, get a ranked shortlist of real jobs — with the missing skills called out.*
2. *AI-assisted resume intelligence and job matching, built as a real retrieval system.*
3. *Resume in, ranked vacancies with gap analysis out. Semantic matching, not keyword search.*

---

## Short release text template

Paste into each GitHub release. Keep it to five short lines:

```
v<MAJOR.MINOR.PATCH> — <one-line theme>

What changed: <1–2 sentences, user-visible>
Why it matters: <1 sentence, measured impact>
Migration: <none | one-line note>
Next: <what is queued after this>
```

Example:

```
v0.8.1 — UI/UX polish + applied-vacancy dedup

What changed: Vacancies with active applications no longer reappear in the matching shortlist; tracker cards match the matching card style.
Why it matters: Removes a confusing duplicate on every refresh; tightens the perceived quality of the workspace.
Migration: None. Pure frontend + a bug fix in the recommendation filter.
Next: Salary-predictor activation once the vacancy corpus is large enough.
```

---

## Resume / portfolio description

### One-liner

> **HR Assist** — AI-assisted resume intelligence and job matching platform (FastAPI + Next.js + Qdrant + OpenAI). Working MVP, closed beta.

### Short paragraph (≤ 80 words)

> Built **HR Assist**, an end-to-end AI platform for jobseekers. Parses resumes (PDF/DOCX), extracts a structured candidate profile with an LLM, fetches live vacancies, and ranks them with a multi-stage semantic matcher (Qdrant vector search + domain gate + skill-overlap floor + MMR + cross-encoder rerank). Explains per-vacancy "why shown" and missing skills. Time-decayed feedback loop changes ranking over time. Shipped as a Docker-deployed MVP with GitHub Actions CI/CD.

### Medium paragraph (≤ 150 words)

> **HR Assist** is a working closed-beta AI platform that turns an uploaded resume into an actionable job search. The pipeline parses PDF/DOCX resumes, runs a structured LLM analysis (role, grade, skills, domains, risks), embeds the profile into Qdrant, fetches live vacancies from the hh.ru API, and ranks them with a multi-stage matcher — domain gate, skill-overlap floor, MMR for diversity, cross-encoder / LLM rerank — with per-vacancy "why shown" and missing-skills explanations. Shortlist / blacklist / like / dislike feedback is weighted by time decay and fed back into ranking. Production concerns are first-class: prompt-injection guard, per-user OpenAI cost ceiling, rate-limited auth with email-OTP, structured telemetry, and an eval harness with NDCG / MAP / MRR floors enforced in CI. Stack: FastAPI, SQLAlchemy, Alembic, PostgreSQL, Qdrant, OpenAI, Next.js 16, React 19, TypeScript, Tailwind v4, Docker Compose.

---

## Bullet points for a CV / "Projects" section

- End-to-end AI product: resume parsing, structured LLM analysis, semantic vacancy matching, and a feedback loop that changes ranking over time.
- Retrieval engineering beyond a single cosine call: domain gate, skill-overlap floor, MMR diversity, cross-encoder / LLM rerank, matching-quality eval harness with NDCG / MAP / MRR floors enforced in CI.
- Production hardening from day one: JWT + email-OTP auth, slowapi rate limiting, prompt-injection guard on untrusted text, per-user OpenAI cost ceiling, structured telemetry, health checks.
- Shipped and operated: Dockerised local stack, GitHub Actions CI, SSH-based CD to a dedicated server, live closed-beta demo.
- Stack: Python / FastAPI / SQLAlchemy / Alembic, Next.js 16 / React 19 / TypeScript / Tailwind v4, PostgreSQL, Qdrant, OpenAI, Docker Compose.
