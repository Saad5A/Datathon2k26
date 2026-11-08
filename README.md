# Before the Breach — CVE exploitation triage

Sheridan Datathon 2026 · IBM “Before the Breach” track.

We rank the 72,670 CVEs on the 2026 scoreboard by how likely each is to be added to CISA KEV, using only information known at the end of its snapshot month. The judged submission is `results/top500.csv`; the full ranking is `results/scores_2026.csv`.

> **No 2026 labels.** We have no 2026 KEV outcomes. We report 2025 backtests, 2026 distributions and the predicted ranking; we do not claim 2026 accuracy.

## What is in this repo

| Area | What it does |
|---|---|
| `dashboard/` | React/Vite pancake dashboard. Upload a CSV/JSON of CVEs, score locally or through the API, inspect the ranking, export it. `/results` is the evidence sheet; the CVE drawer shows Granite retrieval neighbours. |
| `server/` | FastAPI bridge: ranking artifacts, Granite/Gemini explanations, upload scoring. |
| `src/model/` | The audited ranking model: time-safe features, backtests, G2/Granite test, final files. |
| `cloud/` | IBM Granite embedding and explanation scripts (watsonx.ai + local Hugging Face/Ollama). |
| `evolution/` | Separate research observatory: the evolutionary search and its interactive braid. |
| `results/` | Ranked scores, submission, claims, audits and supporting artifacts. |
| `audit/` | Independent audit reports and evidence. |
| `docs/` | Model notes, IBM details, interfaces and this project’s supporting documentation. |

## Production URL

The production deployment is live on the domain with HTTPS (Let's Encrypt, auto-renew enabled):

```text
https://pancakess.work/
https://pancakess.work/results
https://pancakess.work/api/health
https://pancakess.work/evolve/
https://pancakess.work/pancakess_test_upload.csv
```

`www.pancakess.work` and HTTP requests redirect to `https://pancakess.work/`. The origin server is `64.177.59.101`; SSH and deployment commands still use that address. Certificate renewal is handled by the Certbot systemd timer (`certbot renew --dry-run` to test).

## Run the dashboard locally

### 1. Start the API

```bash
.venv/bin/pip install -r server/requirements.txt
.venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Check: <http://localhost:8000/api/health>

### 2. Start the dashboard

```bash
cd dashboard
npm install
printf 'VITE_API_URL=/api\n' > .env.local
npm run dev -- --host 0.0.0.0 --port 5173
```

Open <http://localhost:5173/>. Vite proxies `/api` to `http://127.0.0.1:8000`, so the same relative base works in development and production. The evidence sheet is at <http://localhost:5173/results>.

The default upload engine is **Model API** when `VITE_API_URL` is configured. It sends rows to `POST /api/predict`; known scoreboard CVEs use the audited **G2** score, unknown CVEs use a transparent fallback labelled `api-heuristic-v1`. If the API is unavailable, use **Local demo** in *Processing options*; no file leaves the browser.

To run the dashboard with no backend:

```bash
VITE_API_URL=demo npm run dev -- --host 0.0.0.0 --port 5173
```

### 3. Upload data

- Accepted: **CSV or JSON**, up to 50 MB / 50,000 rows.
- Required: `cve_id`.
- Optional: `published`, `assigner`, `epss`, `exploitdb`, `metasploit`, `nuclei`, `poc_github`, `score`, `rank`, `priority`, `reasons`.
- Pre-scored files keep their supplied scores unless you choose to re-score them.
- There is a built-in sample: **“Try a sample batch”**.

### 4. Evolution observatory (separate)

```bash
bash evolution/serve.sh
# http://127.0.0.1:8010/
```

This is a separate D3 research UI; it is not part of the pancake app. Add `?ui=1` for its full control rail.

## IBM technology

| IBM technology | How it is used | Evidence / code |
|---|---|---|
| **IBM Granite embeddings** `ibm/granite-embedding-278m-multilingual` (768-d, 512 tokens) | Text score for the ranking model. The pre-registered G1/G2 test adopted G2 (C1 + Granite text) with no measurable gain over C1. | `cloud/embed_granite.py`, `src/model/granite.py`, `docs/ibm.md`, `results/granite_comparison.json` |
| **IBM watsonx.ai** (`ca-tor`) + `ibm-watsonx-ai` 1.9.1 | Provider for a 1,966-description Granite embedding subset. | `data_cache/granite_embeddings_watsonx_subset.meta.json`; audit `audit/2026-11-08-granite-final.md` |
| **IBM Granite instruct** `ibm/granite-3-8b-instruct` | Grounded explanations for the top-ranked CVEs via `cloud/explain_granite_top100.py` (optional). | `results/granite_explanations_top100.json`, `cloud/granite_instruct_model_id.txt` |
| **IBM Granite 4.2 3B** via Ollama | Separate top-100 grounded summaries; does not change the ranking. | `cloud/explain_granite_ollama.py`, `results/granite_summaries_top100.json` |

Gemini is used only as an optional executive-synthesis layer (`src/remediation_agent.py`); it is **not** IBM technology and never re-ranks CVEs. The dashboard’s upload results use the ranking’s supplied signals, not a live Gemini call.

Detailed IDs, runs, limits and caveats: **[`docs/ibm.md`](docs/ibm.md)** and **[`docs/IBM_USAGE.md`](docs/IBM_USAGE.md)**.

## API keys and environment

No key is needed for the dashboard, the backend, uploads, the sample batch, or local Ollama.

| Variable | Needed for | Notes |
|---|---|---|
| `WATSONX_APIKEY` | regenerating Granite embeddings / watsonx explanations | IBM Cloud API key; never commit |
| `WATSONX_URL` | watsonx.ai | e.g. `https://ca-tor.ml.cloud.ibm.com` |
| `WATSONX_PROJECT_ID` | watsonx.ai | project ID, not a secret |
| `GRANITE_INSTRUCT_MODEL` | Granite instruct explanations | optional; default `ibm/granite-3-8b-instruct` |
| `GEMINI_API_KEY` | optional live Gemini remediation playbooks | not required for the dashboard or uploads |
| `VITE_API_URL` | dashboard → API | `http://localhost:8000/api`; not a secret |
| `IBM_DATA_DIR` | rebuilding the model from raw IBM data | optional; folder containing `known_exploited.csv` |

Copy `.env.example` → `.env` for Granite/Gemini regeneration. `.env`, `.env.local` and keys are gitignored. See `cloud/README.md` for the Granite steps.

## Reproduce / test

```bash
# Ranking pipeline (requires data/ or IBM_DATA_DIR)
.venv/bin/python run_all.py

# API
.venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8000

# Regenerate the /results snapshot from the audited artifacts
.venv/bin/python -m server.services.results_service

# Rebuild the Granite retrieval index (drawer neighbours; not used for ranking)
.venv/bin/python cloud/build_retrieval_index.py

# Dashboard production build + tests
cd dashboard
npm run build
npm test
```

The production dashboard is `dashboard/dist/`. The API serves only read-only artifacts plus the upload scorer; it never writes to `results/`.

## Honest limits

- 2025 test has **52 positives**; one top-500 hit is about **2%**. Always read intervals.
- The final test set was already used for model selection; it is not fully held out.
- Granite was adopted by a pre-registered tie-break with **no measurable gain** (0.871 vs 0.870 mean AUC).
- `desc`/`assigner` fields are today’s values, not historical snapshots; exploitation wording is masked, but later edits cannot be ruled out.
- KEV is a proxy for exploitation; absence from KEV is not proof of safety.
- Priority scores are **ranking scores / review urgency**, not exploit probabilities.

## Documentation map

- [`docs/ibm.md`](docs/ibm.md) — full IBM Granite/watsonx.ai record
- [`docs/IBM_USAGE.md`](docs/IBM_USAGE.md) — one-page IBM usage + keys
- [`server/README.md`](server/README.md) — API endpoints and upload contract
- [`dashboard/README.md`](dashboard/README.md) — dashboard setup, engines, upload
- [`evolution/README.md`](evolution/README.md) — evolutionary search observatory
- [`docs/RESULTS.md`](docs/RESULTS.md) — consolidated metrics and evidence map
- [`docs/RETRIEVAL.md`](docs/RETRIEVAL.md) — Granite retrieval neighbours, index and limits
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — server, DNS, SSL and production checks
- [`docs/INTERFACES.md`](docs/INTERFACES.md) — data contracts
- [`audit/`](audit/) — independent audits
- [`JUDGE_QA.md`](JUDGE_QA.md) — likely judge questions
