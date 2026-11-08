# IBM Granite integration notes

Branch: `feat/ibm-granite`. Scaffold for watsonx.ai Toronto (`ca-tor`) + local Hugging Face
Granite embeddings. **Do not treat subset numbers below as audited production claims** — they are
preliminary, leakage-aware experiment notes only.

## Architecture

```
vulnerabilities.csv
        │
        ▼
cloud/make_embed_input.py
        │  masks exploitation wording (same as TF-IDF path)
        ▼
data_cache/descriptions_to_embed.parquet   (147,818 rows: cve_id, text)
        │
        ├─ provider WATSONX ──► ibm/granite-embedding-278m-multilingual (768-d)
        │                         cloud/embed_granite.py --provider WATSONX
        │                         Lite: ~300k tokens/month → subset only
        │
        └─ provider LOCAL ───► ibm-granite/granite-embedding-278m-multilingual
                                  cloud/embed_granite.py --provider LOCAL
                                  Colab: cloud/colab_embed_local.py (T4/A100)
                                  max_seq_length = 512 tokens/text (hard truncate)

embeddings parquet ──► optional feature join in ranking baseline
        │
        ▼
results/scores_2026.csv (ranking; protected on this branch)
        │
        ▼
cloud/explain_granite_top100.py
        │  model: ibm/granite-3-8b-instruct (or GRANITE_INSTRUCT_MODEL /
        │         cloud/granite_instruct_model_id.txt). No LLaMA fallback.
        ▼
results/granite_explanations_top100.json
```

Detection helper: `python cloud/list_granite_instruct.py` (enums + IAM-authenticated
`foundation_model_specs` on `ca-tor`). Writes `cloud/granite_instruct_model_id.txt`.

## Token governance

| Item | Value | Notes |
|------|-------|-------|
| Embedding model limit | **512 tokens / text** | Enforced via watsonx `TRUNCATE_INPUT_TOKENS` and LOCAL `max_seq_length` |
| Lite plan FM tokens | **300,000 / month** | watsonx.ai Runtime Lite (see `docs/ibm.md`) |
| Script default refuse | **250,000** estimated tokens | `--max-tokens` on WATSONX path |
| Full corpus estimate | **~16.8 M tokens** | 147,818 texts × chars/4 capped at 512 — ESTIMATE |
| Watsonx subset (ran) | **1,500 rows**, **~233,097** estimated tokens this run | `data_cache/granite_embeddings_watsonx_subset.meta.json` |
| Eval slice | separate `*_evalslice` artifacts | for holdout-style checks only |
| LOCAL Colab batch | T4 **256**, A100 **512** texts / cache commit | encode micro-batch ≤128; truncate 512 |

Rules of thumb:

- Full corpus → **LOCAL / Colab GPU** only (Lite cannot finish 16.8 M tokens).
- Watsonx → `--limit` / `--ids` only until a paid plan is confirmed.
- Never commit `.env`, API keys, or the ~450 MB full `granite_embeddings.parquet`.

## Instruct model availability (ca-tor, verified 2026-11-07/08)

Configured target: **`ibm/granite-3-8b-instruct`**.

Authenticated catalog on this Lite project listed embedding / base / TTM Granite IDs and
third-party instruct models, but **no `ibm/granite-*-instruct` IDs**. Probe generate calls for
`ibm/granite-3-8b-instruct` (and 13b instruct v2) returned `not supported for this environment`.
`explain_granite_top100.py` therefore targets Granite instruct only and falls back to the
**offline template** when watsonx rejects the model — it does **not** call LLaMA.

When the Runtime / plan enables a Granite instruct model, re-run
`python cloud/list_granite_instruct.py` and/or set `GRANITE_INSTRUCT_MODEL=...`.

## Preliminary subset observations (UN-AUDITED)

> **UN-AUDITED — do not copy into judge-facing claims without re-validation.**

- Watsonx embedding subset (`limit=1500`, model `ibm/granite-embedding-278m-multilingual`,
  dim 768, L2-normalised) completed under the Lite token ceiling (~233k estimated tokens).
- Eval-slice and subset comparison JSON under `results/` / `data_cache/` are exploratory;
  ranking deltas vs TF-IDF / LightGBM baselines are **not** locked as official metrics here.
- Grounding checks for instruct explanations reject invented patch versions/URLs; offline
  templates remain the safe path until Granite instruct is enabled on the project.

## Related files

| Path | Role |
|------|------|
| `cloud/embed_granite.py` | WATSONX + LOCAL embedders, cache, token gate |
| `cloud/colab_embed_local.py` | Colab/T4/A100 wrapper for full 147,818-row LOCAL run |
| `cloud/explain_granite_top100.py` | Granite instruct explanations (no LLaMA) |
| `cloud/list_granite_instruct.py` | Detect / record instruct model id |
| `cloud/README.md` | Operator steps (Colab Option A, watsonx Option B) |
| `docs/ibm.md` | Model IDs, plan limits, sources |
