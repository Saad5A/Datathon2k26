# Audit: remaining UNCHECKED model claims (feat/model-ranking @ 2e2e59b), 2026-11-07

Auditor: fresh-context auditor subagent. Scope: the 437 unverified claims in `results/claims_model.json` at HEAD:
the 96 first-pass structured/leaky rows (`primary.hgb_signals_struct`, `primary.hgb_signals_struct_assigner`,
`primary.hgb_all_text`, `primary.leaky_ncpe`), the 300 Phase 3 ablation claims for C1, the 20 C2/C3 secondary
metrics, the 13 tie-order first-pass claims and the 8 held paired median-of-bounds claims.
Environment: `.venv` Python 3.12, scikit-learn 1.9.1, same machine as the producer. Nothing installed; raw data read only.

**Verdict: every re-derived number matches the ledger (467 of 467 comparisons, |diff| <= 1e-6 or exact for counts). 412 claims are
now verified. 25 stay unverified: 17 tie-order `*_first_pass_order` claims and the 8 median-of-bounds paired claims
(text problem from the previous audit). The arithmetic is right, but several conclusions need careful wording (see section 4).**

## Method (independent code path, no `src/` import)
| Script | What it does |
|---|---|
| `audit/scratch/u_run.py` | Starts from my own pool `p3_pool.parquet` (built from raw CSVs in the earlier audits). It reads the CVSS vector fields, `cwe_ids` and `n_affected_cpes` from raw `vulnerabilities.csv` by cve_id. **First-pass structured features**: cvss3 blank = -1; each vector field coded by sorted category with blank = -1 (numpy searchsorted); first CWE = `cwe_ids` up to the first `;`; top-40 by `collections.Counter` over the whole pool (count at rank 40/41 = 298/291, so the set is not tie-sensitive). Unmasked TF-IDF text, 5-fold OOF (seed 0), HGB seeds 0,1,2 with early stopping `auto`, mean of the predictions. **Phase 3**: both folds, time-safe train labels recomputed with numpy datetime64, masked text (own regex) or unmasked, HGB `early_stopping=False` (True for the ablation), 5 seed sets. `plus_structured` is my own one-hot (train vocabulary, NaN = "blank"), plus cvss3 blank = 0 and a missing indicator, plus the top-40 train CWE. C2 and C3 are refit as in `p3_rederive.py`. |
| `audit/scratch/u_check.py` | My numpy metrics (`mymetrics.py`): Mann-Whitney AUC, step AP, lexsort cve_id ranks, tie-aware top-k. Bootstrap uses `default_rng(0)` with 2,000 row resamples, redrawing if a resample has no positive. Sanity checks: my C1 vectors equal my Phase-3 audit files (`p3_C1_*.npy`, max diff < 1e-12), and my first-pass best model equals the harness audit's `best_scores.npy` (diff 0). |
| `audit/scratch/u_extra.py` | Tie ranges for the first-pass-order claims. Paired bootstrap of what `n_affected_cpes` adds. Seed ranges for every ablation. |
| `audit/scratch/u_mark.py` | Writes only `status`/`verified_by` and asserts that no other field changed. `git diff` shows exactly 412 x 2 changed lines, all of them `status`/`verified_by`. |

Outputs are saved next to the scripts: `u_check_out.txt` (one line per claim, mine vs claimed), `u_check_result.json`, `u_extra_result.json`.

## 1. First-pass structured and leaky rows (primary setup: train 2024, labels to 2025-12-31, test 2025-01..09, 52 positives)

| Model | AUC | AP | top500 by id (tie-aware best/worst) | top250 | work50 | Result |
|---|---|---|---|---|---|---|
| hgb_signals_struct | .8030 | .0628 | 19 (19/19, tied group 64) | 14 | 3,521 | PASS (22 of 24) |
| hgb_signals_struct_assigner | .8786 | .1031 | 14 (14/14, tied group 5) | 13 | 1,636 | PASS (23 of 24) |
| hgb_all_text | .8834 | .1130 | 21 | 14 | 1,016 | PASS (23 of 24) |
| leaky_ncpe | .9133 | .1312 | 26 | 21 | 352 | PASS (24 of 24) |

- All 12 bootstrap bounds per model match mine.
- Not verified because they depend on tie order:
  - `hgb_signals_struct.top1000_first_pass_order` (claimed 20; possible 19-20)
  - `hgb_signals_struct.median_rank_first_pass_order` (claimed 3,551; possible about 3,380-3,818)
  - `hgb_signals_struct_assigner.median_rank_first_pass_order` (1,635; possible 1,635-1,637)
  - `hgb_all_text.median_rank_first_pass_order` (1,086; possible 1,086-1,086.5)
- `leaky_ncpe.median_rank_first_pass_order` = 430 has no ties among the positives. Verified.
- **Leakage and reasonableness:** leaky_ncpe AUC .913 is below the .93 alarm. It is a deliberate comparison row: `n_affected_cpes` is an excluded field and appears in no other model (checked `candidates.py` and `final.py`).
- The other three structured rows also contain **cvss3 with blank = -1, which is the excluded blank-score pattern** (`pool.LEAKY_COLUMNS`). Their CWE top-40 vocabulary is chosen over the whole pool, test rows included (no labels are involved). Treat all four rows as comparison rows, never as adoptable models.

**What the leak would buy (paired bootstrap, same 2,000 resamples, seeds 0-2 mean; my computation, not in the ledger):**
- leaky_ncpe minus hgb_all_text (the same model without ncpe): AUC +.030 [95% CI +.008, +.055], expected top-500 +5 [+1, +10]. That is a measurable gain, about 10% of the positives.
- leaky_ncpe minus the honest best model (signals + assigner + text, AUC .888, top-500 25): AUC +.025 [-.009, +.061], top-500 +1 [-2, +5]. **Not distinguishable.**
- Most of the ncpe gain only repairs the damage the structured block does. Adding CVSS/CWE codes to the honest model lowers top-500 from 25 to 21.
- Caveats: one run, in the primary setup that has overlapping train labels (the harness audit calls this setup optimistic). The CIs are row-bootstrap only; they ignore seed noise and the fact that the variant was picked on this test set. **Supported wording:** "Adding the post-hoc n_affected_cpes field would raise test AUC from .883 to .913 and top-500 from 21 to 26 in the first-pass setup. Against our honest model (.888, 25) the difference is within noise."

## 2. Phase 3 C1 ablations (both folds, seed sets 0-4; 300 claims, all PASS)

Seed median [range over 5 seed sets]. C1 for reference. Fold 1 has 52 test positives, fold 2 has 32.

| Variant | fold 1 AUC | fold 1 top500 | fold 2 AUC | fold 2 top500 | fold 1 / fold 2 AP |
|---|---|---|---|---|---|
| C1 (ref) | .860 [.851-.885] | 22 [15-22] | .880 [.854-.891] | 11 [11-12] | .076 / .064 |
| drop_signals | .840 [.837-.852] | 11 [10-12] | .799 [.787-.853] | 4 [3-6] | .011 / .009 |
| drop_assigner | .861 [.848-.867] | 16 [15-18] | .867 [.859-.894] | 12 [11-13] | .101 / .109 |
| drop_text | .836 (no seed spread) | 9 | .788 | 8 | .050 / .043 |
| unmasked_text | .869 [.850-.877] | 21 [20-22] | .865 [.853-.884] | 11 [10-12] | .085 / .068 |
| plus_structured (excluded field) | .890 [.882-.895] | 20 [19-22] | .880 [.854-.888] | 10 [9-12] | .058 / .089 |
| early_stopping_on | .883 [.861-.889] | 18 [15-22] | .861 [.840-.894] | 11 [6-11] | .051 / .045 |

- Every median, min/max, top-250, AP, median rank, work50 and seed-0 bootstrap bound matches.
- drop_text has zero seed spread, as expected: with no text score and early stopping off, HGB ignores `random_state`.
- Feature lists in `model_candidates.json` match my construction. No excluded field appears except in plus_structured, which is labelled.

**Which conclusions the ablations support** (post-selection, same test sets, 32-52 positives, permutation-null SD about .1):
- **Text and signals carry the signal.**
  - Dropping the text score costs AUC in both folds (-.024 / -.092) and top-500 (22 -> 9, 11 -> 8). These drops lie outside C1's seed range in both folds.
  - Dropping the exploit/EPSS signals costs AUC (-.020 / -.080) and top-500 (22 -> 11, 11 -> 4), again outside the seed ranges.
  - Supported: "removing the text score or the exploit signals clearly hurts".
- **The assigner group is not shown to help.**
  - Without it, AUC is the same in fold 1 (.861 vs .860) and .013 lower in fold 2. The seed ranges overlap fully in both folds.
  - AP is higher without it in both folds (.101 vs .076; .109 vs .064).
  - Top-500 is lower without it in fold 1 (16 vs 22, ranges 15-18 vs 15-22) and higher in fold 2 (12 vs 11).
  - Do NOT claim the assigner features improve the model.
- **Masking the exploitation wording costs nothing measurable:** unmasked is +.009 in fold 1 and -.014 in fold 2, within the seed ranges.
- **plus_structured** adds +.030 AUC in fold 1 and nothing in fold 2. It uses an excluded blank-score field and must never be adopted or pitched as "what we left on the table" without that label.
- **Early stopping on** gives +.022 in fold 1 and -.019 in fold 2, with fold-2 top-500 dropping to 6 in one seed. This is noise. It does not argue for changing the pre-registered setting.

## 3. C2 / C3 secondary metrics (20 claims, all PASS)

| | fold 1 C2 | fold 1 C3 | fold 2 C2 | fold 2 C3 |
|---|---|---|---|---|
| top500 best / worst (median) | 18 / 18 | 19 / 19 | 12 / 12 | 13 / 13 |
| top250 by id (median) | 17 | 13 | 11 | 10 |
| AP (median) | .0460 | .0622 | .0820 | .0809 |
| median rank by id (median) | 1,722 | 861 | 1,183.5 | 664.5 |

The exact values for all 20 claims are in `u_check_out.txt`. These numbers back the earlier observation that C3 had more top-500 hits and less work-to-50% than C1 in both folds (C3 top-500 19 / 13 vs C1 22 / 11; work50 831 / 656 vs 1,226 / 1,240). That is a mixed picture, not a C1 win. It does not change the pre-registered AUC selection.

## 4. Still unverified (25)
- **17 `*_first_pass_order` claims.** Their values depend on pandas' unstable tie order (harness policy). 13 are from the harness audit. 4 are new (section 1). Publish the `_cve_id` or `_expected` values instead.
- **8 `p3.fold{1,2}.paired.*.ci95_{lo,hi}` claims.** The values are exact (previous audit), but the text still presents a median of CI bounds as a 95% CI. They need re-texting first (fix 1 of `2026-11-07-phase3-fixes-cap.md`).

## Required fixes
1. Label all four first-pass structured rows as using excluded fields: blank cvss3 = -1 in all four, plus n_affected_cpes in leaky_ncpe. Today only leaky_ncpe says "LEAKY".
2. Any "what the leak would buy" sentence must compare with the honest model (.888 / 25, difference within noise) as well as with hgb_all_text (+.030 AUC, +5 hits). It must name the primary, label-overlap setup and give no 2026 implication.
3. Ablation write-up: say text and signals matter; say the assigner group shows no measurable benefit (AP is better without it); say masking costs nothing measurable; never present plus_structured or early_stopping_on as improvements.
4. Re-text the 8 paired median-of-bounds claims, or drop them (carried over).
