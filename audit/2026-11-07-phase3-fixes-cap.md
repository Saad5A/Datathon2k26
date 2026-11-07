# Audit: Phase 3 fixes, per-assigner cap, two new leakage rows (2026-11-07)

Auditor: fresh-context auditor subagent. Scope: HEAD of feat/model-ranking (0da5fbc plus later out-of-scope final.py / Phase 7 files).
I did not import producer code for any number below. One exception is a diagnostic run of the producer's feature loaders, without any model fitting (`audit/scratch/f_2026_diag.py`), used to explain a mismatch that turned out to be on my side.
I used my own C1 score files from the Phase 3 audit (`audit/scratch/p3_C1_fold{1,2}_s{0..4}.npy`, my own pipeline), my own pool (`my_pool2.parquet`) and my own metrics (`mymetrics.py`).
Scripts: `audit/scratch/f_paired.py`, `f_cap.py`, `f_capcheck.py`, `f_capmean.py`, `f_2026.py`, `f_leak.py`. Their outputs are the `*_out.txt` / `*_result.json` files next to them.

## 1. Required fixes from audit/2026-11-07-phase3.md

| Fix | Result |
|---|---|
| 1. Paired bootstrap and unseen-assigner claims: seed median, with seed 0 labelled | **PASS, with one text fix for 8 claims.** The 22 seed-median claims and 22 new `.seed0` claims exist. All 44 values match mine exactly (`f_paired_out.txt`, 44/44 within 1e-6). |
| 2. Clean-tree meta | **PASS.** `model_candidates.meta.json` and `assigner_cap.meta.json` both have `git_dirty: false` at commit 2d63b58. Every recorded code sha256 equals the current working-tree file. |
| 3. D1 documented | **PASS.** It is in `src/model/FEATURES.md` and in `results/model_candidates.json` `deviations.D1`. Write-up: UNCHECKED (out of scope). |
| 4. plus_structured never adoptable | **PASS.** The claim text, `excluded_field_warning` in the results, and FEATURES.md all say so. |
| 5. Write-up sentences | UNCHECKED (no write-up in scope). |
| 6. Ablations | Still UNCHECKED and still unverified. Do not publish them. |

Re-derived seed-median paired differences (C1 minus exploit-then-EPSS, 2,000 paired resamples, rng 0, same resamples for all seeds):

| | fold 1 | fold 2 |
|---|---|---|
| AUC diff, median of 5 seeds (per seed) | +0.0921 (+.084, +.117, +.104, +.092, +.082) | +0.0708 (+.082, +.054, +.071, +.045, +.071) |
| top-500 expected diff, median (per seed) | +3.64 (-0.36, +3.64, +3.64, +3.64, -3.36) | -3.60 (-3.6, -3.6, -3.6, -2.6, -3.6) |
| seed-0 AUC diff [95% CI] | +0.0839 [-0.0150, +0.1814] | +0.0823 [-0.0271, +0.1997] |
| seed-0 top-500 diff [95% CI] | -0.36 [-8.09, +6.0] | -3.6 [-8.83, +1.0] |
| per-seed AUC CI lower bound | -.015, +.032, +.020, -.003, -.007 | all < 0 (-.027 to -.054) |
| resamples with top-500 diff < 0 | 12-78% by seed | 87-95% by seed |

Fold 1: in 2 of 5 seed sets the paired AUC CI excludes 0. "The CI includes zero in both folds" is therefore only true for seed 0 and for the median-of-bounds. In fold 1, the AUC gain is borderline and depends on the seed.

**Text problem (FAIL, 8 claims):** `p3.fold{1,2}.paired.{auc,top500_expected}.ci95_{lo,hi}` (no `.seed0`) hold the element-wise median of the five per-seed CI bounds. That is not a 95% interval of anything. The current text, "paired bootstrap 95% CI lower bound, selected (median over seed sets 0-4) ...", reads like a CI on a seed-median model. Example: fold 2's "[-9.0, +0.017]" must not be quoted as a 95% CI.

## 2. Per-assigner cap (`src/model/cap.py`, `results/assigner_cap.json`)

- **Rule followed literally: PASS.** The rule allows k in {none, 100, 50}. The re-rank walks down the scores (ties by cve_id) and skips a CVE once its assigner has k slots. The statistic is the seed-median expected top-500 per fold, then the mean over the folds. Any k within 1 hit of the best counts as a tie, and the strictest such cap wins. My own Python walk (`f_cap.py`, not the producer's groupby/cumcount) gives these results:

| k | fold 1 median [seed range] | fold 2 median [range] | mean | largest share f1 / f2 |
|---|---|---|---|---|
| none | 22 [15-22] | 11 [11-12] | 16.5 | .24 / .254 |
| 100 | 20 [17-22] | 11 [11-12] | 15.5 | .20 / .20 |
| 50 | 20 [19-21] | 12 [11-13] | 16.0 | .10 / .10 |

  k=50 is within 1 hit of 16.5, and it is the strictest such cap, so the rule picks **k=50**. All 37 `p5.cap.*` values match mine. No ties straddle rank 500 in any seed, so expected = by-id. The rule shows the cap is roughly neutral. It does **not** show that the cap helps: fold 1 drops by 2 hits, fold 2 gains 1, and with 32-52 positives one hit is 2-3%.
- **Caveat (informational):** the final 2026 score is pre-registered as the seed-**mean** score. The cap was evaluated on per-seed rankings. On my seed-mean scores (`f_capmean.py`): fold 1 none/100/50 = 22/22/21 and fold 2 = 11/11/12. k=50 is still within 1 hit, so the choice stands.
- **2026 preview time-safety: PASS.**
  - Signals come from `scoreboard_2026.csv` at `snapshot_month`.
  - Assigner history counts KEV rows dated strictly before the first day of the snapshot month (the latest KEV date is 2025-12-29). Published counts are taken before that day too, from 2021+ CVEs only, the same definition as training.
  - The description is masked.
  - Training labels end on 2025-12-31.
  - No scoreboard CVE is already on KEV.
  - No 2026 accuracy is claimed.
- **2026 shares re-derived: PASS (all 5 seed sets, not only seed 0).** My own refit on my 75,148-row / 117-positive pool reproduces the claims exactly:
  - Largest share, uncapped: .130/.170/.190/.134/.158 (median .158). The largest assigner is disclosure@vulncheck.com in every seed.
  - Seed-0 top 5: vulncheck .13, oracle .118, apache .114, mitre .07, adobe .056.
  - k=50: .10 in every seed.
  - k=100 equals uncapped because it never binds (19% of 500 is 95 rows, below 100).
- **Sensitivity (disclose):** the 2026 shares depend on the 2021+ history window. My first run counted all published CVEs and KEV rows from every year. With that window, the seed-0 largest share is .18 rather than .13, the median is .18, and Oracle drops out of the top 5. The 2021+ window is the correct one, because it matches the training features. But "shares" are fragile. The number of distinct assigners also swings by seed (77-101), which supports the pre-registered seed averaging.

## 3. New leakage rows (`results/leakage_table.csv`)

| Row | Claimed | Mine (`f_leak.py`) | Result |
|---|---|---|---|
| `txt_masked_tfidf` (fold-1 train fit, labels capped 2024-12-31, 2025 test rows; seed-independent) | 0.8225 | 0.822498 | **PASS** |
| `asg_rate_24m` (D1 definition) | 0.7327 | 0.732668 | **PASS** (all-KEV variant: 0.7368) |

The masked text score alone (.82) is close to C1 (.86-.88). Most of C1's signal is today's description text. The table already states the residual risk (descriptions edited after attacks), and this data cannot test it. Keep that caveat next to any C1 result.

## 4. Re-texted p3 claims

- 194 p3 claims were verified in the previous audit and reset to unverified only because their text changed. All 194 values are unchanged (|diff| = 0).
- The new texts fall into 11 templates, and each is accurate:
  - "median / lowest / highest of seed sets 0-4" for candidates.
  - "(deterministic baseline, no seed)" and "bootstrap CI ... (deterministic baseline)" for cvss3 / epss / exploit-then-EPSS. These are fixed rules, so the label is correct.
  - "selected model (seed set 0), 20 train-label shuffles" for the permutation test.
  - "unseen-assigner rows/positives (median over seed sets 0-4)". These do not depend on the seed, so they are trivially correct.
- **PASS, re-verified.** The 24 removed baseline min/max keys are gone and need no action.

## Claim status set by this audit
- **Verified:**
  - 194 re-texted p3 claims.
  - 36 of the 44 paired/unseen claims: the 4 seed-median diffs, all 22 `.seed0` claims, and the 10 seed-median unseen-assigner claims (5 per fold).
  - All 37 `p5.cap.*` claims.
  - `leakage.solo_auc.txt_masked_tfidf` and `leakage.solo_auc.asg_rate_24m`.
- **Held (values exact, text misleading):** the 8 `p3.*.paired.*.ci95_{lo,hi}` median-of-bounds claims.
- **UNCHECKED:** ablations, write-up sentences, and n_assigners counts in the cap results (not claimed).

## Required fixes
1. Re-text the 8 median-of-bounds claims as "median over seed sets 0-4 of the per-seed paired-bootstrap 95% CI lower/upper bound (not itself a 95% interval)", or drop them and quote the `.seed0` CIs. Then request a re-audit.
2. Any sentence saying "the paired AUC CI includes zero in both folds" must say "for seed set 0". In fold 1, 2 of 5 seed sets exclude zero, so call the gain borderline.
3. The cap write-up must say the cap was chosen as neutral within noise (fold 1 -2 hits, fold 2 +1 hit). It must not say the cap improves hits.
4. Any write-up of 2026 assigner shares must note that they depend on the 2021+ history window and on the seed set, and must use the seed-mean final file, not this preview.
