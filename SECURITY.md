# Security Policy

## Supported versions

HR Assist is pre-1.0 and in closed beta. Only the current `master` branch receives security fixes. Older tagged releases are not patched.

## Reporting a vulnerability

**Please do not file public GitHub issues for security vulnerabilities.**

Instead, send a private report via GitHub's "Report a vulnerability" flow on this repository, or by direct message to the repository owner.

In the report, include as much of the following as you can:

- a clear description of the issue and suspected impact
- exact steps to reproduce (including requests and payloads)
- the affected endpoint, component, or code path
- any suggested remediation

We will acknowledge reports within a few business days and aim to ship a fix or mitigation before public disclosure. Please practise responsible disclosure until a patch is released.

## Out of scope

The following are considered known constraints of a closed-beta MVP and are not accepted as vulnerabilities unless they meaningfully exceed what is already documented:

- Attacks that require a valid `BETA_TESTER_KEYS` entry and an already-authenticated account.
- Rate-limit bypasses that do not produce real impact (spam, cost abuse, credential stuffing).
- Missing hardening headers on the API docs endpoint (`/docs`) in local-only configurations.

## Secure-deployment baseline

If you run your own instance:

- Use a strong, uniquely-generated `JWT_SECRET_KEY` and rotate it if exposed.
- Keep all `.env*` files out of version control. The repository's `.gitignore` already covers them — do not override it.
- Set `AUTH_EMAIL_DELIVERY_MODE=smtp` in production. The `console` mode exists only for local development.
- Do not commit API keys (`OPENAI_API_KEY`, `HH_API_TOKEN`, `SUPERJOB_API_KEY`, `HABR_CAREER_API_TOKEN`, `BRAVE_API_KEY`) or production hostnames to source, docs, or tests.
- Restrict `CORS_ORIGINS` to trusted frontend origins only.
- Rotate API keys on any suspected exposure.
- Keep `OPENAI_ENFORCE_REQUEST_BUDGET=true` in production so cost-abuse attempts hit the per-request budget ceiling.

## Security posture already in the codebase

- JWT authentication with email-OTP second factor.
- Beta-key gate on registration.
- slowapi rate limiting on auth endpoints.
- Prompt-injection guard on untrusted resume and vacancy text (`app/services/llm_guard.py`).
- Per-user daily OpenAI spend ceiling (`app/models/user_daily_spend.py`).
- Structured logs for auth events.

Further hardening (centralised audit logs, secret manager, SAST / DAST in CI) is tracked on the roadmap.
