# Release v<MAJOR.MINOR.PATCH> — <one-line theme>

## Overview

One paragraph, user-facing. What this release is and who it is for. No internal jargon — read like the first sentence of a changelog entry.

## What changed

Bullet list, user-visible. Group by area if there is more than a handful of bullets:

- **Matching / ranking** — …
- **UI / UX** — …
- **Backend / API** — …
- **Infra / ops** — …

Call out behaviour that changed for existing users in **bold**.

## Why it matters

Two or three short bullets on impact. Prefer measured statements ("cuts first-run time from ~25s to ~10s", "kills cross-domain false positives on IT resumes") over adjectives.

## Migration / deployment notes

- **DB migrations:** none / `alembic upgrade head` runs automatically on backend start.
- **Env variables:** list any new or renamed variables with defaults.
- **Breaking API changes:** none / describe.
- **Manual steps on prod:** none / describe.

If the release is purely frontend or documentation, say so explicitly.

## Known limitations

Honest list of what is *not* fixed / *not* in this release. Better to name them than to have a reviewer find them:

- …
- …

## Next step

One or two lines on what is queued immediately after this release. Links to an issue or roadmap entry if they exist.

---

### Release checklist (remove before publishing)

- [ ] Version bumped in `frontend/package.json` and any backend version constant.
- [ ] Git tag `vX.Y.Z` created and pushed.
- [ ] `docs/ROADMAP.md` updated with the new entry.
- [ ] `README.md` "Roadmap" section reflects the new highlight.
- [ ] CI is green on `master` for the tagged commit.
- [ ] Local quality gate run: ruff format / check, backend pytest, frontend tsc + eslint.
- [ ] No secrets committed (run `git diff <previous-tag>..HEAD` and scan).
- [ ] Screenshots in `docs/screenshots/` updated if visible UI changed.
