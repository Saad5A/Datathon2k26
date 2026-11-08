# Repair experiment around the AutoRank champion — pre-registered protocol

Status: **pre-registered before any candidate was evaluated**.
Date written: 2026-11-07.
Owner: model-ranking subagent (bounded experiment, not the official gate).

## 1. Question

The audited baseline is C1 (`cloud/autorank/evaluate.py::C1_GENOME`). The current
blind champion is the C00 genome below. On the 2025 primary+rolling folds the
champion is ahead of C1 but fails the official five-seed adoption gate, mostly
because it needs roughly two more top-500 hits. This experiment asks a narrow,
**exploratory** question: among a fixed list of 24 small perturbations of that
champion, is there one that improves both top-243 and top-500 without losing
average precision?

This is **selection on the same 2025 folds that produced the champion**. It is
therefore biased optimistic and is **not** a valid five-seed gate. No candidate
in this experiment is "eligible"; eligibility can only be established by the
official five-seed gate run separately on the server.

## 2. Fixed data and harness

- Harness: `cloud.autorank.evaluate.evaluate_genome`.
- Baseline genome: `cloud.autorank.evaluate.C1_GENOME`.
- Folds: `("primary", "rolling")`.
- Fold seeds: `0` and `42` (the two cached local fold builds:
  `data_cache/autorank/folds/{primary,rolling}_seed{0,42}.parquet`).
- `bootstrap=0` (no bootstrap in this bounded run; confidence intervals are a
  job for the official gate).
- `postprocess.seed_average` is force-set to `1` for every genome, including
  C1, so no extra fold seeds are built and candidate differences are not
  confounded by seed averaging.
- Feature order is kept exactly as written in section 3. The harness resolves
  groups and drops anything unavailable; dropped groups are recorded in
  `results.json`.
- Parallelism: at most 4 worker processes; `OMP_NUM_THREADS=1`,
  `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
- No package installs. GAM is the sklearn `SplineTransformer` +
  `LogisticRegression` pipeline already in `cloud/autorank/models.py`.
- Read-only outside `experiments/repair_champion/`: this experiment does not
  write `results/top500.csv`, `results/scores_2026.csv`, or anything under
  `cloud/autorank/`.

## 3. Fixed candidate list (24)

Common base (C00):

```json
{
  "features": ["assigner24", "signals", "temporal"],
  "model": "gam",
  "params": {"n_knots": 4, "C": 1.0},
  "postprocess": {"cap": 75, "month_allocation": "none", "flag_quota": 400, "seed_average": 1}
}
```

Every candidate keeps `month_allocation = "none"` and `seed_average = 1`.
Unless a row changes them, `cap = 75`, `flag_quota = 400`, `model = "gam"`,
`n_knots = 4`, `C = 1.0`. "Base + X" means append feature group `X` to the
base feature list in the order written.

| ID | Features | Model | Params | cap | flag_quota |
|---|---|---|---|---|---|
| C00 | base: `assigner24, signals, temporal` | gam | `n_knots=4, C=1.0` | 75 | 400 |
| C01 | base + `text_tfidf` | gam | `n_knots=4, C=1.0` | 75 | 400 |
| C02 | base + `assigner` | gam | `n_knots=4, C=1.0` | 75 | 400 |
| C03 | base + `text_tfidf` + `assigner` | gam | `n_knots=4, C=1.0` | 75 | 400 |
| C04 | C01 features | gam | `n_knots=4, C=0.1` | 75 | 400 |
| C05 | C01 features | gam | `n_knots=4, C=0.3` | 75 | 400 |
| C06 | C01 features | gam | `n_knots=4, C=3.0` | 75 | 400 |
| C07 | C01 features | gam | `n_knots=6, C=1.0` | 75 | 400 |
| C08 | base + `assigner` + `text_tfidf` | gam | `n_knots=4, C=0.1` | 75 | 400 |
| C09 | base + `assigner` + `text_tfidf` | gam | `n_knots=4, C=0.3` | 75 | 400 |
| C10 | base + `assigner` + `text_tfidf` | gam | `n_knots=6, C=1.0` | 75 | 400 |
| C11 | base | hgb | `max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40, l2_regularization=5.0` | 75 | 400 |
| C12 | base | extra_trees | `n_estimators=200, max_depth=10, min_samples_leaf=5, max_features="sqrt"` | 75 | 400 |
| C13 | base | logistic | `C=0.3` | 75 | 400 |
| C14 | `signals, assigner, text_tfidf, assigner24` | gam | `n_knots=4, C=0.3` | 100 | 400 |
| C15 | C14 features | gam | `n_knots=4, C=0.3` | 50 | 400 |
| C16 | C14 features | gam | `n_knots=4, C=0.3` | None | 400 |
| C17 | C14 features + `temporal` | gam | `n_knots=4, C=0.3` | 100 | 400 |
| C18 | C17 features | gam | `n_knots=4, C=0.3` | 75 | 400 |
| C19 | `signals, assigner` | gam | `n_knots=4, C=0.1` | 50 | 400 |
| C20 | `signals, assigner, assigner24, text_tfidf, temporal` | gam | `n_knots=4, C=0.1` | 75 | 400 |
| C21 | C01 features | gam | `n_knots=4, C=1.0` | 50 | 400 |
| C22 | C01 features | gam | `n_knots=4, C=1.0` | 75 | None |
| C23 | C02 features | gam | `n_knots=4, C=0.1` | 75 | 400 |
| C24 | C02 features | gam | `n_knots=4, C=0.3` | 75 | 400 |

The exact feature lists are:

- base / C00, C11, C12, C13: `["assigner24", "signals", "temporal"]`
- C01, C04-C07, C21, C22: `["assigner24", "signals", "temporal", "text_tfidf"]`
- C02, C23, C24: `["assigner24", "signals", "temporal", "assigner"]`
- C03: `["assigner24", "signals", "temporal", "text_tfidf", "assigner"]`
- C08, C09, C10: `["assigner24", "signals", "temporal", "assigner", "text_tfidf"]`
- C14-C16: `["signals", "assigner", "text_tfidf", "assigner24"]`
- C17, C18: `["signals", "assigner", "text_tfidf", "assigner24", "temporal"]`
- C19: `["signals", "assigner"]`
- C20: `["signals", "assigner", "assigner24", "text_tfidf", "temporal"]`

This list is frozen. No candidate may be added, removed, or adapted after
results are seen. Any post-hoc idea is a new, clearly labelled experiment and is
not part of this ranking.

## 4. Evaluation method

For each genome (including the C1 baseline) and each seed in `(0, 42)`:

1. Call `evaluate_genome(genome, folds=("primary", "rolling"), seed=seed, bootstrap=0)`.
2. Record every per-fold metric and the harness mean.
3. A run is `ok` only if `status == "ok"` and both folds produced metrics.

Aggregation across seeds:

- Per-seed per-fold metrics are the raw fold results.
- The per-seed value of a metric is the arithmetic mean over the two folds
  (equal to the harness `mean` for that seed).
- The reported candidate value is the arithmetic mean over all four
  (seed, fold) runs. With 2 seeds x 2 folds this equals the mean of the two
  per-seed means.
- Deltas are candidate minus C1 on the same four (seed, fold) pairs, using the
  aggregate values.

Primary metrics: `top243`, `top500`, `avg_precision`. Secondary/reported
metrics: `top161`, `auc`, `median_rank`, `work50`, `complexity`.

A candidate with any failed run is `partial` or `error`; it is excluded from
ranking but fully reported. Errors are recorded, not retried with a different
genome.

### Gate-equivalent diagnostic (not eligibility)

Report, for each candidate, whether **the mean** over seeds 0+42 satisfies all
three:

- `delta_top243 >= 6`
- `delta_top500 >= 6`
- `delta_avg_precision >= 0`

This is only a diagnostic against the official gate's thresholds. The official
five-seed gate additionally requires seed averaging at 5, a paired bootstrap CI
lower bound > 0 for top-243 on **both** folds, and is the only mechanism that can
make a challenger eligible.

## 5. Pre-registered ranking rule (fixed before results)

Rank only candidates with complete `ok` runs (all 4 seed x fold evaluations).
Sort by, in order:

1. **Primary:** maximize `min(delta_top243, delta_top500)` (higher is better).
   This rewards candidates that improve both cut sizes rather than trading one
   against the other.
2. **Tie-break 1:** higher `delta_avg_precision`.
3. **Tie-break 2:** lower `complexity` (as returned by
   `cloud.autorank.models.complexity`).
4. **Tie-break 3 (determinism only):** lexicographically smaller candidate ID.

The pre-registered winner is rank 1 under this rule. C00 is included in the
ranking as a sanity check, not as a candidate to adopt.

## 6. Runtime bound and failure handling

- Hard budget: 30 minutes wall clock for the whole 24 x 2 x 2 grid plus the C1
  baseline. The runner uses a 29-minute internal deadline and then stops,
  writing partial results with the completed candidate count.
- At most 4 parallel workers.
- If a candidate errors, the error string is recorded and the run continues.
- If the budget is exhausted, unfinished candidates are marked `not_run` and
  the report states the partial coverage explicitly.

## 7. Outputs

Everything is written under `experiments/repair_champion/`:

- `results.json` — provenance, genomes, all raw per-run/per-fold metrics,
  aggregates, deltas, ranking.
- `candidates.csv` — one row per candidate with means and deltas vs C1.
- `report.md` — full table, top 5, pre-registered winner, gate-equivalent
  diagnostic, failures, caveats.

## 8. Reproduction command

From the repository root:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  .venv/bin/python experiments/repair_champion/run_repair.py
```

`--workers` defaults to 4 and is capped at 4. `--deadline-seconds` defaults to
1740.

## 9. Interpretation caveats (fixed now)

- These results are **exploratory**: 24 candidates selected after seeing the
  same 2025 folds, so the winner's advantage is optimistically biased.
- Fold-level noise is large: the 2025 test sets have roughly 52 positives
  each; a single top-500 hit is about 2 percentage points of that metric.
- No 2026 label is used or claimed. Nothing here says anything about 2026
  accuracy.
- A candidate that clears the gate-equivalent diagnostic still **requires the
  official gate** before adoption, and its numbers remain unverified until the
  auditor checks them and they are registered in the claims ledger.

## 10. Post-run bookkeeping note (added after the run, no protocol change)

The task brief labels the candidate list "24", but the enumerated frozen IDs are
`C00` through `C24`, i.e. **25 genomes**. All 25 enumerated IDs were evaluated;
none was added, removed, or adapted. The "24" is a counting error in the brief,
not a change to the frozen candidate set. The ranking rule and candidate
definitions in sections 3 and 5 are untouched.

The same note applies to the task's "24 x 2 x 2" description: the executed grid
was 25 candidates x 2 seeds x 2 folds, plus C1 x 2 seeds x 2 folds.

## 11. Post-run data availability finding (added after the run)

After running, inspection of the per-fold records showed that the four local fold
caches are not schema-consistent: `primary_seed0`, `primary_seed42` and
`rolling_seed0` lack the `assigner24` columns (`asg24_rate`, `asg24_kev`,
`asg24_kev_log`), while `rolling_seed42` has them. The harness therefore dropped
`assigner24` in 3 of 4 fold runs for every candidate that requested it (24 of the
25 candidates). C00 was thus evaluated without one of its three feature groups
in 3 of 4 runs.

This is a property of the fixed local caches, not a change to the protocol. No
cache was modified. The pre-registered ranking is reported as executed, and the
finding is a first-class caveat: absolute numbers here are not the full champion,
and the official gate must run on consistently built folds. A fresh-cache rerun
would be a new experiment, not part of this pre-registered ranking.
