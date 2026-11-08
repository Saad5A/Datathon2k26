# Before the Breach: model write-up

Tagline: [TAGLINE: not decided]

## Problem and what we predict
We rank the 72,670 CVEs on the 2026 scoreboard by how likely each is to be added to CISA's Known Exploited Vulnerabilities list (KEV), using only what was known at the end of each CVE's snapshot month. The score is a ranking, not a probability. KEV is a proxy: it lists confirmed attacks only.

## Data and what we used
**Used:** EPSS and the four public-exploit flags as of the snapshot month. The assigner (the organisation issuing the CVE) plus its KEV history from KEV rows dated *before* that month. The description, with exploitation wording ("actively exploited", "CISA", "KEV") masked out.
**Excluded:** `nvd_status`, `n_affected_cpes`, `n_references`, blank-score patterns, all of `references.csv` and `affected_products.csv`, and the CVSS, CWE and attack-vector fields.

## How we tested
We trained on older CVEs and ranked later ones, using only KEV labels known at the end of training. Fold 1 tests on 2025-01..09 (52 exploited CVEs) and fold 2 on 2025-04..09 (32). The candidates and the selection rule were pre-registered in LOG.md. An independent auditor re-derived every number with its own code.

## What we found
1. **A hidden leak.** All 52 exploited 2025 test CVEs had NIST status "Analyzed", a product list, and a filled CVSS3 score and CWE. Across all test CVEs, 35% had no product list (share of non-exploited CVEs that were Analyzed: [NEEDS VERIFIED NUMBER]). The product count alone ranks better than EPSS (AUC 0.767 vs 0.707).
2. **An honest backtest.** Our first-pass "win" (25 vs 18-19 in the top 500) came from training labels that overlapped the test period, plus seed luck (21-25 across seeds). With time-safe labels, the model roughly ties "exploit code, then EPSS" in fold 1 (22 vs 18; seeds 15-22) and loses in fold 2 (11 vs 15). Its AUC is higher in every fold and seed (0.860 vs 0.768; 0.880 vs 0.809), but for seed set 0 the paired interval on that gain includes zero. The CVSS3 top-500 count depends on tie order (5 to 17).
3. **2026 is shifted.** There are about twice as many rows as in the same 2025 months (72,670 vs 35,280). GitHub advisories rise from 5.6% to 15.0% of rows and VulnCheck from 1.1% to 9.3%. In August-September, 66-68% of CVEs lack a product list. Assigners with no prior KEV make up 36.2% of 2025 rows and 23.8% of 2026 rows (an upper bound).

## Final ranking
Model C1, chosen by the pre-registered rule: boosted trees on signals, assigner history and the masked text score. It is refit on 75,148 rows (117 exploited) and averaged over five seed sets. Each assigner is capped at 50 of the top 500, which was neutral in the backtest, not an improvement. Each CVE lists up to three "reasons": the signals that moved its score most.

## IBM technology
IBM Granite embeddings (via watsonx.ai) are prepared, and a teammate is running them now. There are no results yet.

## Limits
There are 52 test positives, so one hit is about 2%. We have no 2026 labels and make no 2026 accuracy claim. Descriptions are today's text, and the mask covers only known wording.
