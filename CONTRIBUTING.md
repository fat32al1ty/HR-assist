# Contributing

HR Assist is an actively-developed AI MVP. External contributions are welcome for bug reports, reproducible issues, and small focused pull requests. Larger changes should be discussed in an issue first.

## Development setup

1. Fork and clone the repository.
2. Copy the env template:

   ```bash
   cp .env.example .env.local
   ```

   At minimum fill in `OPENAI_API_KEY`, `JWT_SECRET_KEY`, and `BETA_TESTER_KEYS`. Leave `AUTH_EMAIL_DELIVERY_MODE=console` so OTP codes land in the backend log.

3. Start the stack:

   ```bash
   docker compose up -d --build
   ```

4. Verify the services:

   - UI — http://localhost:3000
   - API docs — http://localhost:8000/docs
   - Health — http://localhost:8000/health

Alembic migrations run automatically when the backend container starts.

## Reporting bugs

Open a GitHub issue with:

- a short description of the bug
- exact steps to reproduce (commands, payloads, UI interactions)
- expected vs. actual behaviour
- relevant logs or screenshots (scrub secrets first)
- your environment: local Docker vs. deployed instance, browser, OS

Minimal reproductions help enormously. If the bug touches matching quality, include the resume snippet (or a minimised fake one) and the vacancy set you saw.

## Proposing changes

For anything larger than a one-line fix, open an issue first and describe:

- the problem you are solving
- the proposed approach
- trade-offs and risks
- a rough scope (files / modules likely to change)

This keeps review focused and avoids wasted work. Trivial fixes (typos, obvious bugs) can go straight to a pull request.

## Branching and commits

- Branch per task. Name branches `feature/...`, `fix/...`, `refactor/...`, `docs/...`.
- Use Conventional Commits: `feat(scope): ...`, `fix(scope): ...`, `docs: ...`, `refactor: ...`, `test: ...`, `chore: ...`.
- One logical change per commit where possible.

## Pull request checklist

- [ ] The change has a clear, single purpose.
- [ ] No secrets, tokens, or production hostnames are committed (see `SECURITY.md`).
- [ ] Backend tests pass locally: `docker compose exec -T backend python -m pytest -q`.
- [ ] Backend lint / format passes: `python -m ruff format --check backend/app/` and `python -m ruff check backend/app/`.
- [ ] Frontend type-check and lint pass: `cd frontend && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/eslint .`.
- [ ] Public behaviour changes are reflected in `README.md` and, if applicable, `docs/ROADMAP.md`.
- [ ] Breaking changes and deployment notes are called out in the PR description.

## Coding standards

- **Python:** small, explicit services. Repositories have no hidden side effects. Pydantic schemas at API and service boundaries.
- **TypeScript:** no implicit `any`. Shared types live in `frontend/types/`. Typed API client over fetch.
- **SQLAlchemy / Alembic:** every schema change ships with a reversible migration.
- **Tests:** unit-level where cheap, integration where the correctness comes from wiring (auth flow, rate limiting, matching pipeline). See `backend/tests/` for examples.

## Local quality gate

Before pushing:

```bash
# Backend
python -m ruff format --check backend/app/
python -m ruff check backend/app/
docker compose exec -T backend python -m pytest -q

# Frontend
cd frontend && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/eslint . && cd ..
```

CI runs the same gate. CD does not gate on CI — a red CI does not stop production from deploying, so the local gate is the real safety net.

## Code of conduct

Be direct, kind, and technical. Review feedback should address the code, not the author. Personal attacks, harassment, or discriminatory language are not welcome and will be removed.
