# Deployment — pancakess.work

Production is **https://pancakess.work/** (Let's Encrypt, auto-renew enabled). The origin server is
`64.177.59.101`; SSH and deployment commands still use that address. `www.pancakess.work` and plain HTTP
redirect to the canonical domain.

The production stack:

```text
Browser
  │
  ├─ https://pancakess.work/         → Nginx → /opt/pancakess/dashboard (Vite build)
  ├─ https://pancakess.work/api/     → Nginx → FastAPI 127.0.0.1:8000
  └─ https://pancakess.work/evolve/  → Nginx → /opt/pancakess/evolution
```

## Server layout

| Path | Content |
|---|---|
| `/opt/pancakess/dashboard/` | built React app (`dist/`) |
| `/opt/pancakess/evolution/` | standalone evolution observatory |
| `/opt/pancakess/server/` | FastAPI source |
| `/opt/pancakess/results/` | ranking, explanations and claims |
| `/opt/pancakess/data_cache/` | Granite embedding subsets + retrieval index |
| `/opt/pancakess/.env` | IBM/Gemini credentials, mode `600` |
| `/opt/pancakess/.venv/` | Python 3.10 runtime for FastAPI |
| `/etc/systemd/system/pancakess-api.service` | API service |
| `/etc/nginx/sites-available/pancakess` | Nginx site |

## Build and deploy the frontend

```bash
cd dashboard
VITE_API_URL=/api npm run build
rsync -az --delete dashboard/dist/ root@64.177.59.101:/opt/pancakess/dashboard/
```

`VITE_API_URL=/api` is same-origin; Nginx proxies `/api/` to FastAPI. Do not use `localhost` in the production build.

## API service

```bash
systemctl status pancakess-api
systemctl restart pancakess-api
journalctl -u pancakess-api -f
curl http://127.0.0.1:8000/api/health
```

### Retrieval index

The CVE drawer's neighbour index is a generated artifact (`data_cache/*.parquet` is gitignored). Rebuild it
locally, then sync it before restarting:

```bash
.venv/bin/python cloud/build_retrieval_index.py
rsync -az data_cache/granite_embeddings_retrieval.parquet \
  data_cache/granite_embeddings_retrieval.meta.json \
  root@64.177.59.101:/opt/pancakess/data_cache/
systemctl restart pancakess-api
curl -s 'http://127.0.0.1:8000/api/ranking/similar/CVE-2026-10523?top_k=5'
```

`/api/health` should report `similarity_rows` greater than zero. This index is retrieval-only; it does not
change the ranking or any audited metric. See [`docs/RETRIEVAL.md`](RETRIEVAL.md).

### Live Gemini Judge Q&A

The `/api/gemini/chat` endpoint (also `/api/chat`) uses Gemini 2.5 Flash and needs:

- `GEMINI_API_KEY` in `/opt/pancakess/.env` (mode `600`, never committed)
- `google-genai` installed in `/opt/pancakess/.venv` (listed in `server/requirements.txt`)

```bash
/opt/pancakess/.venv/bin/python -m pip install google-genai
systemctl restart pancakess-api
curl -s -X POST https://pancakess.work/api/gemini/chat \
  -H 'Content-Type: application/json' \
  --data '{"question":"What is KEV?","active_cve":"CVE-2026-10523"}'
```

The response must say `"provider": "GEMINI"` and `"source": "live"`. If it returns a configuration error,
the key is missing. Do not paste the key into git, logs, or chat.

## DNS

At **Porkbun** (authoritative nameservers `*.ns.porkbun.com`), the records are:

| Name | Type | Value |
|---|---|---|
| `@` | A | `64.177.59.101` |
| `www` | CNAME | `pancakess.work` |

Status (2026-11-08): DNS resolves to `64.177.59.101`; Vercel records were removed. `www` and HTTP redirect
to `https://pancakess.work/`.

## SSL

Certificate issued by Let's Encrypt on 2026-11-08 for `pancakess.work` and `www.pancakess.work`; it expires
2027-02-06 and renews automatically through the Certbot systemd timer.

```bash
certbot certificates
certbot renew --dry-run
```

Nginx is managed by Certbot: it added the TLS server block and the HTTP→HTTPS redirect to
`/etc/nginx/sites-available/pancakess`. The repo copy `deploy/nginx-pancakess.conf` documents the pre-TLS
routing; do not overwrite the live file with it after Certbot has run.

UFW allows SSH, HTTP and HTTPS:

```bash
ufw status
ufw allow 80/tcp
ufw allow 443/tcp
```

## Test the live stack

```bash
curl -I https://pancakess.work/
curl https://pancakess.work/api/health
curl 'https://pancakess.work/api/ranking/similar/CVE-2026-10523?top_k=5'
curl -X POST https://pancakess.work/api/predict \
  -H 'Content-Type: application/json' \
  --data '{"rows":[{"cve_id":"CVE-2099-90001","assigner":"microsoft","epss":0.4}]}'
```

The fixture `https://pancakess.work/pancakess_test_upload.csv` contains 8 real scoreboard CVEs and 2
unknown `CVE-2099-*` rows, so both the G2 lookup and the `api-heuristic-v1` fallback can be exercised through
`POST /api/predict`.

Canonical host: `https://pancakess.work/`. The origin IP is for SSH only; the public certificate is issued
for the domain, not for the IP.
