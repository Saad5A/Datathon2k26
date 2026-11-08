# Audit: pre-registered Granite test (G1/G2 vs C1) and the regenerated final files (feat/model-ranking @ bf11016), 2026-11-08

Auditor: a fresh-context auditor subagent. Scope: `src/model/granite.py`, which writes `results/granite_comparison.json` and the 87 `p6.granite.*` claims in `results/claims_model_granite.json`. Also `final.py --text G2`, which writes `results/top500.csv`, `scores_2026.csv`, `signal_vocabulary.json` and the 19 `p7.*` claims in `results/claims_model_final.json`.
Spec: LOG.md "PRE-REGISTRATION, Granite text and per-assigner cap" (c603758), "CLARIFICATION of the Granite pre-registration" and the final seed-averaging pre-registration.
Environment: `.venv` (Python 3.12.15, scikit-learn 1.9.1), on the same machine as the producer. Nothing was installed.

**Verdict.** Every number re-derives exactly with an independent code path. The rule was applied mechanically and adopts G2. Granite produced **no measurable gain**:
- G2's mean AUC is 0.0013 above C1's. The seed spread inside a single fold is about 0.03, which is more than 20 times larger.
- On top-500, G2 is equal to or worse than C1 (20 vs 22, 11 vs 11).
- On work-to-50%, the two folds disagree.

All 87 `p6.granite.*` claims and all 19 `p7.*` claims PASS and are marked `verified`. No claim text says Granite "improves" the model.

## Method (independent code path; nothing imports `src/`)
| Script | What it does |
|---|---|
| `audit/scratch/gf_emb.py` | Checks the embeddings: sha256 of the input, id coverage, finite values, norms, text vs my own masking of the raw `vulnerabilities.csv`, and cosine similarity of the watsonx vectors against the local ones |
| `audit/scratch/gf_rederive.py` | Uses my pool (`p3_pool.parquet`, audited in Phase 3), my label and fold code, my regex mask, TF-IDF + LR(C=2, balanced, max_iter 500) with my own 5-fold StratifiedKFold loop, the same LR on the Granite vectors, and HGB(depth 3, lr .05, 150 iterations, min leaf 40, L2 5, `early_stopping=False`). Covers C1/G1/G2 x 2 folds x seed sets 0-4, plus 10 label shuffles of G2 on fold 1 (seeds 2000-2009) |
| `audit/scratch/gf_claims.py` | Checks every p6 claim with my own rank-based AUC, AP, tie-aware top-k and median rank, and my own bootstrap (2,000 resamples, `default_rng(0)`, seed-0 scores) |
| `audit/scratch/gf_final.py`, `gf_compare.py` | Refits G2 on all 75,148 labelled pool rows. Builds the scoreboard features from the raw CSVs. Seed-averages, applies my own plain-Python k=50 cap walk, recomputes occlusion reasons for all 72,670 rows, then checks the contract and the p7 claims |
| `audit/scratch/gf_spot.py` | Re-embeds 30 random texts with the cached open-weights model (offline, CPU), and checks the unseen-assigner rows against KEV for every publication year |
| `audit/scratch/gf_mark.py` | Writes only the `status`/`verified_by` fields. It asserts that no other field changed |

## 1. Spec compliance: PASS
| Item | Finding |
|---|---|
| G1 = C1 with the Granite text LR score in place of TF-IDF; G2 = C1 with both (`txt_g` appended) | PASS. Same columns as the Phase 3 C1, same folds, same capped train labels (40 / 38 positives), same masking, HGB settings and seed sets 0-4. The Granite LR uses C=2, balanced class weights, 5-fold OOF on train, and is fitted on train only (the harness `fit_lr`) |
| C1 here = the verified Phase 3 C1 | PASS. My C1 test scores equal the Phase 3 audit's saved `p3_C1_*` scores (max abs diff 0.0) for all 10 fold-seed runs. The producer also asserts per-seed AUC equality with `model_candidates.json` |
| Rule applied mechanically | PASS. Means: C1 .869867, G1 .836979, G2 .871216. G2 > G1, and .871216 >= .869867 - .01, so G2 is adopted. `select()` has self-checks for the tie and boundary cases |
| Anything tuned after results? | No evidence. `granite.py` and the CLARIFICATION were last changed in 81b3cd5 (2026-11-07 21:33 -0500). The full embeddings were created at 00:12 -0500 on Nov 8. `granite_comparison.meta.json` records clean commit 31614c8, and the sha256 of `granite.py` matches. I cannot rule out unlogged runs on the teammate's subset embeddings before 21:33 (UNCHECKED). The settings are the harness defaults, so there was nothing obvious to tune |

## 2. Selection numbers (mine vs claimed: identical, max abs diff 2.2e-16)
| | fold 1 AUC, seeds 0..4 | median | fold 2 AUC, seeds 0..4 | median | mean |
|---|---|---|---|---|---|
| C1 | .8519 .8847 .8718 .8601 .8505 | .8601 | .8912 .8628 .8798 .8542 .8796 | .8796 | **.8699** |
| G1 | .8574 .8473 .8643 .8435 .8614 | .8574 | .8374 .8490 .8101 .8166 .7941 | .8166 | **.8370** |
| G2 | .8743 .8809 .8804 .8583 .8616 | .8743 | .8886 .8521 .8681 .8478 .8693 | .8681 | **.8712** |

G2 top-500 by cve_id, per seed: fold 1 is 19 21 20 14 20 (median 20, against C1's 22); fold 2 is 14 11 10 11 11 (median 11, against C1's 11). G2 work-to-50%, per seed: fold 1 is 1700 860 982 1238 1296 (median 1,238, against C1's 1,226); fold 2 is 956 1224 1355 1199 1206 (median 1,206, against C1's 1,240). Fold sizes are 39,868/40 and 31,440/38 for train, and 35,280/52 and 23,367/32 for test. Train/test id overlap is 0. Base rate is .147% / .137%.

All 87 p6 claims PASS: median/min/max of every metric, the seed-0 bootstrap CIs for AUC and top500_expected, and the three selection means. No AUC exceeds .93; the highest run is .8912, C1 fold 2 seed 0.

## 3. Embedding integrity: PASS
- The sha256 of `descriptions_to_embed.parquet` is `2fc1cd5f...e276`, which equals both the local and the watsonx meta.
- The embedding file is 147,818 x 768 with unique ids, and its id set equals the input's. Pool ids missing: 0 of 75,148. Scoreboard ids missing: 0 of 72,670. There are no extra ids.
- All vectors are finite, with norms between 0.99999988 and 1.00000014.
- **watsonx vs local, 1,500 shared CVEs:** cosine min 0.999982, mean 0.999988. So "1.0000" is correct to 4 decimals. None of the vectors are bit-identical (max abs element diff .0019), which fits two independent computations rather than a copy. The shuffled-pair control gives a mean cosine of 0.636.
- My own re-embedding of 30 random rows (cached weights at revision a9cb533, bf16 on CPU) gives a minimum cosine of 0.998 against the stored vectors. So the rows are aligned to the right CVE text.
- The cache key includes the model id, so there is no mixing between watsonx and local vectors.
- The watsonx vectors' provenance (that they really came from watsonx.ai) rests on the teammate's meta only: UNCHECKED.

## 4. Leakage: PASS
- **Text = the masked description.** For all 147,818 rows, the embedded text equals my regex-masking of the raw `vulnerabilities.csv` description. This is the same text the TF-IDF model sees. 160 raw descriptions contain exploitation wording, and 0 do after masking. No excluded NVD field, reference, or label enters the embeddings, and the Granite LR uses train rows only.
- **Permutation test, G2 fold 1, 10 train-label shuffles:** AUC mean .497, SD .094, max .624. The real G2 runs score .858-.881, above every shuffle.
- **Residual caveats, not FAILs:**
  - (a) As before, the description is today's text, not the text as of the snapshot month (UNCHECKED).
  - (b) Granite's pretraining corpus and its cutoff relative to the 2024-2025 CVEs are unknown to me, so knowledge of exploitation could in principle sit in the encoder (UNCHECKED). The G1 result (.837, below C1) gives no sign of this.

## 5. New final files: PASS (exact)
- **Submission.** `top500.csv` has one column `cve_id`, 500 unique rows, and all 500 ids are in the scoreboard. It equals ranks 1-500 of `scores_2026.csv`.
- **Contract.** 11 columns in contract order. 72,670 unique rows, with a set equal to the scoreboard. Ranks are a permutation of 1..n. in_top500 and the tiers are consistent (P0 100, P1 400, P2 72,170). The maximum per assigner in the top 500 is 50.
- **Vocabulary.** The 4 signals are unchanged. `_text_source` is "G2", and `description_text` occludes `["txt","txt_g"]`. Its text discloses that the reason value is the TF-IDF score, with `txt_g` occluded together with it (as the CLARIFICATION says).
- **Independent refit.** My refit of G2 on all labelled rows, averaged over seeds 0-4, gives a max abs score diff of **0.0** against `scores_2026.csv`. Rank mismatches: 0 of 72,670. My top 500 is identical in ids and order to `top500.csv`. Reasons match mine on all 72,670 rows, and 0 fail to parse.
- **p7 claims, all 19 PASS.** Train rows 75,148, positives 117, rows scored 72,670. Top-500 assigners: vulncheck 50, apache 50, github 49, oracle 47, wordfence 21, mitre 16, microsoft 16, patchstack 15, cert.org 12, adobe 11. Any public exploit flag .746; EPSS > .1 .048; unseen assigner .170 (85 rows, and none of those assigners has a KEV row of any publication year before the month, so the claim text holds). Tiers 100/400/72,170.
- **Tie note.** Assigners #6 and #7 are tied at 16. Assigner #10 (adobe, 11) is tied with chrome-cve-admin@google.com and 5d1c2695-... at 11, so ranks #6/#7 and #10 by name are an arbitrary order.
- 445 of the 500 ids are shared with the previously verified TF-IDF `top500.csv` (558960b), which matches the LOG.
- No 2026 accuracy is claimed anywhere. PASS.

## 6. Wording: PASS
No claim text, note, meta or vocabulary string in results/ says Granite "improves", "gains" or is "better". The LOG result entry says "adopted by the pre-registered IBM tie-break, with no measurable gain", which is correct. Why it is correct: the G2-C1 mean AUC difference is +.0013, while the seed range within a fold is about .035 and the null SD is about .09. G2 is worse on fold 1 top-500 (20 vs 22) and equal on fold 2. On work-to-50% it is worse on fold 1 and better on fold 2. The per-fold AUC ordering flips (fold 1 G2 > C1, fold 2 C1 > G2). No paired test was run for G2 vs C1, so even "on par" means only "not distinguishable in this test".

## Required fixes / follow-ups (none block the verified status)
1. In any write-up, describe Granite as **adopted because the track requires IBM technology and it did not hurt within the pre-set 0.01 margin**. Do not say it improves accuracy, AUC or hits. G1 (Granite alone) is .033 below C1 and must be reported honestly.
2. `JUDGE_QA.md` line 45 still says the Granite test result is "pending". `docs/kb/team/model-ranking.md` lists the Granite embeddings as "not started". Both are stale (the owners update them; JUDGE_QA is protected, so only with the human's permission).
3. If the assigner list is quoted, say "tied" for #6/#7 and for #10 (one of three at 11).
4. Every number in docs that described the earlier TF-IDF final files (any-exploit share .712, unseen .158, github 41, adobe 26, ...) is now obsolete. A grep found none in the published docs, but they must not be reused.
