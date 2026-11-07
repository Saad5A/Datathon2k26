# Backtest features (src/model/pool.py, src/model/reproduce_first_pass.py)

Snapshot month `ym` = the CVE's `published` month. Snapshot end = last day of `ym`.
"Cannot leak" below means: the value is fixed from data dated on or before the snapshot end.
Where that cannot be shown from the data, the row says so. Status: unaudited.

## Pool and label

| Item | Source column | As-of logic | Why it cannot leak |
|---|---|---|---|
| pool row | vulnerabilities.csv `published` | CVEs published 2024-01..2025-09. Dropped if `in_kev`=1 in that month's signal row or KEV `date_added` <= snapshot end | Uses only the snapshot-month signal row and KEV dates on or before the snapshot end. Caveat: vulnerabilities.csv is today's file, so CVEs rejected later are already gone (survivor effect, not a feature) |
| `y` (label) | known_exploited.csv `date_added` | 1 if `date_added` is in (snapshot end, min(snapshot end + 365 days, 2025-12-31)] | A label, not a feature. Training labels of 2024 snapshots do use KEV additions in 2025 (overlap with the test period); section B of first_pass_repro.json measures this |

## Features of the signals+assigner+text model (`BEST_FEATURES`)

| Feature | Source column | As-of logic | Why it cannot leak |
|---|---|---|---|
| `epss_f` | exploit_signals_20xx.csv `epss` | Row with `month` == snapshot month; -1 if no row or blank | The signal files are as-of month-end values (DATA_DICTIONARY.md). Joined on (`cve_id`, `month`), checked in checks.py for 2025-03 |
| `exploitdb`, `metasploit`, `nuclei`, `poc_github` | same file, same columns | Same row; 0 if no row | As above |
| `anyx`, `nx` | the four flags | max and sum of the four flags | Derived only from as-of flags |
| `asg_rate` | KEV `date_added`, vulnerabilities `assigner`, `published` | KEV rows with `date_added` < first day of snapshot month, divided by (CVEs published before that day + 20), per assigner. Only CVEs published 2021+ count, as in the first pass | Only rows dated strictly before the snapshot month enter. checks.py drops or moves later KEV rows and confirms no change. Caveat: `assigner` is today's value of the field; we assume it does not change after publication |
| `asg_kev` | same | KEV count part of the above | Same |
| `txt` | vulnerabilities `description` | TF-IDF (fitted on training rows only) + logistic regression. Training rows get out-of-fold scores (5 folds); test rows get a model fit on all training rows | Labels: only training labels are used. Time: NOT proven. `description` is today's NVD text and may have been edited after publication. Section H of first_pass_repro.json counts descriptions with exploitation wording ("actively exploited", "CISA", ...): this is a known leak risk |

## Comparison-only columns (first-pass table rows; not in `BEST_FEATURES`)

| Feature | Source | Note |
|---|---|---|
| `cvss3` | `cvss3_score`, blank -> -1 | NVD analysis field, today's version. The -1 encodes a blank-score pattern, which AGENTS.md rule 4 bans as a model feature. Used in the CVSS3 baseline and the "structured" HGB rows only |
| `*_c` (8 attack-vector fields) | `attack_vector` ... `availability_impact` as category codes | Today's NVD analysis values; blank -> -1 (blank pattern). Codes are fixed over the whole pool (alphabetical) |
| `cwe_<id>` (top 40), `cwe_` (blank CWE) | first entry of `cwe_ids` | Today's NVD values. The top-40 list is picked over the whole pool including test rows (no labels used), as in the first pass |
| `ncpe` | `n_affected_cpes` | LEAKY. Only in the "LEAKY + n_affected_cpes" row to show what leakage buys. Never a model feature |
| `nvd_status`, `n_references` | | Kept in the cache for leak comparisons; never features |
