# Before the Breach — Model write-up (IBM track)

**Branch:** `feat/model-ranking`  
**Judged artifact:** `results/top500.csv` (500 CVE IDs). Full ranking table: `results/scores_2026.csv`.

## Problem

Security teams cannot patch every CVE. Severity (CVSS) answers “how bad if hit,” not “will attackers hit this.” We rank the IBM 2026 scoreboard so defenders know what to fix first, using only information available at each CVE’s snapshot month. Labels in backtests are later CISA KEV membership (a proxy for exploitation, not ground truth).

## System architecture (hybrid local + watsonx.ai)

1. **Local ingestion:** Raw IBM CSVs under `data/` → time-safe feature pool and masked descriptions (`cloud/make_embed_input.py` → `data_cache/descriptions_to_embed.parquet`).
2. **Cloud embeddings (Toronto `ca-tor`):** IBM watsonx.ai Runtime embeds masked text with **`ibm/granite-embedding-278m-multilingual`** (768-dimensional, L2-normalised, truncate at 512 tokens) via `cloud/embed_granite.py` (`ibm-watsonx-ai` SDK, concurrency 1).
3. **Downstream ranking:** scikit-learn HistGradientBoosting / logistic regression on local features; Granite vectors are an alternate **text** signal evaluated on the embedding-covered slice (`src/model/granite_subset_eval.py`). The production ranking recipe and leakage rules remain under local control.

Committed watsonx artifacts (do not re-call the API to regenerate):

| Artifact | Content |
|---|---|
| `data_cache/granite_embeddings_watsonx_subset.parquet` | 1,500 rows × 768-d vectors (meta: 1,489 unique texts; 1,469 newly embedded this run) |
| `data_cache/granite_embeddings_watsonx_subset.meta.json` | Provider `WATSONX`, model id above, **estimated_tokens_this_run = 233,097** |
| `data_cache/granite_embeddings_watsonx_evalslice.parquet` | 466 rows (eval-id slice; ~46,051 estimated tokens this run) |
| Combined eval coverage | **1,966** vectors in `results/granite_subset_comparison.json` |

## Quantitative performance (baseline TF-IDF text vs Granite text)

Source: `results/granite_subset_comparison.json` and `results/claims_model_granite.json`.  
**Caveat (from the comparison file):** metrics are only on CVEs that have embeddings—a partial watsonx Lite slice, **not** the full pre-registered corpus adoption test.

| Fold | Covered test rows (positives) | TF-IDF text LR AUC | Granite text LR AUC | Δ AUC (Granite − TF-IDF) | Top-50 hits (TF-IDF → Granite) | Top-100 hits | Recall@500 |
|---|---:|---:|---:|---:|---|---|---|
| fold1 | 718 (52) | 0.6794 | **0.6981** | **+0.0187** | 8 → **11** | 16 → **22** | 0.8846 → **0.9231** |
| fold2 | 557 (32) | 0.5923 | **0.6392** | **+0.0469** | 4 → **6** | 7 → **8** | 0.9375 → **0.9688** |

- **Mean Δ AUC (Granite − TF-IDF):** **0.0328** (`p6.granite_subset.mean_delta_auc`).
- **Selection hint in comparison JSON:** prefer `granite_text_lr` when mean AUC delta ≥ −0.01 vs TF-IDF on covered folds.

Average precision also rises on both covered folds (fold1: 0.1324 → 0.2148; fold2: 0.0759 → 0.1194).

## Generative explainability

- **`results/granite_explanations_top100.json`:** natural-language risk rationales keyed by `cve_id` (current committed file: **30** explanations; fields include `priority`, `rank`, `explanation`, `is_ai_generated`, `grounding_ok`; provider recorded as `offline_template` in this artifact). Script: `cloud/explain_granite_top100.py`. Grounding check requires product/version/URL phrases to appear in the grounded input.
- **`results/sample_playbooks.json`:** sample automated remediation playbooks (structured sections such as executive summary, triage explanation, immediate mitigation, patch guidance), labelled AI-generated, for UI/triage handoff demos.

Explanations consume ranking outputs (`priority` / `rank` / model `reasons`) and CVE description text; they must not invent patch versions or URLs.

## Resource & budget governance

watsonx.ai Runtime **Lite** foundation-model allowance is **300,000 tokens/month** (`docs/ibm.md`). The main subset run recorded **233,097 estimated tokens** (chars/4, capped at 512/text) for the 1,500-row embed—within Lite—while the full description corpus estimate is on the order of **16.8M** tokens (`results/embed_input_summary.json`), so full-corpus watsonx is out of Lite scope. Teammates reuse `*.parquet` under `data_cache/` **offline**; no live credentials are required to consume vectors.

## Leakage & honesty (ranking model)

Production features exclude post-breach NIST completeness fields (`nvd_status`, product/reference counts, blank-score patterns, news/threat links). Scores are **Priority Scores / ranks**, never “X% chance of exploit.” **No 2026 accuracy claim**—there are no 2026 KEV labels for self-scoring.

## Reproduce (local, no cloud)

```text
# Use committed embeddings + comparison (do not re-embed):
# data_cache/granite_embeddings_watsonx_*.parquet
# results/granite_subset_comparison.json
python src/model/granite_subset_eval.py   # if regenerating comparison from local parquets only
```

Claims ledger for Granite subset lift: `results/claims_model_granite.json`. Full ranking claims: `results/claims_model*.json` / `audit/`.
