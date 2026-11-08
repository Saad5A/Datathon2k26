# Audit: reverse-time check (src/model/reverse_time.py -> results/reverse_time.json, results/claims_model_reverse.json)

Auditor: fresh auditor subagent, 2026-11-07. Spec: LOG.md "PRE-REGISTRATION, reverse-time check" (19:30) and the RESULT line (19:55).

**Verdict:** the numbers reproduce. 75 of 80 `rev.*` claims PASS and are marked verified. 5 FAIL: 4 have truncated values and 1 has an ambiguous definition. The C1 fit, the seed range, every baseline and every bootstrap bound match exactly, and the pipeline passes the leakage controls. The producer's **interpretation** in the LOG RESULT line does **not** hold as written. Do not publish "the expected optimism did not show up" or "AUC well above every baseline" (see section 4).

## 1. How I checked (my own code path, no import of src/model)

| Script (audit/scratch/) | What it does |
|---|---|
| `r_run.py` | Recomputes the labels from raw `known_exploited.csv` with string date comparisons and asserts they equal the auditor pool's `y`. Selects 2025-01..09 rows as train and 2024-01..12 rows as test. Refits C1 with code copied from the earlier auditor's `p3_rederive.py`: masked TF-IDF, LR C=2 balanced, 5-fold OOF with seed s, and HGB depth 3, lr .05, 150 iterations, min leaf 40, L2 5, no early stopping, random_state s, for s = 0..4. Recomputes the baselines from the auditor pool (`p3_pool.parquet`, built from raw CSVs by a1/a2 and checked earlier against the producer cache). Metrics use `mymetrics.py`: numpy rank AUC, AP, tie-aware top-k, and a lexsort on the cve_id string for ties. Runs my own bootstrap loop (2000 resamples, seed 0, positive-free resamples redrawn) and a paired AUC bootstrap. Output: `r_result.json`, `r_scores.npz`. |
| `r_check.py` | Compares every claim to my values (tolerance 1e-6) and checks that each claim text contains "reverse-time (not time-safe)". Also computes the indicator, EPSS coverage by month, and EPSS AUC by year, and compares the forward-fold copy with the p3 claims. Output: `r_check_out.txt`, `r_check_result.json`. |
| `r_ind.py` | Recomputes the indicator under both assigner populations. Output: `r_ind_out.txt`. |
| `r_perm.py` | Label-permutation control: C1 trained on shuffled 2025 labels. Output: `r_perm_out.txt`. |

## 2. Claims: mine vs claimed

| Claim group | Mine | Claimed | Result |
|---|---|---|---|
| train rows / positives | 35,280 / 52 | 35,280 / 52 | PASS |
| test rows / positives | 39,868 / 65 | 39,868 / 65 | PASS |
| train/test cve_id overlap | 0 | 0 (JSON) | PASS |
| C1 top-500 by cve_id, seed median [min-max] | 15 [14-17] (per seed 14, 14, 16, 15, 17) | 15 [14-17] | PASS |
| C1 AUC, median [min-max] | .82218 [.80894-.83535] | same to 1e-12 | PASS |
| C1 work-to-50%, median_rank, top-250, AP, best/worst medians | 2659, 2659, 12, .08508, 15/15 | same | PASS |
| exploit_then_epss top-500 / AUC / work50 | 17 / .64440 / 10,709 | same | PASS |
| epss top-500 / AUC / work50 | 10 / .57840 / 19,569 | same | PASS |
| cvss3 top-500 by id / tie range best-worst / tied group | 0 / 29-0 / 3,961 rows | 0 / 29-0 | PASS |
| assigner_only top-500 / AUC | 7 / .79261 | same | PASS |
| All other baseline secondary metrics (top-250, AP, median rank, work50, best/worst) | equal | equal | PASS |
| CI bounds for C1 (seed set 0), epss, assigner_only (top500_cve_id, top500_expected, auc) and AUC/top500_cve_id bounds for exploit_then_epss and cvss3 | equal | equal | PASS |
| `rev.exploit_then_epss.ci95_lo.top500_expected` | 8.8787 | 8 | **FAIL** (int truncation) |
| `rev.exploit_then_epss.ci95_hi.top500_expected` | 24.1190 | 24 | **FAIL** (int truncation) |
| `rev.cvss3.ci95_lo.top500_expected` | 1.3005 | 1 | **FAIL** (int truncation) |
| `rev.cvss3.ci95_hi.top500_expected` | 2.7593 | 2 | **FAIL** (int truncation) |
| `rev.indicator.positives_own_kev_date_in_2025` | 25 | 25 | PASS |
| `rev.indicator.positives_whose_assigner_has_kev_additions_dated_2025` | 58 if KEV is limited to CVEs published 2021+; **60** with all KEV additions | 58 | **FAIL** (the text does not state the 2021+ restriction; under the plain reading the count is 60) |
| Tag "reverse-time (not time-safe)" in every claim text | 80/80 | | PASS |
| Forward fold-1 numbers copied into the JSON vs p3 claims | C1 top-500 22 [15-22], AUC .8601 [.8505-.8847], work50 1,226, rows/positives 39,868/40 and 35,280/52; baselines exploit_then_epss 18/.768, epss 8/.707, cvss3 5/.732. All equal to the p3 claims, and the C1 ones are `verified`. | | PASS (assigner_only has no forward value; listed in `missing`) |

## 3. Leakage and reasonableness

- **Row and label checks:** overlap is 0. The labels recomputed from raw KEV equal the pool labels on all 75,148 rows. The base rate is 52/35,280 = 0.15% on train and 65/39,868 = 0.16% on test. No AUC is above .93 (maximum .835).
- **Label permutation:** C1 trained on shuffled 2025 labels scores AUC .459, .581 and .471 on 2024, i.e. chance level. The pipeline itself does not leak.
- **Excluded NVD fields:** C1 uses only EPSS, the exploit flags, asg_rate/asg_kev and masked text. None of the excluded fields is used. PASS.
- **Future knowledge (by design):** all 65 test positives have their own KEV addition before 2025-09-01, so each one enters `asg_kev`/`asg_rate` for at least the September 2025 training rows. 40 were added before 2025-01-01 and enter the features of every training row.
  - The claimed indicator (58, or 60) is weak evidence of this. 59% of 2024 test **negatives** also have an assigner with a 2025 KEV addition. It mostly shows that big vendors have KEV additions every year.
  - The more direct number is "65/65 test positives' own KEV additions are in some training row's assigner history". It is not registered as a claim.

## 4. Producer's explanations (LOG RESULT line)

**"EPSS much weaker on 2024 rows (AUC .578)": numerically true, but it is not a coverage effect.**
- EPSS blank share is lower in 2024 than in 2025: 3.7% vs 9.8% of rows. 2025-01 is 44.7% blank and 2025-02 is 23.3%. Every 2024 month is at or below 10.1% (2024-05).
- Positives with a blank EPSS: 3/65 in 2024 vs 5/52 in 2025.
- Counting only non-blank rows, the EPSS AUC is still .590 on 2024 vs .753 on 2025, so the scores themselves rank 2024 rows worse.
- The exploit-flag rate is equal (2.2% of rows in both years). Positives with any flag: 21/65 (32%) in 2024 vs 22/52 (42%) in 2025.
- So the 2024 test set is harder for the signal features. That part of the explanation is fair. Any implication that it comes from missing EPSS is not.

**"2025 train labels censored (Sep rows ~3 months of window)": correct but not a valid confound.**
- Reverse training windows run from 334 days (2025-01) down to 92 days (2025-09), mean 214.
- The forward fold-1 training labels were **more** censored: they were capped at 2024-12-31, so windows run from 335 days down to 0, mean 168. Only 40 of 65 positives survived.
- Censoring therefore cannot explain why reverse is not more optimistic than forward. If anything, the reverse fit had more label time.

**"The expected optimism did NOT show up": not supported as a finding.**
- The comparison is across different test sets: different years, 65 vs 52 positives, different signal quality.
- The CIs overlap heavily. C1 AUC is .822 [.762, .875] reverse vs .860 [.789, .909] forward. Top-500 is 15 [7, 22] vs 22 [9, 25].
- Measured against the strongest baseline, the reverse run looks *more* favourable to C1. On AUC, C1 minus exploit_then_epss is +.178 (paired 95% CI [+.093, +.263]) reverse vs about +.092 forward, which is what optimism would predict. On top-500 it is the other way: −2 (15 vs 17) reverse vs +4 (22 vs 18) forward.
- Work-to-50% is much worse in reverse: 2,659 vs 1,226.
- The defensible statement is: "absolute reverse-time numbers were not higher than the forward fold; because the two test sets differ in difficulty, this does not show that there is no optimism."

**"AUC well above every baseline except on top-500": FAIL.**
- Paired bootstrap of C1 AUC minus baseline AUC (C1 seed set 0, same resamples):
  - vs exploit_then_epss: +.177 [+.093, +.263]
  - vs epss: +.243 [+.151, +.334]
  - vs cvss3: +.044 [−.022, +.107]
  - vs assigner_only: +.027 [−.034, +.094]
- C1 is clearly above the EPSS-based baselines only. It is within noise of cvss3 and assigner_only.

**General points:**
- With 65 positives, one hit is about 1.5% of positives. The seed range 14-17 alone spans about 5 percentage points.
- None of this is a 2026 claim, and no 2026 statement is made. PASS on rule 5.

## 5. Required fixes

1. In `reverse_time.py` `add()`, do not cast non-integer `top500_expected` CI bounds to int. Store them as floats, or give them a non-count unit. Then re-register the 4 FAIL claims.
2. Rename or re-text the assigner indicator so it says "assigner (CVEs published 2021+, as in the asg features) has KEV additions dated 2025". Better: register the direct measure, test positives whose own KEV addition is before 2025-09-01 (65) and before 2025-01-01 (40).
3. Rewrite the LOG RESULT interpretation and any write-up text:
   - Drop "the expected optimism did NOT show up". Use the defensible statement from section 4.
   - Drop "censored labels" as a confound: forward labels were more censored.
   - Say the EPSS weakness on 2024 is in the scores, not in coverage.
   - Replace "AUC well above every baseline" with "AUC above the EPSS-based baselines; not distinguishable from cvss3 or assigner_only (paired CIs include 0)".
4. Every published use must keep the "reverse-time (not time-safe), not an accuracy estimate" label. The claim texts already do.

## 6. Ledger actions

Marked `verified` (verified_by this report): the 75 PASS `rev.*` claims. Left `unverified`: `rev.exploit_then_epss.ci95_lo.top500_expected`, `rev.exploit_then_epss.ci95_hi.top500_expected`, `rev.cvss3.ci95_lo.top500_expected`, `rev.cvss3.ci95_hi.top500_expected`, `rev.indicator.positives_whose_assigner_has_kev_additions_dated_2025`.

UNCHECKED:
- the `results/reverse_time.meta.json` provenance;
- the CI bounds for metrics that are not registered as claims (only the registered keys were compared);
- whether other documents already quote the RESULT-line interpretation (another auditor is reviewing documents).
