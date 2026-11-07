# Audit: leakage table and 2025-vs-2026 drift summary

Auditor: fresh-context auditor subagent, 2026-11-07. Commit under audit: `cecfbc5` (branch feat/model-ranking). The files under audit (`results/leakage_table.csv`, `results/leakage_table.meta.json`, `results/drift_summary.json`, `results/drift_summary.meta.json`) are unmodified relative to that commit.
Scope: `results/claims_model_drift.json` (46 claims), plus the contract and the wording of the notes and reasons in both files.
Method: my own code only. I read `src/model/leakage.py` only for feature definitions (domain list, wording regex, AV mapping), never its computations. 2025 test pool = `audit/scratch/my_pool2.parquet` from the harness audit (`audit/2026-11-07-harness.md`): 35,280 rows, 52 positives, asserted. Every other quantity comes from the raw `.data/data/` CSVs.

| Script | What it does |
|---|---|
| `audit/scratch/ld_1_leak.py` | Builds all 16 columns from raw vulnerabilities / affected_products / references, then computes AUC with a hand-written average-rank Mann-Whitney (pure numpy, no scipy/sklearn). Reports raw and oriented AUC, plus positive/negative counts for binary columns. |
| `audit/scratch/ld_2_domains.py`, `ld_3_domlift.py` | Reference domains of the test positives, checks NEWS_DOMAINS coverage, X-Force link counts. |
| `audit/scratch/ld_4_drift.py` | Drift numbers from raw scoreboard / vulnerabilities / affected_products / KEV. Computes no-prior-KEV both with and without the 2021+ restriction. |
| `audit/scratch/ld_5_compare.py` | Compares every number in `drift_summary.json` and all 46 ledger values with mine. |
| `audit/scratch/ld_6_boot.py` | My own bootstrap (seed 7, 1000 resamples) as a sanity check on the meta CIs. |

## 1. Leakage table: solo AUCs (16 claims): all values reproduce. 16 PASS (with required fixes to the text)

| column | mine (raw) | mine (oriented) | claimed | positives with value 1 / 52 | negatives with value 1 / 35,228 |
|---|---|---|---|---|---|
| nvd_status_analysed | 0.6754 | 0.6754 | 0.6754 | **52** | 22,869 (64.9%) |
| n_affected_cpes | 0.7673 | 0.7673 | 0.7673 | mean 15.2 vs 4.9 | |
| n_references | 0.6434 | 0.6434 | 0.6434 | mean 3.94 vs 2.70 | |
| cvss3_blank | 0.4812 | 0.5188 | 0.5188 FLIPPED | **0** | 1,328 |
| cwe_blank | 0.4784 | 0.5216 | 0.5216 FLIPPED | **0** | 1,519 |
| has_affected_product | 0.6753 | 0.6753 | 0.6753 | **52** | 22,878 |
| ref_news_threat_link | 0.5951 | 0.5951 | 0.5951 | 10 | 77 |
| ref_xforce_link | 0.5 | 0.5 | 0.5 | 0 | 0 |
| ref_exploit_tag | 0.6904 | 0.6904 | 0.6904 | 31 | 7,585 |
| desc_exploitation_wording | 0.5570 | 0.5570 | 0.557 | 6 | 49 |
| epss | 0.7073 | | 0.7073 | | |
| any_public_exploit | 0.7011 | | 0.7011 | 22 | 738 |
| n_exploit_flags | 0.7021 | | 0.7021 | | |
| asg_rate | 0.7463 | | 0.7463 | | |
| cvss3_score | 0.7322 | | 0.7322 | | |
| attack_vector | 0.5752 | | 0.5752 | | |

- **Orientation.** Only cvss3_blank and cwe_blank have a raw AUC below 0.5, and both are the ones marked FLIPPED. "Lower = more exploited" is correct: no positive has a blank CVSS3 or blank CWE. That points the same way as the README's leak (attacked CVEs get NIST scores first).
- **Why some CIs are so narrow (striking leak fact).** **All 52 test positives have `nvd_status` = "Analyzed"** (none are even "Modified"), while 35% of negatives are Deferred, Modified or Undergoing Analysis. All 52 positives also have at least one affected_products row, and none has a blank CVSS3 or CWE. For a binary feature that every positive carries, AUC = 1 - 0.5 x (share of negatives carrying it). Its bootstrap spread therefore comes only from the 35k negatives, which gives [0.673, 0.678]. That interval is correct as arithmetic but badly understates the real uncertainty: it says nothing about how often a future positive would lack the value. With 52/52, the 95% lower bound on "share of positives Analyzed" is only about 94% (rule of three: 1 - 3/52). My own bootstrap (seed 7) agrees with every meta CI to within about 0.006, so the CIs as computed are fine.
- **News/threat rule.** It is applied as described: Press/Media Coverage tag OR lower-cased domain (leading `www.` removed) in the 24-domain list. Rebuilding it gives exactly 10 positive and 77 negative CVEs. **The list misses obvious exploit-research sites.** `horizon3.ai` is on 6 of the 52 positives (12 CVEs in the pool, 50% positive). Also missing: isc.sans.edu, reliaquest.com, intezer.com, blog.nviso.eu, networkworld.com, doublepulsar.com, rapid7.com, tenable.com, sophos.com. Adding horizon3.ai alone raises the AUC from 0.595 to 0.643 (15 positives). Adding a broader set raises it to 0.719 (23 positives), but I picked part of that set after looking at the positives, so treat it as an upper sketch. Only 4 positives carry the Press/Media tag. Conclusion: 0.595 is a **lower bound** on the news/threat-link leak in 2025. It is not the size of that leak.
- **X-Force.** The value is constant at 0 in the test pool. The whole references file has 37,931 rows whose domain contains "xforce", and none belongs to a CVE-2025-* or CVE-2026-* id. AUC 0.5 is correct but tells us nothing.
- Every claim value (to 4 dp) is reproduced exactly. **PASS, verified** for all 16 `leakage.solo_auc.*` claims. The asg_rate column comes from the harness auditor's pool. The harness audit already matched it against an independent per-month recomputation.

## 2. Drift summary (30 claims): 28 PASS, 2 FAIL

Every number in `drift_summary.json` matches my recomputation: 0 mismatches at tolerance 5e-7 for rates and exact for counts. That covers monthly volume (33 months), pool and scoreboard rows per month, distinct assigners, the order of both top-15 lists, the shares, all by-month and overall missing-data rates, and the no-prior-KEV shares by month.

| claim group | mine | claimed | verdict |
|---|---|---|---|
| scoreboard rows 2026-01..09 (8 groups + total 72,670) | identical; no 2026-06 group. 2026-07 = 7,921 June + 9,757 July publications; every other row has snapshot = publish month | identical | PASS |
| pool rows 2025 | 35,280 | 35,280 | PASS |
| distinct assigners | 338 / 382 (0 null assigners; every scoreboard id is in vulnerabilities.csv) | 338 / 382 | PASS |
| GitHub advisories share | 0.056236 / 0.149911 | same | PASS |
| VulnCheck share | 0.011395 / 0.093464 | same | PASS |
| no affected_products row | 0.350057 / 0.496353; 2026-08 0.664597; 2026-09 0.679976 | same | PASS |
| cvss3 blank | 0.037642 / 0.087354 | same | PASS |
| epss blank | 0.098073 / 0.019692 | same | PASS |
| any exploit flag | 0.021542 / 0.022637 | same | PASS |
| EPSS > 0.1 | 0.002438 / 0.000908 | same | PASS |
| **no-prior-KEV share** | with the producer's 2021+ restriction: 0.379110 / 0.249787. **Without it: 0.361678 / 0.237897** | 0.37911 / 0.249787 | **FAIL (wording)** |

- **No-prior-KEV mapping.** KEV row to assigner via vulnerabilities.csv: all 1,484 KEV ids map, none missing. "Prior" means the earliest KEV `date_added` is before the first day of the snapshot month, which is time-safe. The producer, however, counts only KEV rows whose CVE was published 2021 or later, and that drops 671 of the 1,484 KEV rows. The ledger text says "assigner had 0 KEV rows before the snapshot month", which is false for these assigners. Among 2026 rows, those counted as "no prior KEV" only because of the restriction include security-alert@hpe.com (243 rows), security@elastic.co (163), mlhess@drupal.org (148), secure@intel.com (142), hp-security-alert@hp.com (42) and cybersecurity@se.com (41). Effect: it inflates the share by +1.7 pp (2025) and +1.2 pp (2026). The direction of the drift does not change. The drift note does mention "CVEs published 2021+", but the ledger text does not.
- The "2026 share is an upper bound" note is correct: KEV ends 2025-12-31, so missing 2026 additions can only lower the share.

## 3. Contract (INTERFACES.md section 1)

- `leakage_table.csv` header is exactly `column,used_in_model,solo_auc,reason`: **PASS**. But `used_in_model` holds the value "ablation only" for cvss3_score and attack_vector, while the contract says yes/no: **minor FAIL**.
- The table **omits two model inputs**: `asg_kev`, and the description-text score `txt` (TF-IDF over today's description, per the harness audit's feature list). `desc_exploitation_wording` = "no" is misleading, because the model's text feature reads the same, today's, description, including any "exploited in the wild"/CISA/KEV words.
- `drift_summary.json` has monthly volume, assigner mix 2025 vs 2026, and missing-data rates: **PASS**.

## 4. Sentences

- `leakage_table.meta.json` note: "README says the leak is stronger for 2026 rows". The README says these fields "can give part of the answer away" and the data dictionary says "much of the answer" for 2026. Neither says "stronger". Reword to: "the README warns these fields leak for 2026 rows; the 2026 leak size cannot be measured (no 2026 labels)". Nothing in either file claims a 2026 leak size or a 2026 accuracy: good.
- n_references reason: "links are added after attacks". The data guide says "often". Add "often".
- ref_news_threat_link reason: must say the domain list is hand-picked and incomplete (misses horizon3.ai and others), so the AUC is a lower bound for this leak.
- nvd_status_analysed / has_affected_product / cvss3_blank / cwe_blank: the narrow CIs must not be quoted as "precise leak size". State the 52/52 (or 0/52) fact instead. It is the strongest leak finding in this table, and it holds in the 2025 backtest only.
- Drift notes: checked against README/data dictionary (14,500 Feb-2025 gap, EPSS model change March 2025, 51,046/92,205 unreviewed, June 2026 to July). Accurate. The epss_blank 2025 overall (9.8%) is dominated by Jan (44.7%) and Feb (23.3%). The note covers this, so keep it next to any quote of the number.

## Verdict per claim

- **verified (44):** all 16 `leakage.solo_auc.*`; `drift.pool_rows_2025`; 9 `drift.scoreboard_rows.*`; 2 `drift.distinct_assigners.*`; 4 `drift.assigner_share.*`; 12 missing-data claims (`drift.no_affected_product.*` x4, `drift.cvss3_blank.*` x2, `drift.epss_blank.*` x2, `drift.any_public_exploit.*` x2, `drift.epss_gt_0_1.*` x2).
- **FAIL, stay unverified (2):** `drift.no_prior_kev_share.2025_pool`, `drift.no_prior_kev_share.2026_scoreboard`. The value matches the code, but the text misstates the definition.
- UNCHECKED: whether `used_in_model` matches the Phase-3 model in the uncommitted `src/model/candidates.py` (out of scope). I compared it only with the first-pass feature list from the harness audit.

## Required fixes

1. no-prior-KEV: either change the claim text to "...0 KEV rows (CVEs published 2021+) dated before the snapshot month", or drop the restriction (values become 0.361678 / 0.237897). Then re-register and re-audit.
2. leakage_table: add rows for `asg_kev` (yes) and description text `txt` (yes, today's text). Use only yes/no in `used_in_model`, and move "ablation only" into `reason`.
3. ref_news_threat_link reason: add "hand-picked list, misses e.g. horizon3.ai (6/52 positives); AUC is a lower bound".
4. meta note: replace "README says the leak is stronger for 2026" with the wording in section 4.
5. Report the 52/52 Analyzed / 52/52 with products / 0/52 blank CVSS3 or CWE facts with the rule-of-three bound, not the near-zero-width bootstrap CI.
6. (From the harness audit, still open) mask the exploitation wording in descriptions before the 2026 text model.
