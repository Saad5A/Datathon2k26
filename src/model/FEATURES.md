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

## Phase 3 features (src/model/candidates.py)

Status: unaudited. Pre-registration: LOG.md "PRE-REGISTRATION, Phase 3".

| Feature | Source column | As-of logic | Why it cannot leak |
|---|---|---|---|
| `asg24_kev` | KEV `date_added`, vulnerabilities `assigner` | Per assigner: KEV rows with `date_added` in [first day of snapshot month - 24 months, first day of snapshot month). Assigner comes from vulnerabilities.csv, CVEs published 2021+ only (same join as `asg_kev`) | `assigner_window` filters on `date_added < start` and asserts it; `checks.py check_assigner_window` drops, moves later or pulls in KEV rows and confirms only rows inside the window change the value. Same caveat as `asg_rate`: `assigner` is today's value |
| `asg24_rate` | same + vulnerabilities `published` | `asg24_kev` / (CVEs by that assigner published in the same 24-month window + 20). An assigner with KEV rows but no CVE published in the window gets count / 20 (the all-history feature gives 0 in that case) | Same as above; CVEs published on/after the month start do not enter the denominator (checked) |
| `epss0`, `epss_missing` (C3 only) | exploit_signals `epss` | Snapshot-month EPSS with blank -> 0, plus a 0/1 blank indicator, in place of `epss_f` (blank -> -1) | Same row as `epss_f` |
| `txt` (masked) | vulnerabilities `description` | Before TF-IDF, every match of harness `EXPLOIT_WORDING` ("exploited in the wild", "actively exploited", "CISA", "KEV", ...) is replaced by a space, case-insensitive, in train and test rows. TF-IDF and the text LR are fitted on train rows only; train rows get 5-fold out-of-fold scores | Removes the known post-hoc wording only. `description` is still today's text: other later edits cannot be detected from this data |
| `s_*` (ablation `plus_structured` only) | `cvss3_score`, 8 CVSS vector fields, first `cwe_ids` entry | cvss3 blank -> 0 + `s_cvss3_missing`; one-hot of the vector fields (blank is its own category) and of the top-40 first CWE, all vocabularies fitted on the fold's train rows; unseen test categories -> all zeros | Not a model feature. Today's NVD analysis values; the blank indicators are blank-score patterns (AGENTS.md rule 4), allowed only inside this one ablation |

Deviation D1 (recorded after the Phase 3 audit): the 24-month window counts only KEV additions whose CVE was
published 2021 or later, because the assigner is joined from vulnerabilities.csv rows published 2021+ (the same
join as the all-history `asg_kev`). Older CVEs added to KEV inside the window are not counted. It did not affect the
selection: the selected model C1 uses the all-history feature, not `asg24_*`.

`plus_structured` uses excluded blank-score fields (`s_cvss3_missing`, the "blank" CVSS vector categories). It is a
comparison row only and can never be adopted as a model.

## 2026 scoring rows (src/model/cap.py preview; unaudited)

Scoreboard rows take `epss`, the four flags (`anyx`, `nx` derived) from scoreboard_2026.csv itself, at its
`snapshot_month` (blank EPSS -> -1 as in the pool). `assigner` and `description` (masked) are joined from
vulnerabilities.csv. `asg_rate` / `asg_kev` are computed as of the first day of each row's `snapshot_month` from KEV
rows dated before it and CVEs published before it (June 2026 CVEs have snapshot 2026-07, so their history runs to
2026-07-01). C1 is refitted on all 75,148 pool rows with pool labels (KEV to 2025-12-31).
