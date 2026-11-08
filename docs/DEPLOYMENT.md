# Deployment — pancakess.work

The production stack runs on `64.177.59.101`. Until DNS/SSL is cut over, use the IP as the hostname (HTTP):

```text
http://64.177.59.101/
```

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

## DNS

At **Porkbun** (authoritative nameservers `*.ns.porkbun.com`), set:

| Name | Type | Value |
|---|---|---|
| `@` | A | `64.177.59.101` |
| `www` | CNAME | `pancakess.work` |

Remove the existing Vercel A/CNAME records. TTL 300–600 seconds.

Current status (checked 2026-11-08): `pancakess.work` still points to Vercel (`216.198.79.1`), so the domain/SSL cutover requires this DNS change. The IP endpoint is fully live in the meantime; it is HTTP only until DNS is switched and Certbot runs.

## SSL

After DNS resolves to `64.177.59.101`:

```bash
certbot --nginx -d pancakess.work -d www.pancakess.work --redirect --agree-tos -m admin@pancakess.work
certbot renew --dry-run
```

Certbot installs a timer for renewal. Enable UFW:

```bash
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

Upload `pancakess_test_upload.csv` through the dashboard. It contains 8 real scoreboard CVEs and 2 unknown `CVE-2099-*` rows so both the G2 lookup and the `api-heuristic-v1` fallback are exercised.

Until DNS is switched, the same stack is reachable at:

```text
http://64.177.59.101/
http://64.177.59.101/api/health
http://64.177.59.101/api/ranking/similar/CVE-2026-10523?top_k=5
http://64.177.59.101/evolve/
```
