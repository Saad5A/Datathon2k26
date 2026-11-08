# FastAPI dashboard backend

Read-only artifact service plus **upload scoring** for the pancake dashboard.

## Run

```bash
.venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Health:

```bash
curl http://localhost:8000/api/health
```

The frontend uses:

```env
VITE_API_URL=http://localhost:8000/api
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` (alias `/health`) | artifact counts, capabilities, load warnings |
| `GET` | `/api/stats/summary` | rank counts, risk bands, Granite/Gemini availability |
| `GET` | `/api/ranking/cves` | paginated/searchable ranking |
| `GET` | `/api/ranking/similar/{cve_id}` | Granite retrieval neighbours (description similarity; not a prediction) |
| `GET` | `/api/explanations/{cve_id}` | Granite technical + Gemini executive payload |
| `GET` | `/api/models/comparison` | Granite vs Gemini telemetry |
| `POST` | `/api/gemini/chat` (alias `/api/chat`) | live Gemini 2.5 Flash Q&A for the Judge drawer; requires `GEMINI_API_KEY` and `google-genai` |
| `GET` | `/api/results` | audited backtest metrics for the `/results` proof page, with claim ids and status |
| `GET` | `/api/docs` | OpenAPI UI |
| `POST` | `/api/predict` | score uploaded CVE rows |

Retrieval neighbours come from `data_cache/granite_embeddings_retrieval.parquet` (IBM Granite small, 384-d, local). They are display evidence only and never used for scoring; see [`docs/RETRIEVAL.md`](../docs/RETRIEVAL.md).

### `POST /api/predict`

```json
{ "rows": [ { "cve_id": "CVE-2026-10523", "published": "2026-06-09", "assigner": "...", "epss": 0.5, "poc_github": 1 } ] }
```

- Known scoreboard CVEs reuse the audited **G2** score and reasons from `results/scores_2026.csv`.
- Unknown CVEs use a transparent API fallback over EPSS, exploit flags, assigner history and age, labelled `api-heuristic-v1`.
- Rows are ranked by the frontend within the uploaded batch. Nothing is written to `results/` or `data_cache/`.
- Max 50,000 rows per request.

## API keys

**None are required at runtime.** The service reads committed artifacts. Granite/Gemini regeneration is documented in the root `README.md` and `docs/IBM_USAGE.md`.

## Notes

- CORS is open (`*`, no credentials) so the local Vite app can call it.
- Missing optional explanation/playbook artifacts are reported in `/api/health` and do not prevent boot.
- The backend does not mutate audited files.
