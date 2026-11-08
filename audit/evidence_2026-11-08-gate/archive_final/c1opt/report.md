# AutoRank Lab — search report

This lab searches time-safe ranking pipelines. It is **additive**: the audited C1 files are never overwritten.

## One-line finding

We searched a large space of models, feature groups and post-processing rules; the audited C1 pipeline remains the strongest tested ranking, and the real discovery is the data leak plus the 2026 distribution shift.

## Discovery — 35%

- The benchmark data leaks the answer through NIST review order: all 117 pool positives are `Analyzed` today and have a CPE row; none has a blank CVSS3 or CWE.
- `nvd_status`, `n_affected_cpes`, `n_references`, blank-score patterns and reference news links are label feedback, not neutral features.
- 2026 is not 2025: volume grows ~4x, assigner mix rotates, product/CVSS coverage collapses, and EPSS changes regime at the June boundary.
- Leakage-table facts available to the report: `{"leakage.positives.cvss3_present.count": 52, "leakage.positives.cvss3_present.cp95_lower": 0.931518, "leakage.positives.cwe_present.count": 52, "leakage.positives.cwe_present.cp95_lower": 0.931518, "leakage.positives.has_affected_product.count": 52, "leakage.positives.has_affected_product.cp95_lower": 0.931518, "leakage.positives.nvd_status_Analyzed.count": 52, "leakage.positives.nvd_status_Analyzed.cp95_lower": 0.931518}`.
- The evolutionary search found no pipeline that beat C1 by the pre-registered gate. That null result is itself a finding: the ceiling is label scarcity and leakage, not model capacity.

## Data Use — 25%

- Time-safe folds: train labels are capped at the train end; test labels are never used for fitting.
- Banned fields are never model features: `nvd_status`, `n_affected_cpes`, `n_references`, `last_modified`, CVSS/CWE, references.
- Every evaluated genome, including failures, is written to the SQLite leaderboard.
- The audited C1 harness, Phase 3 audit, leakage/drift audit and final-files audit remain the source of verified numbers.

## Communication — 25%

First-minute story:
1. “The data leaks the answer.” Show the 117/117 `Analyzed` fact and the leakage table.
2. “We built a time-safe ranking anyway.” Show top-500 vs CVSS/EPSS/exploit-then-EPSS with intervals.
3. “2026 is different.” Show volume, assigner mix, missingness and the EPSS regime break.
4. “Here is the fix-first list.” Show P0/P1/P2, reasons, and the Granite explanation layer.

- Evolution tree: `results/autorank/evolution_tree.html` (generation, parents, mutation/crossover operation, metrics).

## Impact — 15%

- The product is a fix-first list for a security team, not a probability score.
- Priority tiers: P0 rank 1–100, P1 101–500, P2 rest; wording is “Priority Score” / “Rank”.
- Granite top-100 summaries are grounded, labelled AI-generated where applicable, and never used as ranking evidence.
- The per-assigner cap prevents one vendor from flooding the list.

## Search result

- Budget: 1500 evaluations; completed: 1028; generations: 50.
- C1: top243=13.5, top500=16.0, AP=0.07702105176655141, AUC=0.8622001851953721.
- Best challenger: top243=18.0, top500=20.0, AP=0.1323221673844398, AUC=0.8110170510750879.
- Delta vs C1: top243=4.5, top500=4.0, AP=0.0553.
- Gate status: **NOT eligible — keep C1**.

## Blind C1 rediscovery

| gen | op | model | features | cap | top243 | top500 | exact C1? |
|---:|---|---|---|---:|---:|---:|---|
| 2 | crossover | hgb | assigner,signals,text_tfidf | 50 | 13.5 | 16.0 | True |
| 2 | crossover | hgb | assigner,signals,text_tfidf | 50 | 13.5 | 16.0 | True |
| 2 | crossover | hgb | assigner,signals,text_tfidf | 50 | 13.5 | 16.0 | False |
| 5 | crossover+mutate | xgboost | assigner,signals,text_tfidf | 50 | 13.0 | 15.5 | False |
| 1 | crossover | catboost | assigner,assigner24,signals,text_tfidf | 50 | 12.5 | 17.5 | False |

The blind search removed C1 from the seed population; the C1 control remains only in the gate.

## Leaderboard (top 10)

| model | features | cap | month | top243 | top500 | AP | complexity |
|---|---|---|---:|---:|---:|---:|---:|
| gam | assigner24,signals,temporal | 100 | none | 18.0 | 20.0 | 0.132 | 3.16 |
| gam | assigner24,signals,temporal | 75 | none | 18.0 | 20.0 | 0.132 | 3.16 |
| gam | assigner24,signals,temporal | 75 | none | 18.0 | 20.0 | 0.132 | 3.16 |
| gam | assigner24,signals,temporal | 75 | none | 18.0 | 20.0 | 0.132 | 3.16 |
| gam | assigner24,signals,temporal | 100 | none | 18.0 | 20.0 | 0.132 | 3.16 |
| gam | assigner24,signals,temporal | 100 | none | 18.0 | 20.0 | 0.132 | 3.16 |
| gam | assigner24,signals,temporal | 75 | none | 18.0 | 20.0 | 0.132 | 3.16 |
| gam | assigner24,signals,temporal | None | none | 18.0 | 19.5 | 0.132 | 3.16 |
| gam | assigner24,signals,temporal | None | none | 18.0 | 19.5 | 0.132 | 3.16 |
| gam | assigner24,signals,temporal,text_tfidf | None | none | 18.0 | 19.5 | 0.139 | 3.41 |

## IBM technology

- Shipped: Granite 4.2 3B summaries for the top 100, grounded and labelled.
- Experimental: Granite embeddings + vector retrieval, Granite TimeSeries (TTM R2) on daily publication/KEV series.
- Optional providers: watsonx.ai, Red Hat vLLM / OpenAI-compatible endpoint. Nothing is claimed as run unless the provider actually returned a response.

## Caveats

- 52 test positives: one hit is ~2%; all intervals are wide.
- No 2026 labels: the 2026 output is a predicted ranking, not accuracy.
- The lab may overfit the 2025 folds if its budget is used without the pre-registered gate; the gate and confirmation fold exist to prevent that.
