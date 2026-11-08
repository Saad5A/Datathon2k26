# Interfaces — scoring output & dashboard contract

This is the contract between the Python model pipeline and the triage dashboard
(`dashboard/`). The dashboard's mock data, CSV export, upload parser and
`/predict` client all follow it.

## 1. Scores file (`outputs/scores_2026.csv`)

One row per CVE. RFC 4180 CSV, UTF-8, header row required. Quotes inside a
field are doubled (`""`), which is pandas' default `to_csv` behaviour.
See [`sample_scores_2026.csv`](sample_scores_2026.csv) for a minimal example.

```
cve_id,published,snapshot_month,assigner,score,rank,percentile,in_top500,priority,epss,exploitdb,metasploit,nuclei,poc_github,any_public_exploit,reasons,model_version
```

| Column | Type | Notes |
|---|---|---|
| `cve_id` | string | `CVE-YYYY-NNNN+`. Unique. |
| `published` | string | `YYYY-MM-DD` |
| `snapshot_month` | string | `YYYY-MM`, month the features were frozen |
| `assigner` | string | CNA short name |
| `score` | float | 0.000 – 1.000. Uncalibrated ranking score; compare by rank, not as a probability. |
| `rank` | int | 1 … N (N = 72,670 for the 2026 set). Unique, 1 = highest risk. |
| `percentile` | float | 0.0 – 100.0, `round(100 × (1 − (rank − 1) / N), 1)` |
| `in_top500` | int | 1 if `rank ≤ 500` |
| `priority` | string | `P0` \| `P1` \| `P2` (see §2) |
| `epss` | float \| empty | EPSS at snapshot. Empty when not yet scored. |
| `exploitdb` | int | 0/1 |
| `metasploit` | int | 0/1 |
| `nuclei` | int | 0/1 |
| `poc_github` | int | 0/1 |
| `any_public_exploit` | int | 0/1, OR of the four flags above |
| `reasons` | JSON string | Top signals behind the score, highest impact first (see §3) |
| `model_version` | string | e.g. `v0` |

## 2. Priority bands

| Priority | Rule | Meaning |
|---|---|---|
| **P0** | `percentile ≥ 99.85` (≈ top 100 of 72,670) | Patch now |
| **P1** | `percentile ≥ 90` | Schedule this cycle |
| **P2** | everything else | Routine |

Defined in `dashboard/src/lib/scoring.ts` (`P0_MIN_PERCENTILE`, `P1_MIN_PERCENTILE`).
Bands use percentile, not absolute rank, so they still make sense for a small judge upload.

## 3. `reasons`

```json
[{ "signal": "assigner_kev_rate", "value": 0.071, "impact": 0.82, "direction": "up" }]
```

| Field | Type | Notes |
|---|---|---|
| `signal` | string | snake_case feature name |
| `value` | number \| string \| null | Feature value for this CVE |
| `impact` | float | Relative contribution, 0–1 |
| `direction` | `"up"` \| `"down"` | Raises or lowers risk |

`[]` is valid (no signal cleared the explanation threshold).

## 4. `POST /predict`

The dashboard's "Evaluate dataset → Model API" mode calls this endpoint at
`${VITE_API_URL}/predict`. The browser calls the backend directly (no proxy), so
the backend must allow the app's origin via CORS; see `dashboard/README.md`.
Timeout: 60 s.

**Request** (`Content-Type: application/json`)

```json
{ "rows": [ { "cve_id": "CVE-2026-12345", "published": "2026-05-14", "assigner": "microsoft",
              "epss": 0.03, "exploitdb": 0, "metasploit": 0, "nuclei": 0, "poc_github": 1 } ] }
```

Rows are passed through as parsed from the uploaded file, so extra columns may be present.

**Response** — `200`, JSON: either an array of §1 rows or `{ "rows": [...] }`.
`score` is required on every row. `reasons` may be a JSON string or an array.
If `rank`, `percentile` and `priority` are present on every row and ranks are
unique, the dashboard keeps them; otherwise it ranks by `score` within the batch.

## 4a. `GET /health`

Used by the footer "API status" indicator (every 60 s and on click). Any `2xx`
response means online; the body is ignored. Timeout: 5 s.

## 5. Judge uploads (CSV / JSON)

Accepted by the dashboard's upload modal:

- **CSV** with a header row, or **JSON** as an array of objects or `{ "rows": [...] }`.
- Only `cve_id` is required. `published, assigner, epss, exploitdb, metasploit, nuclei, poc_github`
  feed the in-browser scorer when present.
- If every row already has `score`, the file is treated as pre-scored and shown as-is
  (unless "Re-score" is ticked).
- Duplicate `cve_id`s keep the first occurrence. Limit 50 MB.
