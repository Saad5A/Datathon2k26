# First-pass findings [MEASURED-UNAUDITED unless stated]
Produced by `_probe/ibm/build.py`, `model1.py`, `model2.py` on 2026-11-07 (Sonnet planning session). None of this may be published until the auditor verifies it and it is in `results/claims_model.json`.

## Backtest setup
Rows: CVEs published 2024-01..2025-09, snapshot = publish month, excluding CVEs already on KEV at snapshot. Label = added to KEV after the snapshot month end, within 12 months, capped at 2025-12-31. Train = 2024 snapshots (39,868 rows, 65 positives). Test = 2025-01..2025-09 (35,280 rows, 52 positives, base rate about 0.15%). Combined 2024-01..2025-09 pool: 75,148 rows, 117 positives.

## Results (test pool), VERIFIED [audit/2026-11-07-harness.md; values from results/claims_model.json, feat/model-ranking]
Ties broken by cve_id; "range" = worst..best over all orders of rows tied at rank 500. Train labels use KEV additions up to 2025-12-31 (overlaps the test period; see the honest estimate below).

| Approach | top500 | range | top250 | AUC | Avg precision | CVEs to fix to catch 50% |
|---|---|---|---|---|---|---|
| CVSS3 | 5 | 5..17 | 5 | 0.732 | 0.0064 | 7,952 |
| EPSS | 8 | 8..8 | 8 | 0.707 | 0.0309 | 3,273 |
| exploit flag then EPSS | 18 | 18..19 | 15 | 0.768 | 0.0471 | 2,253 |
| assigner KEV-rate only | 13 | 11..13 | 8 | 0.746 | 0.0109 | 6,011 |
| HGB signals only | 18 | 18..22 | 15 | 0.725 | 0.0369 | 2,777 |
| HGB signals+assigner | 17 | 16..17 | 14 | 0.880 | 0.0727 | 1,182 |
| text-only TF-IDF LR | 9 | 9..9 | 7 | 0.814 | 0.0100 | 3,087 |
| HGB signals+assigner+text score | 25 | 25..25 | 16 | 0.888 | 0.1057 | 686 |

Structured CVSS/CWE rows and the LEAKY n_affected_cpes row: reproduced but UNCHECKED by the audit; do not quote.

**Honest estimate (time-safe train labels, KEV additions up to 2024-12-31 only, which mirrors the 2026 setup):** best model top500 21, AUC 0.871, from 40 train positives. Seed spread of the best model with the original labels: top500 21..25 over 10 seed sets.
**Second fold (train 2024-07..2025-03, test 2025-04..09, 32 positives):** best model top500 11 (AUC 0.861) vs exploit-then-EPSS 15 (AUC 0.809).
**What holds:** the gain in ranking quality (AUC, CVEs to fix to catch 50%) over every baseline, in both folds and with time-safe labels. **What does not hold:** a top-500 win over exploit-then-EPSS (reverses in fold 2). CVSS3 top500 depends on tie order (see range).
Early stopping: HGB uses scikit-learn default early stopping (on above 10,000 rows), so "150 iterations" is a maximum; actual per seed: 150, 138, 55.

## Verified findings, Phase 3 to final (feat/model-ranking) [VERIFIED; generated from results/claims*.json, audits in audit/2026-11-07-*.md]
Do not quote the first-pass table below; quote these. Wording rules are in LOG.md on feat/model-ranking.

**1. Hidden leak in today's NVD fields** (2025 test pool). All 52 later-exploited CVEs had NVD status Analyzed, a product row, CVSS3 and CWE (exact 95% lower bound on each share 0.932); among non-exploited CVEs: Analyzed 50.1%, product row 64.9%. Solo AUC (EPSS 0.707): n_affected_cpes 0.767, ref Exploit tag 0.690, nvd_status 0.675, news/threat links 0.652 (lower bound), n_references 0.643. None is used by the model. Full table: results/leakage_table.csv.

**2. Honest backtest (time-safe train labels, pre-registered selection, 5 seed sets, seed medians).** Selection rule picked C1 (mean AUC C1 0.870, C2 0.848, C3 0.836).

| Fold | Method | top500 | AUC | CVEs to catch 50% |
|---|---|---|---|---|
| 1 (test 2025-01..09) | C1 (seed range 15..22) | 22 | 0.860 | 1,226 |
| 1 | exploit then EPSS | 18 | 0.768 | 2,253 |
| 2 (test 2025-04..09) | C1 (seed range 11..12) | 11 | 0.880 | 1,240 |
| 2 | exploit then EPSS | 15 | 0.809 | 510 |

Paired difference C1 minus exploit-then-EPSS (seed median): AUC +0.092 / +0.071; expected top-500 +3.6 / -3.6. Seed set 0 AUC interval includes 0 in both folds. So: higher AUC but borderline (seed set 0 interval includes 0), NO robust top-500 advantage; never claim we beat the baselines on top-500. Note: the 2025-01..09 period was already used by the first pass to compare about 12 variants, and C1 reuses the winner's inputs.

**3. What carries the model (ablations, seed medians, fold 1 / fold 2).** Drop text: top500 9 / 8, AUC 0.836 / 0.788. Drop exploit/EPSS signals: top500 11 / 4. Drop assigner history: AUC 0.861 / 0.867 (assigner history is NOT shown to help). Unmasked text: AUC 0.869 / 0.865 (masking costs nothing measurable). Masked text alone: solo AUC 0.823.

**4. 2026 shift** (2025 test pool vs 2026 scoreboard). GitHub advisories 5.6% -> 15.0%; VulnCheck 1.1% -> 9.3%; no product row 35.0% -> 49.6% (Aug/Sep 2026: 66.5% / 68.0%); assigner with no prior KEV row 36.2% -> 23.8% (2026 is an upper bound). Full: results/drift_summary.json.

**5. Final 2026 ranking** (results/top500.csv, verified submission-valid). C1 refit on 75,148 rows / 117 positives, mean of 5 seed sets, at most 50 top-500 slots per assigner (cap is neutral in the backtest, not an improvement). Top 500: 71.2% have a public exploit flag, 4.8% have EPSS > 0.1, 15.8% come from assigners with no prior KEV row. No 2026 accuracy claim exists or may be made.

**Not yet verified (do not quote):** reverse-time check (results/reverse_time.json, not time-safe), Granite comparison (pending embeddings), IBM input summary.
## SUPERSEDED: first-pass results table (old run, 7 of 12 rows differ at printed precision; do not quote)
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

HGB = scikit-learn HistGradientBoosting (depth 3, up to 150 iterations with default early stopping, lr .05, min leaf 40, L2 5), mean of 3 seeds. Text score = out-of-fold TF-IDF (1-2 grams, min_df 8, 30k features) logistic regression.
Caveats: only 52 positives (one hit is about 2%); several variants were compared on the same test set (selection optimism); the 2026 pool is about twice as large, so top 500 there is a stricter cut (about top 250 here).
Takeaway: the gain is clear in ranking quality (AUC, median rank), small and noisy in top-500 hits.

## Leakage: solo AUC on the 2025 test pool
analyzed status .675, n_affected_cpes .767, n_references .643, cvss3 score .732, EPSS .707, any exploit flag .701, assigner KEV-rate .746, cvss3-blank .481 (no signal).

## Signals and text
- Assigner (issuer) KEV counts in known_exploited.csv, among CVEs published 2021+ that we could map (813 of 1,484 KEV rows): secure@microsoft.com 159, cve@mitre.org 131, product-security@apple.com 65, chrome-cve-admin@google.com 53, psirt@cisco.com 24, security@vmware.com 22, security-advisories@github.com 22, security@apache.org 18, support@hackerone.com 17, psirt@fortinet.com 16, psirt@adobe.com 15, mobile.security@samsung.com 13.
- Top positive words in the text model include: "remote unauthenticated", "unauthenticated attacker", "windows kernel", "kernel elevation", "sharepoint", "outlook", "microsoft outlook", "error reporting", "net framework", "webmail". The text model partly re-learns vendor identity.
- Of the 52 test positives, 22 had any public exploit flag at snapshot and only 4 had EPSS above 0.1 (first backtest pass, 2025 Jan-Sep).
- KEV additions per year in the file: 2021 311 (from Nov), 2022 555, 2023 187, 2024 186, 2025 245.
- CAVEAT (correction): "all 52 test positives come from assigners with a prior KEV" and "25% of the 2026 pool is from assigners with no KEV history" were computed against the WHOLE KEV file, not time-safely. Treat both as unverified until recomputed with only KEV additions before each snapshot. UPDATE: recomputed time-safely by the auditor, 9 of 52 test positives come from assigners with no prior KEV row (audit/2026-11-07-harness.md; not yet in the claims ledger). The 2026 pool share is still unchecked.

## 2026 distribution shift
- Published CVEs per month: about 3,600-4,300 through 2025; 2026: Jan 4,302, Mar 6,234, Jun 7,942, Jul 9,770, Aug 12,256, Sep 14,928.
- Scoreboard rows by snapshot month: Jan 4,295; Feb 4,603; Mar 6,227; Apr 5,801; May 6,922; Jul (incl. June) 17,678; Aug 12,242; Sep 14,902.
- Assigner share 2026 vs 2025 test pool: GitHub advisories 15.0% vs 5.6%; VulnCheck 9.3% vs 1.1%; Oracle 4.2% vs 0.7%; Chrome admin 4.0% vs 0.3%; Microsoft 4.0% vs 2.6%; Patchstack 5.6% vs 15.8%; VulDB 7.4% vs 13.4%; MITRE 4.6% vs 10.7%.
- CVEs with zero affected-product rows: about 28-43% per month in 2025 (50% in Dec 2025), 66-68% in Aug-Sep 2026. Blank CVSS3: about 1-8% per month Jan-Oct 2025 (16% in Dec 2025), 14-16% in Aug-Sep 2026.
- Any public exploit flag: 2.26% in the 2026 scoreboard (1,645 CVEs) vs 2.15% in 2025 test. EPSS blank: 2% vs 10%. EPSS above 0.1: 66 CVEs in the 2026 scoreboard.

## Changelog
- 2026-11-07 (feat/model-ranking): added "Verified findings, Phase 3 to final" generated from verified claims (leak, honest backtest, ablations, 2026 shift, final ranking).
- 2026-11-07 (feat/model-ranking): added the VERIFIED results table generated from results/claims_model.json; old table marked SUPERSEDED; fixed "150 iterations"; added the time-safe assigner caveat result.
- 2026-11-07: created.
- 2026-11-07: corrected 2025 missing-data ranges after re-checking the monthly table.
