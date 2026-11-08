# First-pass findings [MEASURED-UNAUDITED unless stated]
Produced by `_probe/ibm/build.py`, `model1.py`, `model2.py` on 2026-11-07 (Sonnet planning session). None of this may be published until the auditor verifies it and it is in `results/claims_model.json`.

## Backtest setup
Rows: CVEs published 2024-01..2025-09, snapshot = publish month, excluding CVEs already on KEV at snapshot. Label = added to KEV after the snapshot month end, within 12 months, capped at 2025-12-31. Train = 2024 snapshots (39,868 rows, 65 positives). Test = 2025-01..2025-09 (35,280 rows, 52 positives, base rate about 0.15%). Combined 2024-01..2025-09 pool: 75,148 rows, 117 positives.

## Results (test pool)
| Approach | top500 | top1000 | AUC | Avg precision | Median rank of positives |
|---|---|---|---|---|---|
| CVSS3 | 6 | 9 | .732 | .0064 | 7,884 |
| EPSS | 8 | 13 | .707 | .0309 | 3,376 |
| exploit flag then EPSS | 19 | 22 | .768 | .0471 | 2,496 |
| assigner KEV-rate only | 13 | 15 | .746 | .0109 | 6,075 |
| HGB signals only | 20 | 22 | .726 | .0368 | 2,652 |
| HGB signals+structured (CVSS/CWE/vector) | 19 | 20 | .803 | .0627 | 3,551 |
| HGB signals+assigner | 16 | 24 | .884 | .0727 | 1,190 |
| HGB signals+structured+assigner | 14 | 24 | .879 | .1032 | 1,634 |
| text-only TF-IDF LR | 9 | 14 | .814 | .0100 | 3,379 |
| HGB all + text score | 21 | 25 | .883 | .1142 | 1,103 |
| **HGB signals+assigner+text score (best)** | **25** | **28** | **.886** | **.1050** | **829** |
| LEAKY: + n_affected_cpes (never use) | 27 | 29 | .913 | .1315 | 421 |

HGB = scikit-learn HistGradientBoosting (depth 3, 150 iterations, lr .05, min leaf 40, L2 5), mean of 3 seeds. Text score = out-of-fold TF-IDF (1-2 grams, min_df 8, 30k features) logistic regression.
Caveats: only 52 positives (one hit is about 2%); several variants were compared on the same test set (selection optimism); the 2026 pool is about twice as large, so top 500 there is a stricter cut (about top 250 here).
Takeaway: the gain is clear in ranking quality (AUC, median rank), small and noisy in top-500 hits.

## Leakage: solo AUC on the 2025 test pool
analyzed status .675, n_affected_cpes .767, n_references .643, cvss3 score .732, EPSS .707, any exploit flag .701, assigner KEV-rate .746, cvss3-blank .481 (no signal).

## Signals and text
- Assigner (issuer) KEV counts in known_exploited.csv, among CVEs published 2021+ that we could map (813 of 1,484 KEV rows): secure@microsoft.com 159, cve@mitre.org 131, product-security@apple.com 65, chrome-cve-admin@google.com 53, psirt@cisco.com 24, security@vmware.com 22, security-advisories@github.com 22, security@apache.org 18, support@hackerone.com 17, psirt@fortinet.com 16, psirt@adobe.com 15, mobile.security@samsung.com 13.
- Top positive words in the text model include: "remote unauthenticated", "unauthenticated attacker", "windows kernel", "kernel elevation", "sharepoint", "outlook", "microsoft outlook", "error reporting", "net framework", "webmail". The text model partly re-learns vendor identity.
- Of the 52 test positives, 22 had any public exploit flag at snapshot and only 4 had EPSS above 0.1 (first backtest pass, 2025 Jan-Sep).
- KEV additions per year in the file: 2021 311 (from Nov), 2022 555, 2023 187, 2024 186, 2025 245.
- CAVEAT (correction): "all 52 test positives come from assigners with a prior KEV" and "25% of the 2026 pool is from assigners with no KEV history" were computed against the WHOLE KEV file, not time-safely. Treat both as unverified until recomputed with only KEV additions before each snapshot.

## 2026 distribution shift
- Published CVEs per month: about 3,600-4,300 through 2025; 2026: Jan 4,302, Mar 6,234, Jun 7,942, Jul 9,770, Aug 12,256, Sep 14,928.
- Scoreboard rows by snapshot month: Jan 4,295; Feb 4,603; Mar 6,227; Apr 5,801; May 6,922; Jul (incl. June) 17,678; Aug 12,242; Sep 14,902.
- Assigner share 2026 vs 2025 test pool: GitHub advisories 15.0% vs 5.6%; VulnCheck 9.3% vs 1.1%; Oracle 4.2% vs 0.7%; Chrome admin 4.0% vs 0.3%; Microsoft 4.0% vs 2.6%; Patchstack 5.6% vs 15.8%; VulDB 7.4% vs 13.4%; MITRE 4.6% vs 10.7%.
- CVEs with zero affected-product rows: about 28-43% per month in 2025 (50% in Dec 2025), 66-68% in Aug-Sep 2026. Blank CVSS3: about 1-8% per month Jan-Oct 2025 (16% in Dec 2025), 14-16% in Aug-Sep 2026.
- Any public exploit flag: 2.26% in the 2026 scoreboard (1,645 CVEs) vs 2.15% in 2025 test. EPSS blank: 2% vs 10%. EPSS above 0.1: 66 CVEs in the 2026 scoreboard.

## Changelog
- 2026-11-07: created.
- 2026-11-07: corrected 2025 missing-data ranges after re-checking the monthly table.
