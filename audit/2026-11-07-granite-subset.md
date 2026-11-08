# Audit: Granite watsonx subset comparison (EXPLORATORY), 2026-11-07

Auditor: fresh auditor subagent. Scope: `cloud/make_granite_eval_ids.py`, `src/model/granite_subset_eval.py`,
`results/granite_subset_comparison.json`, `results/claims_model_granite_subset.json` (2 claims).
Re-derivation script: `audit/scratch/g_subset.py` (output `audit/scratch/g_subset_out.txt`). Independent path: labels
recomputed from raw `.data/data/known_exploited.csv` (365-day window, fold caps), own masking regex applied to the pool
description, own TfidfVectorizer/LogisticRegression calls, AUC by Mann-Whitney ranks (scipy `rankdata`), no project imports.
Not touched: `data_cache/granite_embeddings.parquet`, `data_cache/embed_cache/`.

**Missing locally:** `data_cache/granite_embeddings_watsonx_evalslice.parquet` (only its meta exists). It holds the 466
vectors that contain every positive, so **no Granite number can be reproduced here.**

## 1. How the subset was selected (case-control, label-based)

The 1,966 covered CVEs are two pieces:

* **`watsonx_subset` (1,500 rows):** `embed_granite.py --limit 1500` = the first 1,500 rows of `descriptions_to_embed.parquet`.
  That file is in pool row order, and those first rows are the lowest CVE IDs (CVE-2002-20002 .. CVE-2021-47571): old-ID
  CVEs published in 2024-25, 44.5% from the Linux kernel CNA (it has 10.8% of the pool), **0 positives**. So it is not random and
  not representative.
* **`evalslice` (466 rows):** `make_granite_eval_ids.py` picks **every test positive** of both folds, **every (capped) train
  positive** of both folds, and a random sample of test negatives (220 fold 1, 150 fold 2, `random_state=0`). The choice uses labels.
  I rebuilt the list on my own: 466 ids, which matches the meta `n_rows` 466.

Consequences, measured:

| | fold 1 | fold 2 |
|---|---|---|
| covered train rows / positives | 1,248 / 40 (claimed 1,248 / 40) | 547 / 38 (claimed 547 / 38) |
| covered test rows / positives | 718 / 52 of 52 (claimed same) | 557 / 32 of 32 (claimed same) |
| positive rate, covered test vs full fold test | 7.2% vs 0.15% | 5.7% vs 0.14% |
| covered test rows from the old-ID 1,500 block | 301 | 232 |
| train rows with capped label 0 that are pool-positive (included because of a later fold's labels) | 9 | 10 |

* In fold 1 **every training negative** comes from the old-ID block, plus 9 future positives labelled 0. No random negatives
  are used. Both LRs learn "KEV-type text vs old-ID / kernel backfill text", which is a confound, not the task.
* The test set is a case-control sample: all positives, plus negatives that are part random and part old-ID. AUC is not
  comparable to our full-pool AUCs: with the old-ID block removed, the same TF-IDF scores give 0.776 / 0.694 instead of 0.679 / 0.592.
* **Top-k hits mean nothing here.** Top-500 out of 718 rows is 70% of the rows. At a 6-7% positive rate, top-50/100 hits are
  inflated compared with the full pool. They cannot be compared with the baselines' 6/8/19 or with C1's top-500.

## 2. Time-safety

| check | result |
|---|---|
| train/test split by fold months (`C.fold_data`); train and test ids overlap | PASS, 0 overlap in both folds |
| train labels capped (2024-12-31 / 2025-03-31) as pre-registered | PASS, my raw-KEV labels give the same positive counts; pool `y` equals my raw-KEV labels on all 75,148 rows |
| TF-IDF and LR fitted on train rows only | PASS (fitted on covered train only) |
| exploitation wording masked | PASS: embed input text equals my own masking of the pool description on 100% of rows; 0 residual matches |
| Granite model pretrained, no fitting on our labels except the LR | PASS (by construction; vectors UNCHECKED) |
| label-permutation test (TF-IDF, 5 shuffles of train labels) | PASS: fold 1 0.45-0.56, fold 2 0.38-0.53 |
| sample *selection* uses labels (all positives, fold-2 train includes fold-1 test picks) | **FAIL for comparability** (no feature leak, but the sample design depends on the labels, see section 1) |

Excluded NVD fields: none used (text only). Description is today's text, masked, the same as the main model.

## 3. Re-derivation

| quantity | claimed | mine | verdict |
|---|---|---|---|
| n vectors | 1,966 | 1,500 in the local parquet (unique, all in the pool) + 466 = meta `n_rows`, and my rebuilt id list is also 466; no overlap by construction | PASS (466 rests on the meta and the id rebuild, not on the vectors) |
| TF-IDF LR AUC fold 1 / fold 2 | 0.6794294294 / 0.5923214286 | 0.6794294294 / 0.5923214286 | PASS (exact) |
| TF-IDF top50/100/500 fold 1, fold 2 | 8/16/46, 4/7/30 | same | PASS (but meaningless, section 1) |
| Granite LR AUC 0.6981 / 0.6392, AP, top-k | | not reproducible (evalslice parquet missing) | **UNCHECKED** |
| mean delta AUC 0.0328 | | needs the Granite side | **UNCHECKED** |

Noise: the bootstrap 95% CI of the TF-IDF AUC alone is 0.602-0.750 (fold 1) and 0.497-0.675 (fold 2), about 0.15-0.18 wide.
The per-fold deltas (+0.019, +0.047) are small next to that. A paired CI was not computed by the producer and could not be
computed here (UNCHECKED). It is very likely to include 0.

Script detail: the "5 seeds" loop changes nothing. `text_test_score` does not depend on the seed and the OOF scores are thrown
away, so the "mean over 5 seeds" is a single fit.

## 4. Fairness to TF-IDF: FAIL

TF-IDF uses `min_df=8`, which was tuned for about 40k training texts, but here it is fitted on 1,248 / 547 texts. The vocabulary
shrinks to 2,098 / 523 terms, compared with 24,879 / 19,950 when fitted on the full fold train. Granite vectors are pretrained
and need no vocabulary, so the small-n design favours them by construction. A TF-IDF LR fitted on the **full** fold train
(capped labels, same settings) and scored on the **same covered test rows** gets **AUC 0.743 / 0.731**. That is above both
subset-trained models, Granite included (claimed 0.698 / 0.639). So the evidence does not show Granite text beating TF-IDF text
in our real setting. It only shows that Granite does slightly better than a crippled TF-IDF on a tiny training set.

## 5. `selection_hint` and the pre-registered rule: FAIL (conflict)

The pre-registered rule (LOG 17:10 + CLARIFICATION 19:45) compares **G1/G2 (HGB stack, Granite text score) vs C1**, uses **all
rows**, both folds and 5 seed sets, and adopts Granite if its mean AUC >= C1 - 0.01. The `selection_hint` compares **text-only
LRs**, on a **label-selected subset**, against **TF-IDF rather than C1**, and borrows the -0.01 margin. It prints
`"prefer": "granite_text_lr"`. That reads like an adoption decision, which it is not allowed to be. It also existed before the
pre-registered test ran. The rule itself was committed earlier, so it is not invalidated, but nothing from this file may feed
into the adoption choice. The script also reads `data_cache/granite_embeddings.parquet` if that file exists. If it is rerun after
the full embedding job finishes, the output and the claim `n_vectors` silently change meaning.

## Claims

| id | verdict | status |
|---|---|---|
| `p6.granite_subset.n_vectors` (1,966) | PASS: the count is supported (1,500 re-derived from file; 466 from the meta plus the rebuilt id list). The text is acceptable as "CVE descriptions embedded with watsonx Granite" | **verified** |
| `p6.granite_subset.mean_delta_auc` (0.0328) | UNCHECKED (Granite side missing) and FAIL on meaning: label-selected sample, unfair TF-IDF, within noise, no CI | unverified |

## Required fixes

1. Remove `selection_hint` (or rename it to `not_an_adoption_rule` with no `prefer` field). State in the JSON that adoption is
   decided only by the pre-registered `granite.py` G1/G2 vs C1 test.
2. Pin `EMB_PATHS` to the two subset files. Never fall through to `granite_embeddings.parquet`.
3. Drop top-k hits and recall@k from the output, or label them "not comparable to pool top-k".
4. If the delta is ever quoted: commit or provide the evalslice parquet (or its sha256 plus vectors) so it can be audited, add
   a paired bootstrap CI, and add the full-train TF-IDF row (0.743 / 0.731) next to it. Describe the sample as "all positives
   + sampled and old-ID negatives".
5. Remove the no-op 5-seed loop, or say that it is a single fit.
6. Do not quote `mean_delta_auc`, the subset AUCs or the subset top-k in WRITEUP, DEVPOST or the demo. At HEAD, WRITEUP.md
   does not exist and JUDGE_QA.md quotes none of these numbers (checked). Keep it that way.

## What may be said

1. We embedded 1,966 masked CVE descriptions with IBM Granite (`ibm/granite-embedding-278m-multilingual`) on watsonx.ai (Lite plan).
2. In a small exploratory check on a label-selected sample (all positives, few negatives), a Granite-vector text model ranked about as well as a TF-IDF text model trained on the same few rows. This is not comparable to our full backtest and not an adoption test.
3. Whether Granite enters the model is decided only by the pre-registered all-rows G1/G2 vs C1 test.
