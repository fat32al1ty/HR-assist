# Privacy statement

HR Assist is designed so that **the minimum amount of personal data is persisted, for the minimum amount of time**. This document describes what the platform stores, what it deliberately does not store, and what is sent to third parties.

It is not a legal document and does not replace a formal policy of personal-data processing under 152-ФЗ. A user-facing public policy (`/privacy`) is a separate artefact.

## What is deliberately NOT persisted

When you upload a resume, the system:

- **Does not persist the raw resume text** (`resumes.extracted_text` column was removed in migration `0023_pii_minimization`).
- **Deletes the uploaded file immediately after analysis.** The on-disk PDF/DOCX is removed both on the success path and on the failure path of the processing pipeline. `resumes.storage_path` is nulled out as part of the same transaction.
- **Strips PII from the text before it reaches the LLM.** A local scrubber (`app/services/pii_scrubber.py`) removes emails, phone numbers, social-media URLs, cyrillic full-name patterns, and dated-of-birth expressions. Only the scrubbed text is sent to OpenAI.
- **Does not ask the LLM to return name / email / phone.** The analysis JSON schema (`app/services/resume_analyzer.py`) has no fields for these identifiers, and the system prompt explicitly instructs the model to ignore them if they appear in the input.
- **Does not store the candidate name or the full "canonical text" in the vector store.** Qdrant payloads contain only matcher-relevant signals (role, seniority, skills, domains) — no identifiers, no free-form resume text.
- **Replaces the uploaded filename with a generic placeholder.** The database column `resumes.original_filename` stores `resume.pdf` / `resume.docx`, not the user's original `Иванов_И_И_резюме.pdf`.

## What IS persisted

The product cannot function without a small set of data tied to an account:

- `users.email` — required for authentication.
- `users.hashed_password` — bcrypt-hashed, never logged.
- `users.home_city`, `users.preferred_titles`, `users.expected_salary_*` — user-supplied preferences that feed the matcher.
- `resumes.analysis` — the structured profile (role, grade, skills, domains, summary) returned by the LLM. This intentionally contains no name / email / phone (see above).
- `resume_profiles.canonical_text` — the text sent to the embedding model, used to regenerate vectors without re-running the LLM. Contains skill / role / domain text; no identifiers.
- `applications.*` — user's own application tracker entries and AI-generated cover letters.
- `user_vacancy_feedback.*` — like/dislike/shortlist/blacklist signals.
- `match_telemetry.*` — impression/click/dwell events used to improve ranking.

Every row in the tables above cascades on `users.id` delete — removing a user physically removes their rows.

## Third-party processing

- **OpenAI API** — the **scrubbed** resume text is sent to OpenAI for structured analysis. Embeddings are also generated via OpenAI. This is trans-border processing; it will be moved to in-region inference in a later phase (see `docs/ROADMAP.md`).
- **hh.ru API** — public vacancy data is fetched. No user data is sent.

## Auth logging

- The platform includes `mask_email()` (`app/services/pii_scrubber.py`) for producing log-safe email representations (`j***@e***.com`). Structured logs on auth routes use masked forms when email appears.
- `AUTH_EMAIL_DELIVERY_MODE=console` prints OTP codes to stdout for local development only. The backend refuses to start in non-local environments when this mode is active (`app/core/config.py`).

## Retention

As of Level A (`v0.9.0`), there is no scheduled purge of `resumes.analysis`, `applications`, or `user_vacancy_feedback`. Users can delete their account (`DELETE /api/resumes/{id}` for individual resumes; user-deletion endpoint planned for Level B), which cascade-removes their rows. Automated retention windows are a Level-B follow-up.

## Reporting concerns

Use the disclosure process in [`SECURITY.md`](SECURITY.md).
