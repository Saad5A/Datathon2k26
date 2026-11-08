# Audit: documents and process (feat/model-ranking @ a1c32e4), 2026-11-07

Auditor: fresh-context auditor subagent. Read only; wrote only this file and `audit/scratch/z_docs_*.py`.
No claims, code, results or docs edited; nothing committed. `results/reverse_time.json` and the `rev.*` claims
belong to a concurrent audit and are out of scope here (some `rev.*` claims flipped to verified while I worked).

## C. Plain summary for a beginner teammate

What we found, and the experiment behind each finding:
1. **Hidden leak in NIST fields** (leakage table, `src/model/leakage.py`). All 52 CVEs later added to KEV in the 2025 test had NIST status "Analyzed", a product list, CVSS3 and CWE. Among the others, only 50.1% were "Analyzed" and 64.9% had products. With 52 cases, the true share could be as low as about 93%. We do not use these fields.
2. **The first-pass "win" was inflated** (harness sensitivity runs, then Phase 3). The 25 vs 18-19 top-500 result used training labels from the test period and was the best of 10 seeds (21-25). Under pre-registered, time-safe testing (two folds, 5 seed sets), C1 gets 22 vs 18 in fold 1 (seeds 15-22) and 11 vs 15 in fold 2. Its AUC is higher in every fold and seed (0.860 vs 0.768, 0.880 vs 0.809), but for seed set 0 the paired interval includes zero. So we do not beat the baseline at the judges' metric.
3. **What carries the model** (ablations, post-selection). The text score and the exploit/EPSS signals both clearly matter. Assigner history is not shown to help, and masking exploitation wording costs nothing measurable.
4. **2026 looks different** (drift summary). There are about twice as many rows, the assigner mix shifted (GitHub 5.6% to 15.0%, VulnCheck 1.1% to 9.3%), and 66-68% of Aug-Sep CVEs have no product list.
5. **Final ranking** (`final.py`). C1 is refit on all 117 labelled positives and averaged over 5 seeds, with at most 50 top-500 slots per assigner. The cap was neutral in the backtest. We make no 2026 accuracy claim.

How the numbers were verified: six audit reports by fresh-context auditors rebuilt the pool from the raw CSVs, wrote their own metrics (numpy Mann-Whitney AUC, tie-aware top-k), refit the models from the written spec, and compared every claim line by line (outputs in `audit/scratch/*_out.txt`). In git history, no claim changed value or text while it was marked verified. The auditors' 2026 refit matches `scores_2026.csv` exactly.

Weaknesses in that process:
- The auditors share one pool file and one metrics module, so a bug there would affect every audit.
- Two auditor scripts import producer code (for comparison only).
- LOG.md times are hand-typed and disagree with git by up to 2 hours.
- Pre-registration is shown only by commit order plus run timestamps. Unlogged earlier runs cannot be ruled out.
- The 2025 test period was already used in the first pass to choose C1's features, and the docs do not say so.

## A. Document review

`python3 tools/check_claims.py docs/writeup_model.md JUDGE_QA.md` gives 0 unsupported numbers (exit 0). The checker is weak: it accepts any integer from 0 to 10 and any value that matches any verified claim. So I mapped every number by hand to its ledger key. All numbers below match a verified claim unless I say otherwise.

### A1. docs/writeup_model.md

| Sentence / value | Ledger | Wording | Verdict |
|---|---|---|---|
| 72,670 rows; ranking, not probability; KEV is a proxy | p7.rows_scored | good | PASS |
| "Used: EPSS and the four public-exploit flags ... The assigner ... The description" | | Prose only. Missing the exact column names and two columns that are used: `published` (assigner denominators, 2021+) and KEV `date_added`. The README requires the write-up to say which columns we used | **FAIL (fix W1)** |
| "using only what was known at the end of each CVE's snapshot month" | | Too absolute: the description and the assigner are today's values. Limits covers the description only | FAIL (fix W2) |
| "Fold 1 ... (52 ...) and fold 2 ... (32). The candidates and the selection rule were pre-registered" | p3.fold*.test_positives | Leaves out that the first pass already compared 12 variants on the same 2025-01..09 period, and C1 is the first-pass winner's feature set. LOG 16:05 says "must be disclosed in the write-up". It is not | **FAIL (fix W3)** |
| "An independent auditor re-derived every number with its own code." | audits | Holds for this write-up's numbers. "Own code" has two comparison-only exceptions (B2) | PASS (minor W4) |
| 50.1% / 64.9%; AUC 0.767 vs 0.707 | leakage.negatives.*, leakage.solo_auc.* | "ranks better than EPSS": the unpaired 95% CIs overlap ([.716,.821] vs [.612,.794]) | FAIL (fix W5) |
| "came from training labels that overlapped the test period, plus seed luck (21-25)" | primary.*.top500_cve_id 25, *_best/_worst 19/18, d.top500_min/max | Causal and too strong. Time-safe labels still give 21 vs 18-19. JUDGE_QA's "inflated" is the right word | FAIL (fix W6) |
| 22 vs 18 (15-22); 11 vs 15; AUC 0.860/0.768, 0.880/0.809; "for seed set 0 ... includes zero"; CVSS3 5 to 17 | p3.* medians/min/max, paired.*.seed0, p3.fold1.cvss3.top500_worst/best | good, seed set named | PASS |
| 72,670 vs 35,280; 5.6->15.0%; 1.1->9.3%; 66-68%; 36.2% / 23.8% (upper bound) | drift.* | good | PASS |
| C1; 75,148 rows (117); five seed sets; cap 50 "neutral ... not an improvement" | p7.*, p5.cap.* | good. Could add "assigner history is not shown to help (ablation)" | PASS |
| IBM: "via watsonx.ai ... no results yet" | | JUDGE_QA says "watsonx.ai or the open Granite weights". The two documents disagree | minor (W7) |
| Limits: 52 positives, one hit about 2%, no 2026 labels, today's text, mask | | Missing: unseen-assigner weakness, EPSS gaps in Jan-Feb 2025 (44.7% / 23.3% blank), survivor effect | PASS (recommend W8) |

### A2. JUDGE_QA.md

| Q | Issue | Verdict |
|---|---|---|
| 1, 2 | Q2 lists columns in prose; the same gap as W1. "Auditor reproduced every 2026 score exactly from the allowed columns alone" is supported by audit/2026-11-07-final.md item 3-4 | PASS (W1 applies) |
| 3 | "NIST reviews attacked CVEs first, so ..." is the organisers' README explanation, but here it reads as our finding. Attribute it. "later-exploited" should read "later KEV-listed" | FAIL (fix Q3) |
| 4 | 93% matches the leakage.positives.*.cp95_lower value 0.932 | PASS |
| 5 | "On AUC, yes." then the seed-0 caveat. The opener claims more than the borderline evidence. Rest correct | FAIL (fix Q5) |
| 6 | 65 -> 40, 21, best of 10 (21-25) all verified. "Our audit caught both problems": the producer's harness sensitivity sections B and D found them (LOG 16:25, data-engineer), and the audit confirmed them and made them binding | FAIL (fix Q6) |
| 7 | "We fixed this rule, and the three candidates, in LOG.md before running anything." Not true for the test data: the first pass had already run on 2025-01..09, and C1 = the first-pass winner | **FAIL (fix Q7, same as W3)** |
| 8 | "so the model is not reading the answer from somewhere else": a permutation test only rules out label paths that bypass training. It does not prove the features are time-safe (that was checked separately) | FAIL (fix Q8) |
| 9 | "(6 of the 52 positives)" said "actively exploited": h.test.positives_with_wording = 6 counts the whole wording pattern (also "exploited in the wild", "CISA", "KEV"). "so most of our signal comes from text" is too strong: dropping the signals hurts as much as dropping text (top-500 22->11 vs 22->9) | FAIL (fix Q9) |
| 10 | "6 to 8" are the organisers' 2026 baseline figures (task prompt: 6 EPSS, 7 CVSS3, 8 exploit-then-EPSS), not ours. They pass the checker only because they are 10 or less | PASS (say "the organisers report") |
| 11 | all verified | PASS |
| 12 | 22->20, 11->12, rule, VulnCheck/Apache/Oracle at 50 all verified. Missing the 2021+ window caveat required by phase3-fixes-cap fix 4 | PASS (recommend) |
| 13, 14 | match final audit; Granite has no results | PASS |
| 15 | "The auditor also found the problems behind our first-pass result": same misattribution as Q6. "re-derived each one with different code": true per-claim (scratch outputs), with the two comparison-only exceptions | FAIL (fix Q15) |

### A3. LEARNING.md, "What we did, phase by phase"

| Sentence | Verdict |
|---|---|
| "the old numbers come back": harness audit says 7 of 12 first-pass rows differ at printed precision (baselines and text-only exact) | FAIL, minor (fix L1) |
| "the auditor checked that it was committed before the results existed": the audit (D4) found it consistent but could not rule out unlogged runs | PASS (add the caveat) |
| Phase 3 table, 0.870/0.848/0.836, "does not prove C1 is better than C2", seed-0 CI -0.015..+0.181 | PASS |
| "In fold 1, 2 of 5 seed sets exclude zero" is from the audit report (per-seed lower bounds), not a ledger claim | UNREGISTERED (fix L2) |
| "This shows the model is not finding the answer some other way." (permutation) | FAIL (same as Q8) |
| "these columns are filled in by NIST's review, which reaches attacked CVEs first": README explanation, unattributed | FAIL (same as Q3) |
| "Most of our signal therefore comes from the description text" | FAIL (same as Q9) |
| Drift bullets (338->382, 9.8%/2.0%, 35%/50%, 66-68%, 36.2%/23.8%) | PASS. "NIST has not caught up" is speculation: say "possibly because NIST review lags" |
| Final: 75,148/117, cap neutral (22->20, 11->12), VulnCheck/Apache/Oracle 50, GitHub 41, Adobe 26, "four assigners tie at 12" (from audit-final), 71.2/4.8/15.8%, P2 72,170 | PASS (recommend the 2021+ window caveat) |
| Reasons section | PASS |

### A4. KB 02, "Verified findings, Phase 3 to final"

Every number maps to a verified claim: 0.932; 50.1/64.9; solo AUCs .767/.690/.675/.652/.643; table; +0.092/+0.071; +3.6/-3.6; ablations 9/8, .836/.788, 11/4, .861/.867, .869/.865, .823; drift; p7. **PASS**, with one wording fix. "So: better overall ordering" should read "higher AUC in every fold and seed, borderline (seed-0 interval includes 0)" (fix K1). Out of scope but stale: the "Signals and text" caveat still says the 9-of-52 result is "not yet in the claims ledger". It now is (p3.fold1.unseen_assigner.positives).

### A5. results/backtest_summary.json

- `audit/scratch/z_docs_bs.py`: every non-null `claim_ids` entry (both folds, all methods, CI and range lists) points to an existing **verified** claim with an identical value. 0 BAD, 0 MISSING. **PASS.**
- Null ids (values present, must not be displayed): fold1 assigner_only.median_rank, ours_first_pass_optimistic.median_rank; fold2 assigner_only top250, median_rank, work_to_catch_50pct, ci95. Note 8 tells the UI this. PASS, but the UI must enforce it.
- Notes:
  - Note 1: "publication month" is accurate, because snapshot = published month in the pool (FEATURES.md).
  - Note 2: 1/52 ≈ 1.9%, 1/32 ≈ 3.1%. Correct.
  - Note 3: "its paired bootstrap interval includes 0" for top-500 is true for seed set 0 (fold 1 [-8.1, 6.0], fold 2 [-8.8, 1.0]), but the note does not say which seed set. **FAIL, minor (fix S1).**
  - Notes 4-7: accurate. "ci95 for 'ours' is from seed set 0" matches the claim texts.

## B. Process audit

### B1. Pre-registration order (`git log -S` on LOG.md; run times from `results/*.meta.json`, `date_utc` converted to -0500)

| Rule | Pre-reg commit | Results run | Results commit | Verdict |
|---|---|---|---|---|
| Phase 3 candidates and selection | b18032b 16:44:31 | first run 16:55:38 at HEAD cecfbc5 (b08b518 meta); rerun 17:19:09 at 2d63b58, clean | b08b518 16:56:27 | PASS (order) |
| Granite rule + per-assigner cap | c603758 17:08:03 | cap 17:19:44 at 2d63b58, clean; Granite: no results exist | 0da5fbc 17:20:33 | PASS |
| Granite clarification (settings) | 81b3cd5 21:33:41 | none (no embeddings; claims_ibm unverified) | n/a | PASS |
| Final seed-mean + k=50 | 2d63b58 17:15:52 | final.py 18:07:16 at 2760292, clean | 286054a 18:07:26 | PASS. The rule was written after the per-seed 2026 shares from cap.py had been seen. No labels exist, and the rationale discloses this |
| Reverse-time check | d4dc0f8 21:31:51 | 21:33:39 at HEAD d4dc0f8, **dirty** (reverse_time.py uncommitted) | f9bf05b 21:34:19 | PASS on order only. The 108 s gap and dirty tree cannot exclude an earlier draft run: UNCHECKED |

**FAIL (process): LOG.md timestamps are hand-typed and unreliable.** The Phase 3 pre-reg says 16:55 but was committed at 16:44. The seed-mean rule says 17:25 but was committed at 17:15. The reverse-time pre-reg and result say 19:30 / 19:55 but were committed at 21:31 / 21:34, and the run time is 21:33. The final-audit entry says 18:45, but its commit is 18:32. Ordering evidence must come from git and meta, not from LOG times (fix P1).

### B2. Independence of auditor scripts
`grep` over the 40 `audit/scratch/*.py` files for imports of pool / candidates / reproduce_first_pass / final / cap / metrics / leakage / drift, `sys.path` to `src/model`, and `exec`:
- `p3_hand.py` imports `candidates.add_window_features` and `pool.load_pool`, only to compare with the hand computation. It is disclosed in audit/2026-11-07-phase3.md.
- `f_2026_diag.py` imports `candidates`, `reproduce_first_pass` and `pool` loaders (no fitting) to diagnose a mismatch. It is disclosed in audit/2026-11-07-phase3-fixes-cap.md.
- `ld_6_boot.py` `exec`s the auditor's own `ld_1_leak.py`. That is fine. `a2_baselines.py` reads the producer cache `data_cache/backtest_pool.parquet` for comparison only. `my_pool2.parquet` is the auditor's own pool. `ld_3_domlift.py` takes the news-domain list from the producer meta (an input definition).
- **PASS with 2 disclosed exceptions.** Weakness: every later audit reuses the harness auditor's `my_pool2.parquet` / `p3_pool.parquet`, `mymetrics.py` and `p3_C1_*.npy`. A bug in `a1_pool.py` or `mymetrics.py` would therefore spread to every audit. Also, the score `.npy`/`.npz` files are untracked, so later checks cannot be replayed from the repo without the expensive refits.

### B3. Traceability
- Verified claims per report: harness 249, leakage-drift 59, phase3 83, phase3-fixes-cap 265 (226 p3 + 37 p5 + 2 leakage), remaining 412 (320 p3 + 92 primary), final 19. Total 1,087 outside `rev.*`. Every `verified_by` file exists, no verified claim lacks `verified_by`, and no unverified claim has one.
- Each report covers its groups at section level. 30 random verified claims (`z_docs_sample.py`, seed 20261107): 17 values are quoted in the report text. The other 13 (CI bounds) each have a "mine vs claimed ... OK" line in the auditor outputs (`u_check_out.txt`, `p3_boot_out.txt`, `a5_out.txt`). **PASS.**
- `z_docs_hist.py` walks all 20 commits that touch the claims files. **0 claims changed value or text while staying verified.** 194 re-texted p3 claims were reset and then re-verified. 24 verified baseline min/max claims were removed at 0da5fbc (noted in phase3-fixes-cap). **PASS.**

### B4. Reproducibility (meta files)
- Clean: first_pass_repro (48e4e23), model_candidates (2d63b58), assigner_cap (2d63b58), scores_2026 (2760292).
- Dirty:
  - leakage_table: 21a534b, run 21:24:48, code committed in de10050 at 21:25:01.
  - drift_summary: 89e6dc9, run 16:58:51, code committed in f64fccf at 16:59:21.
  - reverse_time: d4dc0f8.
  - For all three, the recorded code sha256 equals the committed HEAD code, so the outputs match committed code. But no LOG line or meta field explains the dirty flag (contrast with Phase 3 D3, which was re-run clean). **FAIL, minor (fix P2).**
- `final.py` at HEAD differs from the hash in `scores_2026.meta.json` (81b3cd5 added `--text`). The claim that the default reproduces the files byte-for-byte, and the run_all.py full rebuild, are unaudited. **UNCHECKED** (I may not write to results/).
- `sidecar.py` counts untracked files as dirty (`git status --porcelain`), so auditor scratch files can set the flag.

### B5. Leaks and biases found, how, and what happened
| # | Issue | Found by | Resolution | Disclosed in docs? |
|---|---|---|---|---|
| 1 | Train labels overlap test period | producer harness section B; audit made it binding | time-safe labels in Phase 3 | yes |
| 2 | Seed luck (25 = max of 21-25) | producer section D; audit | 5 seed sets, medians, seed-mean final | yes |
| 3 | Selection optimism: first pass compared 12 variants on the same 2025 test; C1 = that winner | orchestrator LOG 16:05; harness audit | pre-registration for later choices; the 2025 period was reused | **NO, open (W3/Q7)** |
| 4 | Early stopping silently on | producer section C; audit | off in Phase 3 | KB only |
| 5 | Post-hoc exploitation wording in descriptions | producer section H; audit | masked; ablation shows no effect | yes |
| 6 | Description = today's text (other edits) | harness audit | not fixable | yes |
| 7 | NVD status/products/CVSS3/CWE leak (52/52) | leakage table + audit | excluded | yes (headline) |
| 8 | "All 52 positives had prior-KEV assigners" not time-safe | KB correction; harness audit (9 of 52) | ledger p3.fold1.unseen_assigner | not repeated (good) |
| 9 | No-prior-KEV share used a 2021+ filter | leakage-drift audit | redefined, 36.2/23.8 | yes |
| 10 | News-link list incomplete | leakage-drift audit | labelled lower bound | KB yes |
| 11 | Structured rows use blank-score pattern | phase3 + remaining audits | plus_structured labelled; **3 first-pass struct rows still not labelled leaky in the ledger** (remaining fix 1) | open, not published |
| 12 | Seed-0 vs median labelling (D2); median-of-bounds CIs | phase3 / fixes-cap audits | D2 fixed; 8 claims still unverified, never re-texted | open, not published |
| 13 | CVSS3 tie-order artefact; 17 tie-order claims | producer; audits | held unverified | yes (5 to 17) |
| 14 | Unseen-assigner weakness: fold 1 C1 .737 vs exploit-then-EPSS .920 (9 pos) | phase3 audit | none | **NO** (2026 has 23.8% such rows; 15.8% of our top 500) |
| 15 | EPSS blank 44.7%/23.3% in Jan/Feb 2025; EPSS model change Mar 2025 | harness audit | none | LEARNING only |
| 16 | Survivor effect; assigner = today's value | FEATURES.md, harness audit | not fixable | not in write-up |
| 17 | 2026 assigner shares depend on 2021+ window and seed | fixes-cap audit | seed-mean final | window caveat missing |
| 18 | Reverse-time confounds (censored 2025 labels, weak EPSS on 2024) | producer LOG | not used as evidence | docs do not use it (good) |

## Required fixes (exact sentence -> proposed rewording)

- **W1** (writeup "Data and what we used"; JUDGE_QA Q2): append "Columns: `exploit_signals`/`scoreboard_2026` `epss`, `exploitdb`, `metasploit`, `nuclei`, `poc_github` at `snapshot_month`; `vulnerabilities.csv` `assigner`, `description`, `published` (CVEs published 2021+ for assigner history); `known_exploited.csv` `date_added` (rows before the snapshot month). Nothing else."
- **W2**: "using only what was known at the end of each CVE's snapshot month" -> "using only information dated on or before the end of each CVE's snapshot month, except the description and assigner fields, which are today's values (see Limits)".
- **W3 / Q7**: add to "How we tested": "The first pass had already compared 12 variants on the 2025-01..09 period, and C1 reuses the first-pass winner's inputs, so that period is not fully held out and our fold-1 numbers may be slightly optimistic." In Q7, replace "before running anything" with "before running Phase 3 (the 2025 data had already been used in our first pass)".
- **W5**: "The product count alone ranks better than EPSS (AUC 0.767 vs 0.707)." -> "In this backtest the product count alone scores a higher AUC than EPSS (0.767 vs 0.707; the intervals overlap)." Apply the same in JUDGE_QA Q3 and LEARNING.
- **W6**: "came from training labels that overlapped the test period, plus seed luck" -> "was inflated by training labels that overlapped the test period and by seed luck".
- **Q3** (and LEARNING): "NIST reviews attacked CVEs first, so these columns partly record ..." -> "The organisers' README explains why: NIST reviews attacked CVEs first, so these columns can partly record that an attack was already noticed." Also "later-exploited" -> "later KEV-listed".
- **Q5**: "On AUC, yes." -> "On AUC, our estimate is higher, but the gain is borderline."
- **Q6**: "Our audit caught both problems" -> "Our own sensitivity checks found both, and the independent audit confirmed them". **Q15**: "The auditor also found the problems behind our first-pass result" -> "The auditor confirmed the problems behind our first-pass result".
- **Q8** (and LEARNING "This shows the model is not finding the answer some other way."): -> "so no path from the test labels into the model bypasses training. Time safety of each feature was checked separately."
- **Q9**: "some 2025 descriptions already said 'actively exploited' (6 of the 52 positives)" -> "6 of the 52 positives already contained exploitation wording such as 'actively exploited' or 'CISA'". "so most of our signal comes from text" -> "so text is our strongest single input; dropping it, or dropping the exploit/EPSS signals, clearly hurts". Apply the same in LEARNING ("Most of our signal therefore comes from the description text").
- **L1**: "the old numbers come back" -> "the baseline and text-only numbers come back exactly; the boosted-tree rows differ slightly".
- **L2**: register "2 of 5 seed sets exclude zero" (per-seed paired AUC CI lower bounds) in the ledger, or remove it.
- **K1**: KB "So: better overall ordering" -> "So: higher AUC in every fold and seed (borderline; seed-0 interval includes 0)".
- **S1**: backtest_summary note 3: "its paired bootstrap interval includes 0" -> "its paired bootstrap interval (seed set 0) includes 0".
- **P1**: record LOG times from the clock (e.g. `date`) or cite commit hashes in pre-registration entries.
- **P2**: re-run leakage.py and drift.py from a clean commit, or add a LOG line explaining the dirty metas. Get `final.py` at HEAD audited (default output byte-identical) before relying on run_all.py.
- Recommended (not blocking): W4 (say "with its own code, apart from two comparison-only checks"); W7 (make the IBM wording match); W8 (add the unseen-assigner weakness once its baseline value is registered, plus the EPSS Jan-Feb 2025 gaps and the survivor effect to Limits); the 2021+ window caveat next to 2026 assigner counts; label the 3 first-pass structured rows leaky in the ledger; re-text or drop the 8 median-of-bounds claims.

UNCHECKED: whether earlier unlogged runs preceded any pre-registration; `final.py` HEAD reproducibility; run_all.py; `rev.*` claims (concurrent audit).
