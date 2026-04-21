---
name: deploy-cicd
description: Configure, trigger, rotate, or diagnose the HR-Assist CI/CD pipeline (GitHub Actions → SSH → server /opt/hr-assist, docker compose build+up). Use for deploying, adding/rotating deploy keys, setting GitHub secrets, checking last deploy status, or debugging failed deploys.
---

# HR-Assist CI/CD skill

Production target: **`root@185.76.242.254:/opt/hr-assist`** (Ubuntu + Docker + Compose v2).
Delivery model: `git push master` → GitHub Actions runs `.github/workflows/cd.yml` → SSH into server → `git reset --hard origin/master` + `docker compose up -d --build`.

Images are **built on the server** (no registry). Do not reintroduce ghcr.io pushes — the server has compute, builds once per deploy, it keeps the workflow simple.

## 1. GitHub secrets (one-time)

`.github/workflows/cd.yml` requires these secrets at the **repo level** (Settings → Secrets and variables → Actions):

| Name | Value |
|---|---|
| `SSH_HOST` | `185.76.242.254` |
| `SSH_USER` | `root` |
| `SSH_PORT` | `22` (or omit — workflow falls back to 22) |
| `DEPLOY_PATH` | `/opt/hr-assist` |
| `SSH_PRIVATE_KEY` | full contents of the deploy private key (ed25519), including `-----BEGIN/END-----` lines |

`ci.yml` uses `OPENAI_API_KEY` for backend tests — optional but add a low-budget key if you want backend-test job to run real OpenAI calls.

Upload via `gh`:

```bash
gh auth login -w         # one-time
gh secret set SSH_HOST       --repo fat32al1ty/HR-assist --body "185.76.242.254"
gh secret set SSH_USER       --repo fat32al1ty/HR-assist --body "root"
gh secret set SSH_PORT       --repo fat32al1ty/HR-assist --body "22"
gh secret set DEPLOY_PATH    --repo fat32al1ty/HR-assist --body "/opt/hr-assist"
gh secret set SSH_PRIVATE_KEY --repo fat32al1ty/HR-assist < .tmp/deploy_key/hrassist_deploy
```

The cd job references `environment: production`. GitHub auto-creates the environment on first run. If you add required reviewers there, deploys will wait for approval.

## 2. Deploy key on the server

Public key is appended to `/root/.ssh/authorized_keys`. Private key lives at `.tmp/deploy_key/hrassist_deploy` (gitignored via `.tmp/`). Never commit it.

Rotate:

```bash
# local
ssh-keygen -t ed25519 -f .tmp/deploy_key/hrassist_deploy_new -N "" -C "hr-assist-cd@github-actions"
PUB=$(cat .tmp/deploy_key/hrassist_deploy_new.pub)

# server (via current key or password)
ssh root@185.76.242.254 "echo '$PUB' >> /root/.ssh/authorized_keys"

# GitHub
gh secret set SSH_PRIVATE_KEY --repo fat32al1ty/HR-assist < .tmp/deploy_key/hrassist_deploy_new

# smoke test a deploy, then remove the old key from authorized_keys
ssh -i .tmp/deploy_key/hrassist_deploy_new root@185.76.242.254 \
  "sed -i '/hr-assist-cd@github-actions/!b;n' /root/.ssh/authorized_keys"   # review first!

mv .tmp/deploy_key/hrassist_deploy_new     .tmp/deploy_key/hrassist_deploy
mv .tmp/deploy_key/hrassist_deploy_new.pub .tmp/deploy_key/hrassist_deploy.pub
```

For initial bootstrap (if ever redoing on a fresh server) plink via password works (PuTTY ships with Git for Windows in most setups):

```powershell
plink -ssh -batch -hostkey SHA256:xntTeNn5ReZcL7yj4OLrn6Xm/bY7ZbaoNLBF5L9jY9M `
  -pw '<PASSWORD>' root@185.76.242.254 `
  "mkdir -p /root/.ssh && chmod 700 /root/.ssh && echo '<PUBKEY>' >> /root/.ssh/authorized_keys"
```

## 3. What the workflow does

`cd.yml` runs on `push` to `master`/`main` and on manual `workflow_dispatch`:

1. SSH into `$SSH_HOST` as `$SSH_USER` using `$SSH_PRIVATE_KEY`
2. `cd $DEPLOY_PATH`
3. `git fetch --prune origin && git reset --hard origin/<ref>` — server tracks the pushed ref exactly (any server-side drift is wiped; commit intentional server changes back to the repo)
4. `docker compose pull --ignore-buildable || true` (pulls pinned third-party images)
5. `docker compose up -d --build --remove-orphans` (rebuilds app images, rolling restart)
6. `docker image prune -f`
7. Separate health-check step polls `http://localhost:8000/health` for up to 60s

`concurrency.group: deploy` serialises deploys — a second push waits for the first.

## 4. Manual deploy

From GitHub: Actions → CD → Run workflow → choose branch.
From CLI: `gh workflow run cd.yml --ref master`.
From server (emergency, bypasses CI gating): `cd /opt/hr-assist && git pull && docker compose up -d --build`.

## 5. Diagnosing a failed deploy

```bash
# latest run
gh run list --workflow cd.yml --limit 5
gh run view --log-failed

# server state
ssh root@185.76.242.254 "cd /opt/hr-assist && git log -1 --oneline && docker compose ps && docker compose logs --tail=80 backend"

# re-run health-check without redeploy
ssh root@185.76.242.254 "curl -s http://localhost:8000/health"
```

Common failures:

- **`git reset` conflicts**: shouldn't happen (reset is destructive), but if `.env.server` / `.env.local` are missing, docker fails. They live **outside** git on the server (`/opt/hr-assist/.env.local`, `/opt/hr-assist/.env.server`) — do not add them to the repo; manage separately.
- **`docker compose up` rebuilds everything slowly**: expected on first deploy after dependency changes. BuildKit cache on the host speeds subsequent builds.
- **Port 80/3000/8000 already bound**: previous `docker compose down` never ran. Workflow uses `up -d` which recreates containers — fine for the standard path.

## 6. Current secrets inventory (for reference)

Run `gh secret list --repo fat32al1ty/HR-assist` to see what's set. Expected set after initial config:

- `SSH_HOST`, `SSH_USER`, `SSH_PORT`, `SSH_PRIVATE_KEY`, `DEPLOY_PATH`
- `OPENAI_API_KEY` (optional, for `ci.yml` backend-test)

## 7. Things NOT to do

- Don't re-add `build-and-push` jobs or push to ghcr.io. Images are built on the server.
- Don't commit `.tmp/deploy_key/*` or any `.env*` files. `.gitignore` already covers them.
- Don't `git pull` on the server while a CD run is in progress — the `concurrency: deploy` group only serialises GitHub-side runs, not a human racing a run.
- Don't change the compose project name (`hr-assist` from dir `/opt/hr-assist`) — container names and volumes depend on it.
