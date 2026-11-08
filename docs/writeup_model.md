# Before the Breach: model write-up

Tagline: [TAGLINE: not decided]

## Problem and what we predict
We rank the 72,670 CVEs on the 2026 scoreboard by how likely each is to be added to CISA's Known Exploited Vulnerabilities list (KEV). We use only information dated on or before the end of each CVE's snapshot month, except the description and assigner fields, which are today's values (see Limits). The score is a ranking, not a probability. KEV is a proxy: it lists confirmed attacks only.

## Data and what we used
**Used:**
- `epss`, `exploitdb`, `metasploit`, `nuclei` and `poc_github` at the snapshot month, from `exploit_signals_2024.csv`/`exploit_signals_2025.csv` (rows matched on `month`) and from `scoreboard_2026.csv` (at `snapshot_month`).
- `assigner`, `description` and `published` from `vulnerabilities.csv`. Assigner history counts CVEs published 2021+. In `description`, exploitation wording ("actively exploited", "exploited in the wild", "CISA", "KEV" and similar) is masked out.
- `date_added` from `known_exploited.csv`. For features we count only rows dated before the snapshot month; for training labels, additions up to the end of each training period.
- `in_kev`, only to drop CVEs already on KEV at their snapshot. Nothing else.

**Excluded:**
- From `vulnerabilities.csv`: `nvd_status`, `n_affected_cpes`, `n_references`, `last_modified`, `cwe_ids`, every `cvss2_*`, `cvss3_*` and `cvss4_*` column, and `attack_vector` through `availability_impact`. Blank-score patterns are excluded with them.
- All of `references.csv`, `affected_products.csv` and `weakness_types.csv`.

## How we tested
We trained on older CVEs and ranked later ones, using only KEV labels known at the end of training. Fold 1 tests on 2025-01..09 (52 later KEV-listed CVEs). Fold 2 tests on 2025-04..09 (32). The candidates and the selection rule were pre-registered in LOG.md before Phase 3 ran. Before that, though, our first pass had already compared about a dozen variants on the 2025-01..09 period, and C1 reuses the first-pass winner's inputs. That period is therefore not fully held out, and our fold-1 numbers may be slightly optimistic. An independent auditor re-derived every number with its own code, apart from two comparison-only checks.

## What we found
1. **A hidden leak.** All 52 later KEV-listed 2025 test CVEs had NIST status "Analyzed", a product list, and a filled CVSS3 score and CWE. Among the other test CVEs, only 50.1% were "Analyzed" and 64.9% had a product list. In this backtest, the product count alone scores a higher AUC than EPSS (0.767 vs 0.707; the intervals overlap).
2. **An honest backtest.** Our first-pass "win" (25 vs 18-19 in the top 500) was inflated by training labels that overlapped the test period and by seed luck (21-25 across seeds). With time-safe labels, the model roughly ties "exploit code, then EPSS" in fold 1 (22 vs 18; seeds 15-22) and loses in fold 2 (11 vs 15). Its AUC is higher in every fold and seed (0.860 vs 0.768; 0.880 vs 0.809), but for seed set 0 the paired interval on that gain includes zero. The CVSS3 top-500 count depends on tie order (5 to 17).
3. **2026 is shifted.** There are about twice as many rows as in the same 2025 months (72,670 vs 35,280). GitHub advisories rise from 5.6% to 15.0% of rows and VulnCheck from 1.1% to 9.3%. In August-September, 66-68% of CVEs lack a product list. Assigners with no prior KEV make up 36.2% of 2025 rows and 23.8% of 2026 rows (an upper bound).

## Final ranking
Model C1, chosen by the pre-registered rule: boosted trees on signals, assigner history and the masked text score. It is refit on 75,148 rows (117 later KEV-listed) and averaged over five seed sets. Each assigner is capped at 50 of the top 500; the cap was neutral in the backtest, not an improvement. Each CVE lists up to three "reasons": the signals that moved its score most.

## IBM technology
IBM Granite embeddings of the masked descriptions run via watsonx.ai and/or the same open Granite model on Colab. A teammate is running them now, and results are pending.

## Limits
- There are 52 test positives, so one hit is about 2%. We have no 2026 labels and make no 2026 accuracy claim.
- Descriptions are today's text, and the mask covers only known wording.
- EPSS is often blank in the January-February 2025 test rows.
- CVEs rejected later are absent from today's file (a survivor effect).
- Assigner history counts only KEV CVEs published 2021+.
- On test CVEs from assigners with no earlier KEV entry, the model did worse than the simple baseline in fold 1.
