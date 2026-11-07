# Team Interfaces — IBM Before the Breach

Contract between ranking (ML), enrichment, and Gemini triage modules.

## Ranking output: `results/scores_2026.csv`

ML ranking **must not** include free-text descriptions or reference URLs (leakage / fairness).

| Column | Type | Notes |
|---|---|---|
| `cve_id` | string | Join key |
| `rank` | int | 1 = highest priority |
| `priority_score` | float | Model score; UI label: **Priority Score** (never “X% chance of exploit”) |
| `priority` | string | `P0` / `P1` / `P2` — set by ML thresholds only |
| `reasons` | JSON string | Top model signals, e.g. `{"epss":0.42,"has_public_exploit":1}` |
| `in_top500` | bool | Convenience flag for enrichment |

## Enrichment output: `results/top500_enriched.csv`

Produced by `src/enrich_top500.py`. Joins scores with display metadata.

| Column | Source | Null handling |
|---|---|---|
| `cve_id`, `rank`, `priority_score`, `priority`, `reasons` | scores file | required |
| `description` | vulnerabilities / display cache | empty string if missing |
| `cvss_score` | `cvss3_score` (else cvss4/cvss2) | `"Pending Review"` |
| `cwe_name` / `weakness` | weakness_types join or display cache | `"Unassigned"` |
| `vendor` / `affected_products` | products / display; else `assigner` | use assigner fallback |
| `reference_urls` | references tagged patch/advisory/exploit | `[]` or empty list string |

**Score input fallback:** `results/scores_2026.csv` → else `docs/sample_scores_2026.csv`.

**Display input fallback:** `data_cache/cve_display.parquet` → else `data/vulnerabilities.csv` (+ optional refs/products) → else `docs/sample_cve_display.csv`.

## Gemini remediation playbook JSON

`src/remediation_agent.py` returns **only** this schema. Gemini **must not** choose or override `priority` / P0–P2.

```json
{
  "cve_id": "CVE-2026-0001",
  "priority_tier": "P0",
  "executive_summary": "...",
  "triage_explanation": "...",
  "immediate_mitigation": "...",
  "patch_guidance": "...",
  "is_ai_generated": true
}
```

### Guardrails

1. Ground impact on provided `description` + `weakness` only.
2. Explain priority using ML `reasons`; never invent a new tier.
3. Label score as “Priority Score” or “Rank”, never exploit probability %.
4. Patches: cite only URLs in `reference_urls`. No invented versions. If none:  
   `No verified vendor patch URL identified in advisory references — rely on interim mitigations.`
5. Workarounds: standard safe mitigations only (firewall, disable unused services, isolation).
6. Post-generation validation: product/version strings in output must appear in grounded input text.
