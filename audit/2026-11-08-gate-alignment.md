# Audit — adoption-gate alignment and the AutoRank champion

**Date:** 2026-11-08
**Auditor:** independent subagent (fresh context; no producer reasoning seen)
**Scope:** the pre-registered adoption gate, the archived blind champion, the C1 comparator, the judged-cut alignment, selection optimism, and time-safety of the champion's feature groups.
**Verdict in one line:** the gate is internally consistent and the champion legitimately fails it (`eligible=false`); the `+6 top500` condition is **not** the judged-equivalent cut, and the champion's `+7.5 top243` headline is inflated by the five-seed control protocol. **Keep C1. Do not revise the gate now. Require independent confirmation before any change.** Recommendation **(c)**.

---

## 0. Bottom line

1. **Rate match is confirmed for the primary fold, not for the gate as a whole.** The judged cut is `500 / 72,670 = 0.688042%`. The primary 2025 test pool is 35,280 rows, so `243 / 35,280 = 0.688776%` is the judged-equivalent cut (242 is farther away: 0.685941%). The rolling test pool is 23,367 rows, so its judged-equivalent cut is `161 / 23,367 = 0.689006%`, **not 243** (1.0399%, 1.51× looser). The gate uses 243 on both folds.
2. **The `+6 top500` requirement is not aligned with the judged cut.** On the backtest, top500 is 1.417% (primary) / 2.140% (rolling) of the pool — 2.06× / 3.11× the judged rate. It is a secondary robustness check on a looser cut, not a judged-cut proxy. It also sits above the empirical search ceiling: the archived single-seed search's best mean top500 is 21.0, while C1's five-seed top500 mean is 16.0, so the gate requires 22.0. No archived run reached 22.0: blind/c1opt single-seed max 21.0, repair five-seed max 20.5, champion five-seed 20.0. Whether an unsearched five-seed text genome could is UNCHECKED.
3. **The archived gate JSON is arithmetically correct and reproducible.** I rebuilt the primary fold from `pool_derived.parquet` with `assigner24` present, recomputed C1's five-seed text scores for seeds 43–46 independently, refitted both genomes, and reproduced every gate number exactly, including the paired-bootstrap CIs/p-values: mean `+7.5` top243, `+4.0` top500, `+0.054171413487934104` AP, `eligible=false`.
4. **The `+7.5` is not a like-for-like gain.** The champion's absolute mean top243 is **18.0**, not 23.0. C1 with five seeds is **10.5**; C1 as evaluated in the search (one seed) is **13.5**. Thus:
   - champion vs C1 single-seed = **+4.5** top243;
   - single-seed C1 vs five-seed C1 = **−3.0** (the five-seed control is worse on top243);
   - gate headline = **+7.5**.
   The champion is deterministic (no `text_tfidf`), so its five-seed gate score is bit-identical to its single-seed search score (AP matches to the last digit). The "five-seed protocol" adds no robustness evidence for the champion; it changes C1.
5. **At rate-matched cuts the champion is borderline, not eligible.** Primary 243 + rolling 161 vs five-seed C1: gains `+7` and `+5`, mean **+6.0** (exactly the threshold), but the rolling top161 paired-bootstrap lower bound is **0.0**, which would fail the gate's own `lo > 0` rule if applied at the judged-equivalent cut (the current gate applies it to top243, where the lower bound is 1.0). Against single-seed C1 the mean gain is **+3.5** (primary `+3` CI `[-4,10]`, rolling `+4` CI `[-2,9]`): clearly below `+6`.
6. **The champion should not replace C1.** The official gate says no; the aligned-cut analysis also says no; the top500 gain `+4.0` is below `+6` and is not distinguishable from zero on the primary fold (`[-4,10]`, `p_gt0=0.726`); and 2026 feature shift is severe. The current C1 submission remains the defensible one.
7. **Revising the gate now would not be legitimate.** The gate predates the blind search (config mtime 22:46; search start ≈22:51), the champion was selected on the same folds from 2,213+ genomes, and even a principled rate-matched revision rejects the champion. Changing the rule after seeing `+7.5/+4.0` would be moving the goalposts. A v2 may only be pre-registered for a *future* search (spec in §9) and must be applied to a genuinely held-out fold.

---

## 1. What I checked and how

I did **not** run the full CLI gate on the local tree because the local fold caches are schema-inconsistent: `primary_seed42`, `primary_seed0` and `rolling_seed0` lack the `assigner24` columns, while `rolling_seed42` has them (this is independently documented in `experiments/repair_champion/PROTOCOL.md` §11). A naive local `run gate` would silently drop `assigner24` on the primary fold (and change the champion from 19/22 to 18/21 top243/top500 on primary). The archived server JSON is therefore the authoritative artifact.

Independent path used:

- Rebuilt the primary fold directly from `data_cache/autorank/pool_derived.parquet` via `candidates.fold_data` (not the stale cached primary fold), with `assigner24` present; rebuilt the rolling fold the same way for the champion, and used the cached `rolling_seed42` fold for C1's text (it has `assigner24`).
- Refitted the champion (`gam`, `n_knots=4`, `C=1.0`, `cap=75`, `flag_quota=400`) and C1 (`hgb` C1 genome, `cap=50`) with plain sklearn through `cloud.autorank.models.fit_predict`.
- For C1's five-seed control, recomputed the TF-IDF OOF text scores for seeds 43–46 independently (sklearn `TfidfVectorizer`/`LogisticRegression`; same pre-registered parameters and `StratifiedKFold` seed), and combined with the cached seed-42 text. This reproduced the gate's C1 AP values **exactly**.
- Rebuilt rankings with `features.select_top`, computed hits/AP with plain NumPy/sklearn, and implemented the paired bootstrap loop independently (`n_boot=500`, seed 42, row resampling, stable `argsort`). All per-fold diffs, CIs and `p_gt0`/`p_lt0` matched the gate JSON exactly.
- Re-derived `assigner24` from raw `known_exploited.csv` and `vulnerabilities.csv` for five months (2024-06, 2025-01, 2025-09, 2026-01, 2026-09): exact match, max abs diff `0.0`.
- Spot-checked `exploit_signals_2024.csv` / `_2025.csv` against the pool for 2024-06 and 2025-09: exact EPSS/flags match; no duplicate `(month,cve_id)` rows.
- Ran a train-label permutation test (5 permutations per fold) and solo-feature ranking checks.
- Built the 2026 scoreboard features in memory (no writes to `results/`), scored the champion, and compared its would-be 2026 top500 with the audited C1 `results/top500.csv`.
- Computed the confirmation-fold (defined in `config.py` but never used by the gate) as an **exploratory** robustness check; its test rows are the same 2025 rows as primary, so it is not independent.

Files read include `cloud/autorank/config.py`, `run.py`, `evaluate.py`, `features.py`, `data.py`, `models.py`, `metrics.py`, `report.py`, `src/model/pool.py`, `docs/kb/00_event_and_rules.md`, `docs/kb/01_data_guide.md`, `docs/kb/02_findings_first_pass.md`, `experiments/repair_champion/PROTOCOL.md`, and the archived JSON/SQLite evidence under `audit/evidence_2026-11-08-gate/`.

---

## 2. Rate match: top243 is right for primary, top161 for rolling; top500 is not the judged cut

Judged cut: `500 / 72,670 = 0.006880418… = 0.688042%`.

| Pool | Rows | 0.688042% equivalent | Exact k | Rate | Ratio to judged |
|---|---:|---:|---:|---:|---:|
| 2026 scoreboard (judged) | 72,670 | 500 | 500 | 0.688042% | 1.000 |
| Primary test (2025-01..09) | 35,280 | 242.741 | **243** | 0.688776% | 1.001 |
| Rolling test (2025-04..09) | 23,367 | 160.775 | **161** | 0.689006% | 1.001 |
| Primary top500 (gate) | 35,280 | — | 500 | 1.417234% | 2.060 |
| Rolling top500 (gate) | 23,367 | — | 500 | 2.139770% | 3.110 |

- **PASS:** `243/35,280` is the judged-equivalent cut on primary. `242` would be 0.685941%, farther from 0.688042% than 243. The `config.py` comment says `35,281`; the actual pool is 35,280, but the rounding still gives 243 (exact 242.748 on 35,281). No material issue.
- **FAIL:** the gate uses top243 on the rolling fold, where the judged-equivalent cut is top161. `243/23,367 = 1.0399%`, 1.51× the judged rate.
- **FAIL:** top500 on either backtest fold is not the judged cut. It is a looser secondary cut (2.06× / 3.11×). The `+6 top500` condition is not a rate-matched judged criterion.

**Consequence:** the gate mixes one correctly aligned condition (top243 primary), one lenient condition (top243 rolling), and one non-aligned robustness condition (top500 on both). That is the structural alignment problem.

---

## 3. Archived gate JSON: internal consistency and exact reproduction

Evidence: `audit/evidence_2026-11-08-gate/archive_final/blind/gate_result.json` (official blind champion gate); `.../c1opt/gate_result.json` is the same champion and the same numbers (only `flag_quota` differs: 400 vs null).

| Item | Claimed | Re-derived | Status |
|---|---:|---:|---:|
| `mean_top243_gain` | 7.5 | `(7.0+8.0)/2 = 7.5` | PASS |
| `mean_top500_gain` | 4.0 | `(3.0+5.0)/2 = 4.0` | PASS |
| `mean_ap_gain` | 0.054171413487934104 | mean of `(.12060315308502262-.06325185149219811)` and `(.144041181683857-.09304965630081329)` = 0.054171413487934104 | PASS |
| `eligible` | false | `7.5>=6` true, `4.0>=6` false, `AP>=0` true, both top243 `lo>0` true → false | PASS |
| primary top243 diff / CI / p | 7.0 / [1.0,12.0] / .976/.014 | exact | PASS |
| primary top500 diff / CI / p | 3.0 / [-4.0,10.0] / .726/.18 | exact | PASS |
| rolling top243 diff / CI / p | 8.0 / [1.0,13.0] / .986/.004 | exact | PASS |
| rolling top500 diff / CI / p | 5.0 / [1.0,10.0] / .994/0.0 | exact | PASS |
| primary `ap_best` | 0.12060315308502262 | exact (champion single-seed AP) | PASS |
| primary `ap_c1` | 0.06325185149219811 | exact (C1 five-seed AP) | PASS |
| rolling `ap_best` | 0.144041181683857 | exact | PASS |
| rolling `ap_c1` | 0.09304965630081329 | exact | PASS |

**Absolute metrics behind the diffs** (reconstructed; the gate JSON does not record them, which is a transparency weakness):

| Fold | Genome | top161 | top243 | top500 | AP |
|---|---|---:|---:|---:|---:|
| primary | champion | 16 | **19** | **22** | 0.1206031531 |
| primary | C1, single seed (search baseline) | 10 | **16** | **20** | 0.0706294901 |
| primary | C1, five seeds (gate control) | 11 | **12** | **19** | 0.0632518515 |
| rolling | champion | 12 | **17** | **18** | 0.1440411817 |
| rolling | C1, single seed | 8 | **11** | **12** | 0.0834126135 |
| rolling | C1, five seeds | 7 | **9** | **13** | 0.0930496563 |
| mean | champion | 14.0 | **18.0** | **20.0** | 0.1323221674 |
| mean | C1, single seed | 9.0 | **13.5** | **16.0** | 0.0770210518 |
| mean | C1, five seeds | 9.0 | **10.5** | **16.0** | 0.0781507539 |

The champion's gate AP values are **identical** to its single-seed search AP values. This is expected: its features are `assigner24 + signals + temporal`, with no stochastic text component; the GAM pipeline is deterministic across seeds. The five-seed average is therefore a no-op for the champion. C1's five-seed average is **not** a no-op: it lowers C1's top243 from 13.5 to 10.5 while leaving its top500 mean at 16.0. That is the source of the headline inflation.

**Verdict:** the gate JSON is internally consistent and was implemented correctly *as coded*. The issue is not arithmetic; it is cut alignment and the asymmetry of the five-seed control.

---

## 4. Judged-cut gains vs the search baseline vs the gate control

| Comparison | primary top243 | rolling top161 (judged cut) | mean rate-matched top-k | rolling top243 (gate) | top500 mean |
|---|---:|---:|---:|---:|---:|
| Champion | 19 | 12 | — | 17 | 20.0 |
| C1, five seeds | 12 | 7 | — | 9 | 16.0 |
| C1, single seed | 16 | 8 | — | 11 | 16.0 |
| Champion − C1 five seeds | **+7** CI [1,12] | **+5** CI [0,10] | **+6.0** | **+8** CI [1,13] | **+4.0** |
| Champion − C1 single seed | **+3** CI [-4,10] | **+4** CI [-2,9] | **+3.5** | **+6** CI [1,11] | **+4.0** |

Key observations:

- Against the **five-seed** control, the rate-matched mean gain is exactly **+6.0**, but the rolling top161 lower bound is **0.0**, which would fail the gate's `lo > 0` rule if applied at the judged-equivalent cut. The gate's current rolling top243 use turns that `+5` into `+8` (1.5 hits of mean inflation: 7.5 vs 6.0).
- Against the **single-seed** C1 that the search actually evaluated, the champion's top243 gain is **+4.5** (primary +3, rolling +6), below the `+6` threshold; the primary fold's CI includes 0. The single-seed comparator is not the deployed C1 (the deployed 2026 C1 uses five seed sets), but it is the comparator used throughout model selection. A robust challenger should beat both; this one does not.
- The confirmation fold (train 2024-01..09, test 2025-01..09; **same test rows, not independent**) gives champion 17/22 vs five-seed C1 13/17 → **+4 top243 / +5 top500**, and vs single-seed C1 11/16 → **+6 / +6**. The headline `+7.5` does not replicate on a different train window. Treat this as exploratory, not as confirmation.
- The top500 gain is **+4.0** in every comparison. It is below `+6` and is not the judged cut. No archived run reached the required mean 22.0: the blind leaderboard max is 21.0 (2,343 ok runs), the c1opt leaderboard max is 21.0 (1,085 ok runs), `arena_top20.json` max is 20.0, the champion five-seed gate is 20.0, and the four repair five-seed gates are ≤20.5 (gains ≤4.5). The `+6` top500 bar is above every archived result.

---

## 5. Statistical power with 52 positives

Primary test: 35,280 rows, **52 positives**. Rolling test: 23,367 rows, **32 positives**.

- One top500 hit = 1/52 = **1.92%** of primary positives; six hits = **11.54%**. On rolling, one hit = 3.13%; six = 18.75%.
- Top500 primary: champion 22 vs five-seed C1 19 → +3, paired CI `[-4,10]`, `p_gt0=0.726`. **Not distinguishable from zero.**
- Top500 rolling: 18 vs 13 → +5, CI `[1,10]`, `p_gt0=0.994`. Positive but on 32 positives.
- Combined mean top500 gain +4.0: an independent-fold row bootstrap gives an approximate 95% interval `[0.0, 8.5]`, `p_gt0≈0.9585` — marginal, not a clear positive. (The folds overlap in rows, so this is approximate; a positive covariance would narrow it, but the point estimate remains +4.)
- Top243 primary: +7, CI `[1,12]`; rolling: +8, CI `[1,13]` — these are the strong numbers, but they are vs the five-seed control. Against single-seed C1: primary +3 CI `[-4,10]` (not significant), rolling +6 CI `[1,11]`.
- A `+6` top500 requirement is about 1.5 hits above the observed +4 and outside the primary-fold interval. With 52 positives, a 2-hit difference is not resolvable. The `-6/+6` top500 requirement is not statistically justified **as a judged-cut criterion**; it can only be defended as a deliberately conservative robustness bar. But it is above the search ceiling and therefore does not discriminate among the candidates that were actually searched.

**Verdict:** the top243 evidence is real on these folds but fragile to the comparator; the top500 evidence is weak and not distinguishable from zero on the primary fold. The gate's rejection is not a statistical accident, but the `+6 top500` bar is not the right way to express the judged cut.

---

## 6. Selection optimism, seed averaging, and multiple testing

**Search size and distribution.**

- Blind search: budget 3,000, **2,213 genomes evaluated**, 80 generations, `seed_c1=false`.
- Leaderboard: 2,403 rows, **2,343 `ok`**, 60 errors.
- Top243 among `ok` runs: mean **12.769**, sd **3.253**, median 13.5, max **18.0**. 30 runs at 18.0; 148 at ≥17; 650 at ≥15.
- Top500: mean **16.952**, sd **3.264**, max **21.0**. 60 runs at ≥20; 7 at 21.
- The champion is the fitness maximum (`top243 + 0.5*top500 + 20*AP − 0.5*complexity`), not a random draw. Its top243 18.0 is the search maximum, but it sits on a broad plateau of 30 genomes; its top500 20.0 is not the maximum (21.0).
- C1-opt: 1,028 genomes, `seed_c1=true`; the same champion was re-found, but on the same folds and with C1 in the population. This is reproducibility on the selection data, not independent confirmation. Three exact C1 copies appear in its `c1_like` list.
- Repair: 25 candidates, four server gate runs (C04, C14, C16, C19), all `eligible=false` (top500 gains +3.0, +4.5, +3.5, +4.5; none reaches +6).
- Arena: local `results/autorank/arena_result.json` is a smoke test (7 genomes, 4 full evaluations, champion = C1 control). `audit/evidence_2026-11-08-gate/arena_top20.json` contains 20 champion-family genomes (top243 18.0, top500 20.0/19.5) with no run metadata; its max top500 is 20.0, not 21.0. The "arena ceiling 21.0" claim is consistent with the blind/c1opt leaderboards, not with `arena_top20.json`.
- Total: >3,200 evaluations on the same primary+rolling folds. At least six challengers were gated. The gate does not control family-wise error; the top243 pass is one of several tests on the same data.

**Seed averaging.**

- The champion is deterministic across seeds (no text; AP exact match). The five-seed gate adds **zero** new information for the champion.
- C1's five-seed control is worse on top243 (10.5 vs 13.5) and equal on top500 (16.0). Thus **+3.0 of the +7.5 headline is a control-protocol effect**, not a champion improvement.
- The remaining **+4.5** vs the search's single-seed C1 is selected on the same folds from 2,213 genomes. It may be partly real (the same genome family is re-found in c1opt/arena and its AP gain is consistent), but its magnitude is optimistically biased and unconfirmed on independent data.

**Blind seeding check.**

- `search_result.json` has `seed_c1=false`, `best == best_nocontrol`, and 10 `c1_like` candidates with **no exact C1 copy**. PASS: the champion was not seeded with C1 in the blind search.
- The c1opt run did seed C1 and contains exact C1 copies; its champion re-finding is not independent. PASS for provenance, FAIL for independence.

**Multiple testing.** With ~2,213 blind genomes, 1,028 c1opt genomes, 25 repair candidates and an arena, the maximum metric is expected to be inflated. The champion's top243 18.0 is at the 98.7th percentile of the 2,343 ok runs; the top500 20.0 is at the 97.4th percentile. A selected maximum at that percentile is not a rare event. The correct control is a held-out fold/search budget, not a post-hoc threshold change.

---

## 7. Time-safety and leakage of the champion's feature groups

Champion feature groups: `assigner24`, `signals`, `temporal`. No `text_tfidf`, no `assigner`, no `vector`/`timeseries`, no CVSS/CWE/structured features.

| Feature group / field | Definition (code) | Independent check | Status |
|---|---|---|---|
| `assigner24` (`asg24_rate`, `asg24_kev`, `asg24_kev_log`) | `data.py::_add_assigner24`: KEV rows with `date_added in [month−24, month)` divided by CVEs published in the same window, per assigner; KEV joined to assigner via `pool.py::kev_with_assigner` | Recomputed from raw `known_exploited.csv` + `vulnerabilities.csv` for 2024-06, 2025-01, 2025-09, 2026-01, 2026-09; max abs diff **0.0** vs `pool_derived`/scoreboard | **PASS** (time-safe) |
| `signals` (`epss_f`, `exploitdb`, `metasploit`, `nuclei`, `poc_github`, `anyx`, `nx`) | `pool.py::build_pool` merges `exploit_signals_YYYY.csv` on `(cve_id, year-month)`; `epss_f = epss.fillna(-1)`; missing flags = 0 | Spot checks 2024-06 / 2025-09 exact; no duplicate `(month,cve_id)` rows; `in_kev` is only used to exclude already-KEV rows, never as a feature | **PASS** (time-safe as-of-month) |
| `temporal` (`age_days`, `month_idx`, `month_volume`, `same_day_count`, `assigner_month_volume`) | `data.py::_add_derived`: publication/assigner/month counts computed from `published`, `snap_month`, `assigner`; no labels | Code inspection: counts are known at month/day end; no test labels or KEV outcomes enter. `month_idx` is a global calendar ordinal | **PASS for leakage**; **FAIL/UNCHECKED for 2026 comparability** (see below) |
| Banned NVD fields | `nvd_status`, `n_affected_cpes`, `n_references`, blank-score patterns, CVSS/CWE, news/threat links | Champion feature matrix contains only the 15 allowed columns; no banned column; `paths.BANNED` includes the NVD fields | **PASS** |
| `text_tfidf` / text | Not used by the champion | Champion feature list has no text group; the C1 comparator uses it but that is outside this champion | **PASS** for champion |
| `flag_quota` | `features.py::select_top` checks `"any_public_exploit" in df.columns`; fold data has `anyx`, not `any_public_exploit`; only the 2026 scoreboard renames it | In backtest the quota is silently ignored. Fixing the name changes the rolling flagged count 387→400 but not top243/top500/AP for this champion; the 2026 natural top500 is already 500/500 flagged, so the quota is also inert there | **FAIL (latent code defect); numerically inert for this champion** |
| Label permutation | Train labels shuffled, champion refit, test metrics recomputed (5 permutations/fold) | Primary top243 observed 19 → permuted mean 12.2 (range 7–14); top500 22 → 18.2 (9–21). Rolling top243 17 → 8.4 (2–12); top500 18 → 11.2 (2–16). Residual is explained by standalone feature signal: `poc_github` alone top500 15, `anyx` 14, `asg24_rate` 12, exploit-then-EPSS baseline 19 | **PASS (no evidence of label leakage)** with caveat: permutation is not a clean null because the features themselves are predictive |

**2026 transfer check (no labels; distribution only).**

Built `scoreboard_2026.csv` features in memory and scored the champion. Important differences from the 2025 primary test:

- `month_idx`: 2025 test 13–21; 2026 1–9. **100%** of 2026 rows are outside the 2025 test range (the feature is a global calendar ordinal, so 2026 Jan–Sep is coded like 2024 Jan–Sep, not like 2025). This is a covariate shift, not leakage.
- `month_volume`: 2025 test [3621, 3967, 4313] (1st/50th/99th pct) vs 2026 [4295, 12242, 17678]; **94.1%** of 2026 rows outside the 2025 test range.
- `assigner_month_volume`: [1, 280, 1136] vs [3, 551, 2473]; **31.2%** outside.
- `same_day_count`: [23, 175, 792] vs [47, 374, 1556]; **14.6%** outside.
- `age_days`: [0, 15, 30] vs [0, 16, 58]; **10.9%** outside.
- `asg24_rate`: [0, 0.0005, 0.0597] vs [0, 0.001, 0.0295]; 0% outside; coverage 70.7% in 2026 vs 60.1% in 2025. But the KEV file ends 2025-12-29, so for later 2026 months the 24-month numerator window is truncated (e.g. Sep 2026 uses 2024-09..2025-12, 16 months) while the denominator still uses 24 months. This biases `asg24_rate` downward for later 2026 months. Time-safe, but not the same feature as in the backtest.
- `epss_f`: 0% outside; blank EPSS is 2% in 2026 vs 10% in 2025.

**Would-be 2026 top500 (in-memory, not written to `results/`).**

- Champion with `cap=75`, `flag_quota=400` vs C1 `results/top500.csv`: overlap **176/500** (35.2%); champion-only **324/500**.
- Champion 2026 top500: **500/500** flagged (`any_public_exploit=1`), max assigner share **15%** (GitHub 75, VulnCheck 75, Apache 57); snapshot shares July **65.6%**, Sep 21.6%, Aug 11.4%, other months ~2%.
- C1 2026 top500: 71.2% flagged, max assigner share **10%**, snapshot shares July 34.8%, Aug 23.0%, Sep 16.4%, Jan–May 4–6% each.
- The champion's `month_idx`/`month_volume` reliance produces a much more July-concentrated list; with no 2026 labels, this cannot be validated. It is a reason for caution, not a proven defect.

**Verdict:** the champion's three feature groups are time-safe and do not use the excluded NVD fields. `assigner24` is exactly reproducible from raw data. The serious caveats are (i) the `flag_quota` code bug (latent, inert for this champion), and (ii) severe 2026 covariate shift in the temporal features, which is UNCHECKED because no 2026 labels exist.

---

## 8. Code, artifact, and process defects found

1. **`GATE` thresholds and `H243`/`H161` are dead config.** `cloud/autorank/config.py:121-132` defines `GATE`, `H243`, `H500`, `H161`, but `run.py:215-220` hardcodes `>=6`, `>=6`, `>=0` and `243`/`500`; `report.py:43-45` hardcodes the same thresholds. `H243`/`H161` are never imported. Changing `config.py` would not change the gate. **FAIL** for single-source-of-truth/pre-registration. (The current literals happen to match the config.)
2. **`flag_quota` is not evaluated in the backtest.** `features.py:111` checks `any_public_exploit`, but fold data exposes `anyx`; only `data.load_scoreboard_base` renames it. The gated champion's `flag_quota=400` is therefore untested by the gate. For this champion the gate metrics are unchanged if the bug is fixed (primary already 436 flagged; rolling 387→400, no hit/AP change; 2026 natural top500 500/500 flagged), but it is a latent validity bug for other genomes and for the claim "the gated genome is the submitted genome." **FAIL (latent); PASS numerically for this champion.**
3. **Stale `results/autorank/gate_result.json`.** The current `results/autorank/gate_result.json` (mtime 22:06) is a *different* genome (`signals,temporal,text_tfidf`, gam C=0.1, cap75, flag350) with `+6.0` top243 / `+3.5` top500. The authoritative blind champion gate is the archived `archive_final/blind/gate_result.json` (23:21) with `+7.5`/`+4.0`. A write-up that reads `results/autorank/gate_result.json` will report the wrong challenger. **FAIL (artifact versioning).**
4. **`report.py` gate status uses the search deltas, not the official gate.** `report.py:40-46` computes eligibility from the single-seed search means: best top243 18.0 vs C1 13.5 → `+4.5`, top500 `+4.0`; both are below 6, so it reports "not eligible" for a different reason than the official gate (which passes top243 at `+7.5` and fails top500 at `+4.0`). The final conclusion is the same, but the stated reason differs. **FAIL (documentation/traceability).**
5. **The `confirmation` fold is defined but never used.** `config.py:18-22` defines it; `report.py:135` says "the gate and confirmation fold exist to prevent overfitting," but no gate/search code uses it. Even if used, its test rows are the same 2025 rows as primary, so it is not independent. **FAIL (documentation/process).**
6. **Pre-registration provenance is partial.** `config.py` mtime 2026-11-07 22:46:21 predates the blind search start (≈22:51, from the 1,769.9 s elapsed and 23:21 archive), which is good. But `run.py` mtime is 23:03 — after the search's first top243 18.0 genome (gen 5, ~98 s) and before the 23:21 gate — and `cloud/autorank/` is untracked in git (`git status: ?? cloud/autorank/`). There is no commit history proving the gate implementation and hardcoded thresholds were frozen before the champion was known. **PARTIAL/UNCHECKED.**
7. **No claims-ledger entries.** `results/claims*.json` contains no gate/champion/top243/assigner24 claims. Per `AGENTS.md` rule 1, these numbers may not be published until registered. I did not edit `results/` (per the task restriction), so the producer must add entries with `source_script` and `output_file`; only then can the auditor mark them verified. **FAIL (process).**
8. **Gate JSON transparency.** The gate result records only per-fold diffs and AP values, not absolute hits or the C1 control's absolute metrics. I reconstructed them, but the artifact should include them. **PARTIAL.**
9. **Best-genome artifact ambiguity.** The blind `best_genome.json` has `seed_average=1`; the gate result's `best_genome` has `seed_average=5` (forced by `with_seed_average`). The c1opt gate has `flag_quota=null` vs blind `400`; the metrics are identical. **PARTIAL (naming/provenance).**
10. **Arena evidence mismatch.** `arena_top20.json` has no metadata and max top500 20.0; the local `arena_result.json` is a 7-genome smoke test with C1 as champion. The claimed "arena top500 ceiling 21.0" is supported by the blind/c1opt leaderboards, not by `arena_top20.json`. **PARTIAL/UNCHECKED.**

---

## 9. Decision

### 9.1 Should the champion replace C1?

**No.** Four independent reasons:

1. **The pre-registered gate says no.** `eligible=false` because top500 `+4.0 < 6`. A pre-registered gate is only meaningful if it is honored when the result is inconvenient.
2. **The aligned-cut analysis also says no.** At the judged-equivalent cuts (primary 243, rolling 161) the champion beats the five-seed control by exactly `+6.0`, but the rolling top161 lower bound is `0.0` (would fail `lo > 0`); against the single-seed C1 used in the search it is `+3.5` (fails `+6`, CIs include 0). There is no specification under which the champion is clearly above the bar except the current one (top243 on both folds, five-seed control), which is the most lenient combination.
3. **The headline is not robust.** `+7.5 = +4.5` (champion vs search C1) `+ 3.0` (control seed effect). The champion is deterministic, so the five-seed protocol adds no robustness for it. The confirmation-fold check (same test rows) gives `+4` top243 vs the five-seed control. Selection was over 2,213+ genomes on the same folds; there is no independent confirmation.
4. **2026 is different and unvalidated.** The champion's temporal features are 10–100% outside the 2025 test range; its would-be 2026 top500 changes 324/500 rows, is 100% flagged, concentrates 65.6% in July, and uses a 15% assigner cap vs C1's audited 10%. With no 2026 labels, the backtest gain does not justify that change.

The AP gain (`+0.0542` vs the five-seed control, `+0.0553` vs single-seed; `.1323` vs `.0770`) is real and consistent, and the champion's top243 ranking is genuinely better on 2025. But AP is not the judged metric, and the top243 gain is not robust enough to override the gate.

**Keep `results/top500.csv` (C1) as the submission.**

### 9.2 Is the `+6 top500` requirement correctly aligned with the judged cut?

**No, not as a judged-cut criterion.** The judged cut is 0.688042%; the primary equivalent is top243 and the rolling equivalent is top161. Backtest top500 is 1.42%/2.14%, 2.06×/3.11× looser. The `+6 top500` condition is a secondary robustness check, not the judged cut. It is also above the empirical search ceiling (required 22.0; archived single-seed max 21.0; archived five-seed gates: champion 20.0 and repair candidates ≤20.5), so it does not discriminate among the searched candidates.

This does **not** mean it should be removed now. It is a legitimate conservative choice in principle; its failure is a real shortfall at a looser cut, and the champion also fails the aligned-cut CI check. The misalignment is a reason to design a better gate for the next search, not a reason to retroactively adopt this champion.

### 9.3 Would revising the gate now be legitimate?

**No.** The gate predates the blind search (config mtime 22:46 vs search start ≈22:51); the champion was selected on the same folds; and the revision would be proposed only after seeing `+7.5/+4.0`. Even the most favorable principled revision (rate-matched cuts) rejects the champion on the rolling `lo > 0` condition and on the single-seed comparator. Changing the rule now would be moving the goalposts to fit the observed result, not fixing a pre-existing specification error in a way that changes the decision.

**Decision: (c) — keep C1 today; require additional independent confirmation before any change.** If the team still wants a v2, pre-register it for a future search (below), commit it before evaluating candidates, and apply it to a held-out fold. Do not apply it retroactively to this champion.

### 9.4 Conditional v2 specification (future searches only; not for this champion)

Only if a new search is run with new data/time:

- **Cuts:** per-fold rate-matched `k_f = ceil(n_f × 500 / 72,670)`: primary 243, rolling 161. Use these, not top243 on both.
- **Comparators:** evaluate C1 under both the single-seed and five-seed protocols; require the challenger to beat **both** on the mean rate-matched top-k gain (`>= 6` hits) and on AP (`>= 0`).
- **CIs:** both folds' paired-bootstrap 95% lower bound `> 0` at the rate-matched cut.
- **Top500:** report as a diagnostic; require only `gain >= 0` as a robustness floor, not `+6`. If the team insists on a top500 gate, it must be justified as a separate operational requirement, not as the judged cut, and its threshold must be below the search ceiling.
- **Independent confirmation:** a fold whose test rows were not used in selection, with labels available at decision time. The current `confirmation` fold does not qualify (same 2025 test rows). If no such fold exists, no adoption.
- **Multiple testing:** one pre-registered final candidate per search, or a max-statistic/Bonferroni correction across all gated candidates (e.g. alpha = 0.05 / number of challengers).
- **Code:** read thresholds from `config.GATE`; use `H243`/`H161`; commit `cloud/autorank/` before the search; record absolute hits and the C1 control metrics in `gate_result.json`.
- **Claims:** register every gate number in `results/claims*.json` before publication.

**Would v2 admit the current champion?** No. Rate-matched mean vs five-seed C1 is `+6.0` (borderline), but rolling top161 lower bound `0.0` fails `>0`; vs single-seed C1 mean `+3.5` fails `+6`. The v2 is not a backdoor.

---

## 10. PASS / FAIL / UNCHECKED summary

| # | Check | Status |
|---|---|---|
| 1a | `243/35,280` is the judged-equivalent cut on primary (0.688776% vs 0.688042%) | **PASS** |
| 1b | `161/23,367` is the judged-equivalent cut on rolling; gate uses 243 | **FAIL** (gate uses 243) |
| 1c | Top500 on the backtest is the judged cut | **FAIL** (1.42%/2.14%, 2.06×/3.11× looser; secondary check) |
| 2 | Gate means, AP, CIs, p-values, `eligible` follow the code | **PASS** (exact reproduction) |
| 3 | `+6 top500` is statistically justified as a judged criterion; champion `+4` distinguishable from zero | **FAIL** (primary CI `[-4,10]`; combined marginal; above search ceiling) |
| 4a | Champion not seeded with C1; no exact C1 copy in blind search | **PASS** |
| 4b | Selection optimism controlled; five-seed adds independent evidence for champion | **FAIL** (2,213 genomes on same folds; five-seed no-op for deterministic champion; +3.0 control effect) |
| 4c | Independent confirmation exists | **FAIL/UNCHECKED** (no held-out fold; confirmation fold unused and shares test rows) |
| 5a | Champion uses no excluded NVD fields | **PASS** |
| 5b | `assigner24` time-safe; exact raw recompute | **PASS** |
| 5c | `signals` as-of-month; no label use | **PASS** |
| 5d | `temporal` features no label leakage | **PASS** for leakage; **UNCHECKED** for 2026 comparability (100% `month_idx` outside test range) |
| 5e | `flag_quota` actually tested by the gate | **FAIL** (silent no-op; numerically inert for this champion) |
| 6a | Current champion should replace C1 | **FAIL** (no; keep C1) |
| 6b | Revise gate now | **FAIL** (not legitimate; recommendation c) |
| 7 | Claims registered | **FAIL** (no gate/champion entries in `results/claims*.json`) |
| 8 | Pre-registration provenance | **PARTIAL/UNCHECKED** (config predates search; runner mtime 23:03 during search; untracked) |
| 9 | Artifact/version consistency | **FAIL** (stale `results/autorank/gate_result.json`; report uses search deltas; arena metadata mismatch) |

---

## 11. UNCHECKED / limits

- **Full CLI gate not rerun.** Local fold caches are schema-inconsistent (primary lacks `assigner24`); I rebuilt the primary fold and reconstructed the gate, matching the archive exactly. A naive local rerun would change the champion's primary top243/top500 from 19/22 to 18/21 because `assigner24` is dropped.
- **Repair-candidate CIs not independently reproduced.** No per-row predictions are archived for C04/C14/C16/C19; I checked their JSON arithmetic and `eligible` flags only. All fail top500; the conclusion is robust.
- **Arena provenance unknown.** `arena_top20.json` has no run metadata; local `arena_result.json` is a smoke test. The "ceiling 21.0" is from the blind/c1opt leaderboards, not the arena file.
- **No 2026 labels.** All 2026 statements are distributional/predicted-ranking statements, not accuracy. The champion's 2026 top500 was computed in memory and not written to `results/`.
- **Permutation test is not a clean null.** Residual permutation performance is explained by standalone feature signal (`poc_github`, `anyx`, `asg24_rate`), not by label leakage; a stronger test would permute features or use a held-out generator.
- **Pre-registration cannot be proven without git history.** `cloud/autorank/` is untracked; the mtime evidence is suggestive but not cryptographic.
- **Claims ledger not edited** per the task restriction (write only under `audit/`). The producer must register the numbers before publication.

---

## 12. Claims status

No `results/claims*.json` entry exists for the gate, the champion, the top243/top500 gains, `assigner24`, or the 2026 candidate ranking. The numbers below are re-derived exactly in this audit and are **supported**, but they are **not registered**, so under `AGENTS.md` rule 1 they must not be published until the producer adds claims and the auditor marks them verified.

| Claim | Value | Re-derived by | Status |
|---|---:|---|---|
| Blind gate mean top243 gain | 7.5 | independent refit + bootstrap | arithmetic PASS; unregistered |
| Blind gate mean top500 gain | 4.0 | independent refit + bootstrap | arithmetic PASS; unregistered |
| Blind gate mean AP gain | 0.054171413487934104 | independent refit | arithmetic PASS; unregistered |
| Blind gate `eligible` | false | code rule | PASS; unregistered |
| Champion absolute top243 (mean) | 18.0 | independent refit | PASS; unregistered |
| Champion absolute top500 (mean) | 20.0 | independent refit | PASS; unregistered |
| C1 single-seed top243 (mean) | 13.5 | independent refit | PASS; unregistered |
| C1 five-seed top243 (mean) | 10.5 | independent text-seed reconstruction | PASS; unregistered |
| Champion vs single-seed C1 top243 gain | +4.5 | independent refit | PASS; unregistered |
| Rate-matched gain vs five-seed C1 (243/161) | +6.0 mean; rolling CI lower 0.0 | independent refit + bootstrap | PASS; unregistered |
| Judged cut rate (500/72,670) | 0.688042% | arithmetic | PASS; unregistered |
| Primary rate-matched cut (243/35,280) | 0.688776% | arithmetic | PASS; unregistered |
| Rolling rate-matched cut (161/23,367) | 0.689006% | arithmetic | PASS; unregistered |

**Recommended ledger entries (producer):** one entry per row above, with `source_script` pointing to the script that reruns the gate/audit reconstruction and `output_file` pointing to the archived `gate_result.json` or a new audit output. The 2026 candidate ranking is *not* a verified claim; it is a predicted ranking with no labels.

---

*End of audit.*
