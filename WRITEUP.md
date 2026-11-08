# [TAGLINE]

## Problem
We rank the 72,670 software flaws (CVEs) on the 2026 scoreboard by how likely each is to be added to CISA's Known Exploited Vulnerabilities list (KEV), using only what was known by the end of each one's snapshot month, apart from today's description and assigner fields. It is a ranking, not a chance of attack. KEV is a proxy: confirmed attacks only.

## Biggest finding: a hidden leak
In our 2025 backtest, all 52 CVEs later added to KEV had NIST status "Analyzed" and a product list. Among the others, only 50.1% were "Analyzed" and 64.9% had a product list. Per the organisers' README, NIST reviews attacked CVEs first, so these fields partly record attacks already noticed. The product count alone scores a higher AUC than EPSS, a public exploitation score (0.767 vs 0.707; intervals overlap). AUC: how often a random exploited CVE ranks above a random non-exploited one.

Why it matters: a model using them looks strong in backtests but partly reads NIST's reaction to attacks, which new CVEs lack. We excluded them.

## Columns
**Used:** `epss`, `exploitdb`, `metasploit`, `nuclei`, `poc_github` at the snapshot month; `assigner`, `published` and `description` (exploitation wording masked) from `vulnerabilities.csv`; `date_added` from `known_exploited.csv`, only rows before the snapshot month; `in_kev` only to drop CVEs already listed.

**Excluded:** `nvd_status`, `n_affected_cpes`, `n_references`, `last_modified`, `cwe_ids`, all `cvss2_*`, `cvss3_*`, `cvss4_*` and `attack_vector` through `availability_impact` columns (so no blank-score patterns), and all of `references.csv`, `affected_products.csv` and `weakness_types.csv`.

## Approach
Boosted decision trees on exploit signals, assigner KEV history and two text scores (masked-description words; IBM Granite), trained on older CVEs using only KEV labels then known. Folds 1 and 2 test 2025-01..09 and 2025-04..09. Rules were fixed in `LOG.md` before results; an independent auditor re-derived every number, apart from two comparison-only checks.

## Results and limits
Our first pass showed 25 vs 18-19 top-500 hits over "exploit code first, then EPSS", inflated by training labels overlapping the test period and by seed luck (21-25 across seeds). With time-safe labels, our base model roughly ties that rule in fold 1 (22 vs 18; seeds 15-22) and trails in fold 2 (11 vs 15). Its AUC is higher in every fold and seed (0.860 vs 0.768; 0.880 vs 0.809), though for seed set 0 the paired interval on the gain includes zero: borderline. No robust top-500 advantage.

2026 is shifted: about twice the rows of 2025's same months (72,670 vs 35,280); GitHub advisories go 5.6% to 15.0%, VulnCheck from 1.1% to 9.3%; in August-September 66-68% lack a product list.

An automated search over many variants found none passing our pre-registered gate; the submitted model stayed.

Limits: 52 test positives, so one hit is about 2%. No 2026 labels, so no 2026 accuracy claim. The description mask covers only known wording. Our first pass compared about a dozen variants on 2025, so it is not fully held out.

## IBM technology
IBM's Granite embedding model (ID in `docs/ibm.md`) embedded every masked description locally; 1,966 also went through IBM watsonx.ai, with matching vectors where both ran (audited). A pre-registered tie-break favouring IBM technology adopted it (mean AUC within 0.01 of the base model), with no measurable gain: mean AUC 0.871 vs 0.870; top-500 hits 20 vs 22 (fold 1), 11 vs 11 (fold 2). A Granite instruct model also summarised the top tier (AI-generated, unaudited, some template fallbacks).

## Impact
A ranked 2026 queue in a dashboard: tier P0 (top 100) and P1 (next 400), each CVE with up to three reasons, at most 50 per assigner. Plus a warning: backtests leaning on NIST review fields may not carry over.
