# IBM software usage

The project uses IBM Granite models and IBM watsonx.ai. IBM technology is part of the ranking and explanation layers; the dashboard and upload API do **not** need IBM credentials at runtime because they read committed artifacts.

## 1. Granite embeddings — the ranking model

| Item | Value |
|---|---|
| Model | `ibm/granite-embedding-278m-multilingual` |
| Hugging Face | `ibm-granite/granite-embedding-278m-multilingual`, revision `a9cb5338491faf32b73dd17b714a31821c021bbf` |
| Vector | 768 numbers per description, L2-normalised |
| Input limit | 512 tokens |
| Providers | IBM watsonx.ai (`ca-tor`) for a 1,966-row subset; open weights on Hugging Face/Colab for the full 147,818 descriptions |
| Used in | `src/model/granite.py`, `cloud/embed_granite.py`; the G1/G2 pre-registered test |
| Result | **G2 adopted** (C1 + Granite text), mean AUC 0.871 vs 0.870 for C1; no measurable gain. Top-500: 20 vs 22 (fold 1), 11 vs 11 (fold 2) |
| Files | `results/scores_2026.csv`, `results/top500.csv`, `results/granite_comparison.json`, `results/claims_model_granite.json` |
| Audit | `audit/2026-11-08-granite-final.md` |

The pre-registered rule (written before results) is in `LOG.md` and `src/model/granite.py`: adopt the better of G1/G2 if its mean AUC is within 0.01 of C1. G2 won the tie-break; it is not claimed as an improvement.

## 2. Granite instruct — grounded explanations

| Item | Value |
|---|---|
| Model | `ibm/granite-3-8b-instruct` (watsonx.ai) |
| Code | `cloud/explain_granite_top100.py` |
| Output | `results/granite_explanations_top100.json` |
| Scope | Top-ranked CVEs; facts are grounded in the CVE record + model reasons |
| Key | `WATSONX_APIKEY`, `WATSONX_URL`, `WATSONX_PROJECT_ID` |

## 3. Granite 4.2 3B via Ollama — separate summary layer

| Item | Value |
|---|---|
| Model | Ollama `granite4.2:3b` (IBM Granite 4.2 3B) |
| Code | `cloud/explain_granite_ollama.py` |
| Output | `results/granite_summaries_top100.json` |
| Key | none (local CPU) |
| Scope | Top-100 summaries only; does not change the ranking |
| Grounding | 94 summaries passed grounding, 6 deterministic-template fallbacks; fallbacks are not labelled AI-generated |

## 4. IBM watsonx.ai

- IBM Cloud region: Toronto (`ca-tor`), service URL `https://ca-tor.ml.cloud.ibm.com`.
- SDK: `ibm-watsonx-ai` 1.9.1.
- The free Lite plan was used for a 1,966-description subset; the full embedding run used the same open weights locally because the quota was exhausted.
- Evidence: `data_cache/granite_embeddings_watsonx_subset.meta.json`, `audit/2026-11-08-granite-final.md`.
- The watsonx and local vectors agree: min cosine 0.999982, mean 0.999988 on the 1,500 overlapping rows.

## 5. What is not IBM

Gemini (`gemini-2.5-flash`) is a separate, optional executive-synthesis layer in `src/remediation_agent.py` / `scripts/build_gemini_from_granite.py`. It never re-ranks CVEs and is not required by the dashboard or upload API. Cached Gemini-template artifacts without live provenance are not served as live Gemini output.

## API keys

| Variable | Required? | Use |
|---|---|---|
| `WATSONX_APIKEY` | only to regenerate Granite artifacts | IBM Cloud IAM API key |
| `WATSONX_URL` | only to regenerate | `https://ca-tor.ml.cloud.ibm.com` |
| `WATSONX_PROJECT_ID` | only to regenerate | watsonx.ai project ID |
| `GRANITE_INSTRUCT_MODEL` | optional | defaults to `ibm/granite-3-8b-instruct` |
| `GEMINI_API_KEY` | optional | live Gemini playbooks; not needed for ranking/upload |
| `VITE_API_URL` | dashboard only | API origin, not a secret |

Nothing above is needed to run `uvicorn server.app:app`, `npm run dev`, upload a CSV/JSON, use the sample batch, or run local Ollama.

## Detailed record

The long-form record, including model IDs, SDK calls, quotas, pricing notes and the full Granite test, is in [`docs/ibm.md`](ibm.md).
