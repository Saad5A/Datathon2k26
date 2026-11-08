# Retrieval neighbours — CVE drawer

The dashboard's CVE drawer can show the **nearest CVEs by description similarity** for the selected CVE. This is a retrieval feature. It never scores, ranks, or changes the submitted model, and it does not contribute to any audited metric.

## Why not a vector database

The index is tiny: 2,000 vectors at 384 dimensions. A full cosine scan is a single matrix multiply and returns in about a millisecond. A vector database (Chroma, Qdrant, pgvector, FAISS) would add a service to operate and a second place for data to drift, with no user-visible benefit at this scale.

The existing in-memory index in `server/services/data_service.py` is the right tool.

## What is in the index

| Property | Value |
|---|---|
| Historical CVEs | 1,500 (the original watsonx embedding subset, 2018–2021) |
| 2026 CVEs | Top 500 from `results/top500.csv` |
| Total vectors | 2,000 (no ID overlap) |
| Dimension | 384 |
| Model | `ibm-granite/granite-embedding-small-english-r2` |
| Input | CVE description with exploitation wording masked, same mask as the text model |
| Provider | Local Hugging Face cache (`LOCAL_HF`), no API key, no token quota |
| Output | `data_cache/granite_embeddings_retrieval.parquet` + `.meta.json` |

The **ranking** model still uses `ibm/granite-embedding-278m-multilingual` via watsonx (`data_cache/granite_embeddings_watsonx_subset.parquet`). The retrieval index is a separate embedding space on purpose: the account's watsonx Lite quota was exhausted, and mixing 278m ranking vectors with 384d retrieval vectors in one matrix would be invalid.

## API

```http
GET /api/ranking/similar/CVE-2026-10523?top_k=5
```

```json
{
  "cve_id": "CVE-2026-10523",
  "top_k": 5,
  "similar": [
    {
      "cve_id": "CVE-2021-44228",
      "similarity": 0.91,
      "score": null,
      "rank": null,
      "published": null,
      "scope": "historical pool"
    }
  ],
  "index": {
    "model_id": "ibm-granite/granite-embedding-small-english-r2",
    "dimension": 384,
    "rows": 2000,
    "purpose": "retrieval-only (CVE drawer neighbours); never used for scoring or ranking"
  },
  "note": "Description-similarity neighbours. Retrieval evidence only, not a probability of exploitation."
}
```

A historical neighbour has no 2026 score, so `score` and `rank` are `null` and `scope` says `historical pool`. A 2026 neighbour carries its rank and score.

## Rebuild

```bash
.venv/bin/python cloud/build_retrieval_index.py          # full top-500 index, ~10 min on CPU
.venv/bin/python cloud/build_retrieval_index.py --top 100 # faster subset
```

The script reads the existing historical IDs, the top 500 from `results/top500.csv`, and descriptions from `data_cache/backtest_pool.parquet` + `data/vulnerabilities.csv`. It never writes to `results/`.

`data_cache/*.parquet` is gitignored, so the generated index is deployed as an artifact and is not committed. Rebuild it from the command above if it is missing.

## Deploy

```bash
rsync -az data_cache/granite_embeddings_retrieval.parquet \
  data_cache/granite_embeddings_retrieval.meta.json \
  root@64.177.59.101:/opt/pancakess/data_cache/
systemctl restart pancakess-api
curl -s http://64.177.59.101/api/ranking/similar/CVE-2026-10523?top_k=5
```

`GET /api/health` reports `similarity_rows` and `similarity_model`.

## Limits

- Retrieval covers **the historical pool plus the 2026 top 500**, not all 72,670 CVEs.
- Similarity is not a probability of exploitation and is not a model feature.
- The historical neighbours have no 2026 outcome; we do not claim they were exploited.
- No AUC, top-500, or accuracy claim is attached to this feature.
- The 2026 queue's ranking is unchanged; `results/top500.csv` and `results/scores_2026.csv` remain the audited artifacts.

## UI

The panel is in `dashboard/src/components/dashboard/CveInspectionDrawer.tsx` under **“Nearest neighbours · IBM Granite”**. It is labelled as retrieval evidence and names the embedding model and index size.

## Tests

- `dashboard/src/components/dashboard/CveInspectionDrawer.test.tsx` asserts the neighbour panel renders with the disclaimer and model id.
- Backend smoke test: `curl /api/ranking/similar/CVE-2026-10523?top_k=5`.
