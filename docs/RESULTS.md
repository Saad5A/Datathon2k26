# Results — what the model achieves

This is the consolidated results sheet. Raw artifacts are in `results/`; independent checks are in `audit/`; the full narrative is in `docs/writeup_model.md` and `JUDGE_QA.md`.

> **No 2026 accuracy claim.** The 2026 scoreboard has no outcomes we can see. All labelled metrics below are 2025 backtests. KEV is a proxy for exploitation, not a complete record of attacks.

## The submitted ranking

The final submission is **G2**:

- C1: HistGradientBoosting on time-safe exploit signals + assigner KEV history + masked description TF-IDF.
- G2: C1 plus an IBM Granite embedding text score.
- G2 was adopted by the **pre-registered Granite tie-break** (mean AUC within 0.01 of C1; declared in advance in favour of IBM technology).
- **No measurable gain over C1**: mean AUC 0.8712 vs 0.8699.
- Final file: `results/top500.csv`; full ranking: `results/scores_2026.csv`.
- The top 500 is capped at 50 rows per assigner; the cap was neutral in backtest, used for 2026 drift robustness.

## 2025 backtest — fold 1

Test: `2025-01..2025-09`, 35,280 rows, **52 positives** (one hit ≈ 2%). Train labels end `2024-12-31`. Values are medians over 5 seed sets.

| Method | Top-500 | Top-250 | AUC | Avg precision | Median rank of positives |
|---|---:|---:|---:|---:|---:|
| CVSS3 | 5 | 5 | 0.732 | 0.0064 | 7,960 |
| EPSS | 8 | 8 | 0.707 | 0.0309 | 3,379 |
| Exploit code → EPSS | 18 | 15 | 0.768 | 0.0471 | 2,499 |
| **C1 (ours)** | **22** | **14** | **0.860** | **0.0759** | **1,249** |
| **G2 (final, ours)** | **20** | **15** | **0.874** | **0.0518** | **1,288** |

## 2025 backtest — fold 2

Test: `2025-04..2025-09`, 23,367 rows, **32 positives**. Train labels end `2025-03-31`.

| Method | Top-500 | Top-250 | AUC | Avg precision | Median rank of positives |
|---|---:|---:|---:|---:|---:|
| CVSS3 | 5 | 4 | 0.714 | 0.0083 | 5,048 |
| EPSS | 6 | 6 | 0.713 | 0.0299 | 1,867 |
| Exploit code → EPSS | 15 | 13 | 0.809 | 0.0523 | 524 |
| **C1 (ours)** | **11** | **10** | **0.880** | **0.0637** | **1,348** |
| **G2 (final, ours)** | **11** | **9** | **0.868** | **0.0507** | **1,236** |

## What this actually achieves

- **Strong ranking quality.** G2/C1 AUC is about **0.87**, vs 0.71–0.77 for CVSS/EPSS. The typical exploited CVE appears around rank **1,249–1,288**, vs 1,867–7,960 for the baselines.
- **Earlier surfacing** of the median exploited CVE, which is the practical “work saved” story.
- **Top-500 is noisy, not a blowout.** C1 gets 22/11 hits in the two folds; the best simple baseline gets 18/15. G2 gets 20/11. The top-500 difference is not robust; the defensible advantage is AUC/median rank, not “we catch everything.”
- **G2 is not an improvement over C1.** It was adopted by the declared IBM tie-break; its mean AUC is +0.0013, while its top-500/AP are slightly lower. Say “adopted, no measurable gain,” never “Granite improves accuracy.”
- **No 2026 accuracy.** We can describe the 2026 distribution and the predicted ranking, but only the judges can count 2026 hits.

## The separate evolution experiment

The AutoRank evolutionary search is **not the submitted model**. Its complete lineage, gate report, and audit are in `evolution/`, `audit/2026-11-08-gate-alignment.md`, and `audit/evidence_2026-11-08-gate/`. It is an exploratory search result, not a 2026 claim.

## Evidence map

| Claim / result | Source |
|---|---|
| C1 / baselines, fold 1 + fold 2 | `results/backtest_summary.json` |
| G2 vs C1, per-fold and seed medians | `results/granite_comparison.json` |
| Final ranking and top 500 | `results/scores_2026.csv`, `results/top500.csv` |
| Claim ledger | `results/claims_model*.json` |
| Granite audit | `audit/2026-11-08-granite-final.md` |
| AutoRank gate audit | `audit/2026-11-08-gate-alignment.md` |
| Narrative / judge answers | `docs/writeup_model.md`, `JUDGE_QA.md` |
| 2026 drift | `results/drift_summary.json`, `docs/kb/02_findings_first_pass.md` |

## Reproduce

```bash
.venv/bin/python run_all.py                 # rebuild results/
.venv/bin/uvicorn server.app:app --port <PORT>
cd dashboard && npm run build && npm test
```

Every published number must be in `results/claims*.json` before it is quoted. One hit in the 2025 test is about **2%**, so always read the interval, not just the count.
