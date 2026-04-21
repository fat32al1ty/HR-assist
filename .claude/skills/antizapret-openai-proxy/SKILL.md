---
name: antizapret-openai-proxy
description: Manage the OpenAI reverse-proxy hosted on the antizapret VPN server (213.176.16.206). Use when OpenAI needs to be reached from a geo-blocked prod host, when diagnosing proxy failures (401/403/5xx), rotating the IP whitelist, renewing the TLS cert, or repointing backend OPENAI_BASE_URL. NOT for managing the antizapret VPN include-hosts list — that lives in the /antizapret slash command.
---

# OpenAI proxy on antizapret

HR-Assist prod (`185.76.242.254`) is geo-blocked from `api.openai.com` (direct call returns `403`). OpenAI requests are tunnelled through an nginx reverse-proxy on the existing antizapret VPN server (`213.176.16.206`), reachable as `https://213-176-16-206.sslip.io/v1/`. The proxy itself is IP-whitelisted so only the prod host can use it — no API key leakage risk to anonymous internet traffic.

## 1. Topology

```
HR-Assist backend (185.76.242.254)
    │
    │  HTTPS (LE cert, TLS 1.2/1.3)
    │  Authorization: Bearer sk-proj-...
    ▼
nginx reverse-proxy on 213.176.16.206
(sslip.io DNS: 213-176-16-206.sslip.io)
    │
    │  proxy_pass https://api.openai.com/v1/
    │  (antizapret server has working OpenAI egress)
    ▼
api.openai.com
```

- nginx config: `/etc/nginx/sites-available/openai-proxy` (symlinked into `sites-enabled/`)
- LE cert: `/etc/letsencrypt/live/213-176-16-206.sslip.io/`
- Whitelist: `allow 185.76.242.254; deny all;` — inside the `443` server block
- No `/healthz` / other endpoints — `return` in rewrite phase fires before the access phase and bypasses `allow/deny`, so the proxy has exactly one allowed path: `/v1/*`

## 2. Wiring from the backend

Backend reads `OPENAI_BASE_URL` from `/opt/hr-assist/.env.local` (not `.env.server` — that file is present but not referenced by `docker-compose.yml`). The three OpenAI client sites (`embeddings.py`, `resume_analyzer.py`, `vacancy_analyzer.py`) all honour `settings.openai_base_url`, so no code change is needed.

```
# /opt/hr-assist/.env.local
OPENAI_BASE_URL=https://213-176-16-206.sslip.io/v1
OPENAI_API_KEY=sk-proj-...   # unchanged, your real OpenAI key
```

Re-apply after any env edit:

```bash
ssh -i .tmp/deploy_key/hrassist_deploy root@185.76.242.254 \
  'cd /opt/hr-assist && docker compose up -d --force-recreate backend'
```

`--force-recreate` is required: `docker compose up -d` alone does not reload `env_file:` on a running container.

## 3. Connecting to the antizapret host

SSH access uses a password (same server is the `/antizapret` VPN):

- Host: `213.176.16.206`
- User: `root`
- Password: `84699583Fat!`

Prefer paramiko for automation — but note that **more than ~5 rapid paramiko sessions in a minute triggers fail2ban** on this host. The ban is roughly 10 min. Recover: poll port 22 until it reopens, do not retry inside a tight loop.

```python
import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('213.176.16.206', username='root', password='84699583Fat!', timeout=30)
```

## 4. Verifying the proxy

Positive path (from prod):

```bash
ssh -i .tmp/deploy_key/hrassist_deploy root@185.76.242.254 \
  'docker compose -f /opt/hr-assist/docker-compose.yml exec -T backend \
   python -c "from openai import OpenAI; from app.core.config import settings; \
              print(OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url).models.list().data[0].id)"'
```

Negative path (from any other IP, including your laptop):

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://213-176-16-206.sslip.io/v1/models
# expected: 403
```

Whitelist self-check:

- `/v1/*` from non-whitelisted IP → `403`
- `/` from any IP → `404` (no leak about what runs here)

## 5. Rotating the IP whitelist

If the prod host gets a new IP (`185.76.242.254` is currently static at the hosting provider, so this is rare):

```python
# 213.176.16.206 :: edit the single `allow` line
sed -i 's|allow 185\.76\.242\.254;|allow NEW.IP.HERE;|' /etc/nginx/sites-available/openai-proxy
nginx -t && systemctl reload nginx
```

Multiple IPs: duplicate the `allow` line. `deny all;` stays last.

## 6. TLS renewal

Certbot installed a systemd timer during issuance — `systemctl list-timers | grep certbot` shows the next run. The cert for `213-176-16-206.sslip.io` was issued for 90 days on 2026-04-21; auto-renewal kicks in at ~60 days. If it ever fails:

```bash
certbot renew --nginx
nginx -t && systemctl reload nginx
```

## 7. Diagnosing failures

| Symptom | Likely cause | Where to look |
|---|---|---|
| Backend HTTP 401 from proxy | bad OPENAI_API_KEY in `.env.local`; env not reloaded (missed `--force-recreate`) | `docker compose exec backend env \| grep OPENAI` |
| Backend HTTP 403 from proxy | prod IP changed → whitelist miss | `/var/log/nginx/access.log` on 213.176.16.206 |
| Backend HTTP 502 / 504 | antizapret host lost OpenAI egress or proxy_pass TLS failure | `journalctl -u nginx -n 100` + `curl -v https://api.openai.com/v1/models` from antizapret |
| `ssl: unable to get local issuer certificate` from the SDK | nginx cert expired; `certbot renew` |
| All requests time out | nginx down; or fail2ban banned prod | `systemctl status nginx`; `fail2ban-client status sshd` |

Raw test from antizapret host itself (bypasses the whitelist since it hits OpenAI directly):

```bash
curl -sS -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models
```

## 8. Do NOT

- Do not add `/healthz` or any other public endpoint to the server block — `return` directives run in rewrite phase and skip `allow/deny`, leaking presence.
- Do not proxy the OpenAI key inside the nginx config (`proxy_set_header Authorization`) — keep the key on the backend; the proxy is deliberately dumb.
- Do not point CI tests at this proxy — GitHub Actions runners have direct OpenAI access and shouldn't be whitelisted here.
- Do not reuse this proxy for any other service — keep the scope narrow so whitelist / cert / renewal / audit stay simple.
