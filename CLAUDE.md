# HR-Assist — contributor conventions

Short, load-bearing rules for anyone (human or agent) making code changes in this repo.

## Backend (FastAPI + SQLAlchemy + Alembic)

- **`@limiter.limit` handlers MUST declare `response: Response`.** Without it, slowapi's header injection raises 500 on every request. Signature shape:

  ```python
  @router.post("/login")
  @limiter.limit("5/minute")
  def login(request: Request, response: Response, payload: LoginIn, db: Session = Depends(get_db)):
      ...
  ```

  Unit tests that flip `limiter.enabled = False` bypass this code path and cannot catch the regression. Keep the integration-style test in `backend/tests/test_auth_rate_limiting.py` and extend it when adding new rate-limited endpoints.

- **FastAPI route order matters.** Literal paths must be registered before `{param}` catch-alls in the same router, otherwise `GET /resumes/active` routes into `GET /resumes/{resume_id}` and returns 422 "not a valid integer".

- **Lint / format** is `ruff check app/` + `ruff format --check app/`. Scope is `app/` only, not `tests/`. CI pins the latest published ruff — upgrade your host copy (`pip install -U ruff`) if CI drifts ahead.

## Host ↔ container file drift

`backend/Dockerfile` does `COPY . .` and compose does NOT volume-mount `backend/`. So:

- Edit Python source on the **host**, never via `docker exec` or `docker cp` — the host copy is the source of truth, the image is rebuilt from it.
- After editing, rebuild: `docker compose up -d --build backend`.
- If you need to run `ruff format` to fix a CI diff, run it on the host: `python -m ruff format backend/app/`.

## Frontend (Next.js + TypeScript)

- Gate before pushing: `./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/eslint .` from `frontend/`.
- No implicit `any`. Shared types live in `frontend/src/types/`.
- **Design tokens & style-guide are owned by the `designer` agent.** `frontend-impl` consumes them by semantic name, never inlines raw colors/spacing/motion values. See the `team-workflow` skill for the full handoff protocol between tech-lead, designer, frontend-impl, backend-impl, test-author, and reviewer.

## Local quality gate (run before every `git push master`)

```bash
# Backend
python -m ruff format --check backend/app/
python -m ruff check backend/app/
docker compose exec -T backend python -m pytest -q

# Frontend
cd frontend && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/eslint . && cd ..
```

CD does **not** gate on CI — a red CI does not stop prod from deploying. The local gate is your only safety net.

## Secrets

Never hardcode real secrets, API keys, or server identifiers into source, examples, docs, or tests. Use env vars read at runtime. `.env*` files are gitignored — keep them that way. Same for `.tmp/`.

## Commits

- Conventional-commit style: `feat(scope): …`, `fix(scope): …`, `chore: …`.
- Don't `git push --force` master — CD resets the server to `origin/master`, so a rewrite propagates to prod.
- Don't commit `.env*`, `.tmp/`, `.claude/`, or generated artifacts (`node_modules/`, `__pycache__/`, `.next/`, `backend/storage/`).
