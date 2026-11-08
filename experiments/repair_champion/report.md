# Repair experiment around the AutoRank champion — exploratory report

- Generated: 2026-11-08T04:47:17Z
- Git commit: `fddf9d83d41a9512622cafe566f5d93c96a16dab`
- Protocol: `experiments/repair_champion/PROTOCOL.md` (pre-registered)
- Candidates: 25 (`C00`–`C24`; see PROTOCOL.md section 10 on the brief's "24" label)
- Folds: primary + rolling; seeds: 0, 42; bootstrap: 0; `seed_average=1`
- Wall clock: 14.8s

> **This is exploratory selection on the same 2025 folds that produced the
> champion, not a valid five-seed gate. Nothing here is eligible. Any
> challenger requires the official gate before adoption.**

## Baseline (C1, seed_average=1)

| top243 | top500 | top161 | AP | AUC | median rank |
|---:|---:|---:|---:|---:|---:|
| 12.2 | 15.8 | 9.2 | 0.0717 | 0.8686 | 1547.8 |

## Coverage

- Candidates completed (all 4 seed x fold runs): **25/25**
- Ranked candidates: **25**

## Data caveat: inconsistent cached fold schemas (important)

The four local fold caches do not all contain the `assigner24` columns
(`asg24_rate`, `asg24_kev`, `asg24_kev_log`). `evaluate_genome` silently drops
requested feature groups that are missing from a fold, and records them in
`features_dropped`. In this run:

- `primary_seed0`: requested but missing -> `assigner24`
- `primary_seed42`: requested but missing -> `assigner24`
- `rolling_seed0`: requested but missing -> `assigner24`

Consequences:

- 24 of the 25 candidates request `assigner24`; C19 is the only one that does not.
  Those 24 effectively ran with a different feature set in 3 of their 4 fold runs.
- In particular, the nominal champion **C00 was evaluated without `assigner24`**
  in 3 of 4 runs. This screen therefore does not reproduce the full champion, and
  its absolute numbers should not be equated with the quoted champion/gate numbers.
- The pre-registered ranking is reported exactly as executed on these fixed caches.
  No cache was modified (that is outside this experiment's write scope). The official
  gate must run on consistently built folds, and a fresh-cache rerun is needed before
  drawing conclusions about the true champion or about absolute gains.

## Full table (ranked, then unranked)

| Rank | ID | Status | top243 | Δ243 | top500 | Δ500 | AP | ΔAP | minΔ | complexity | notes |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | C08 | ok | 16.0 | 3.75 | 19.2 | 3.50 | 0.1318 | 0.0601 | 3.50 | 3.6580 |  |
| 2 | C20 | ok | 16.0 | 3.75 | 19.2 | 3.50 | 0.1318 | 0.0601 | 3.50 | 3.6580 |  |
| 3 | C04 | ok | 16.8 | 4.50 | 19.2 | 3.50 | 0.1230 | 0.0513 | 3.50 | 3.4080 |  |
| 4 | C09 | ok | 15.5 | 3.25 | 19.5 | 3.75 | 0.1343 | 0.0626 | 3.25 | 3.6580 |  |
| 5 | C18 | ok | 15.5 | 3.25 | 19.5 | 3.75 | 0.1343 | 0.0626 | 3.25 | 3.6580 |  |
| 6 | C17 | ok | 15.5 | 3.25 | 19.0 | 3.25 | 0.1343 | 0.0626 | 3.25 | 3.6580 |  |
| 7 | C05 | ok | 16.5 | 4.25 | 19.0 | 3.25 | 0.1265 | 0.0548 | 3.25 | 3.4080 |  |
| 8 | C00 | ok | 16.8 | 4.50 | 19.0 | 3.25 | 0.0991 | 0.0275 | 3.25 | 3.1580 |  |
| 9 | C19 | ok | 15.0 | 2.75 | 20.5 | 4.75 | 0.1315 | 0.0599 | 2.75 | 2.9080 |  |
| 10 | C06 | ok | 15.5 | 3.25 | 18.2 | 2.50 | 0.1245 | 0.0528 | 2.50 | 3.4080 |  |
| 11 | C21 | ok | 16.8 | 4.50 | 18.2 | 2.50 | 0.1232 | 0.0515 | 2.50 | 3.4080 |  |
| 12 | C01 | ok | 16.8 | 4.50 | 18.2 | 2.50 | 0.1232 | 0.0515 | 2.50 | 3.4080 |  |
| 13 | C22 | ok | 16.8 | 4.50 | 18.2 | 2.50 | 0.1232 | 0.0515 | 2.50 | 3.4080 |  |
| 14 | C15 | ok | 14.5 | 2.25 | 20.0 | 4.25 | 0.1186 | 0.0470 | 2.25 | 3.4080 |  |
| 15 | C14 | ok | 14.2 | 2.00 | 20.5 | 4.75 | 0.1183 | 0.0467 | 2.00 | 3.4080 |  |
| 16 | C16 | ok | 14.2 | 2.00 | 20.8 | 5.00 | 0.1183 | 0.0466 | 2.00 | 3.4080 |  |
| 17 | C13 | ok | 14.2 | 2.00 | 18.8 | 3.00 | 0.0641 | -0.0075 | 2.00 | 2.4500 |  |
| 18 | C07 | ok | 15.2 | 3.00 | 17.5 | 1.75 | 0.1165 | 0.0448 | 1.75 | 3.4120 |  |
| 19 | C23 | ok | 13.8 | 1.50 | 18.2 | 2.50 | 0.1424 | 0.0707 | 1.50 | 3.4080 |  |
| 20 | C24 | ok | 13.8 | 1.50 | 19.8 | 4.00 | 0.1368 | 0.0651 | 1.50 | 3.4080 |  |
| 21 | C03 | ok | 12.5 | 0.25 | 19.8 | 4.00 | 0.1212 | 0.0495 | 0.25 | 3.6580 |  |
| 22 | C12 | ok | 12.0 | -0.25 | 16.0 | 0.25 | 0.0721 | 0.0005 | -0.25 | 3.7700 |  |
| 23 | C02 | ok | 11.8 | -0.50 | 18.2 | 2.50 | 0.1367 | 0.0650 | -0.50 | 3.4080 |  |
| 24 | C10 | ok | 11.5 | -0.75 | 17.5 | 1.75 | 0.1106 | 0.0390 | -0.75 | 3.6620 |  |
| 25 | C11 | ok | 8.2 | -4.00 | 11.2 | -4.50 | 0.0363 | -0.0354 | -4.50 | 3.0560 |  |

## Top 5 by the pre-registered rule

Rule: maximize `min(Δtop243, Δtop500)`; tie-break higher `ΔAP`; then lower complexity; then candidate ID.

1. **C08** — top243 16.0 (Δ 3.75), top500 19.2 (Δ 3.50), AP 0.1318 (Δ 0.0601), complexity 3.658
2. **C20** — top243 16.0 (Δ 3.75), top500 19.2 (Δ 3.50), AP 0.1318 (Δ 0.0601), complexity 3.658
3. **C04** — top243 16.8 (Δ 4.50), top500 19.2 (Δ 3.50), AP 0.1230 (Δ 0.0513), complexity 3.408
4. **C09** — top243 15.5 (Δ 3.25), top500 19.5 (Δ 3.75), AP 0.1343 (Δ 0.0626), complexity 3.658
5. **C18** — top243 15.5 (Δ 3.25), top500 19.5 (Δ 3.75), AP 0.1343 (Δ 0.0626), complexity 3.658

## Pre-registered winner

**C08** (exploratory winner under the fixed rule): mean top243 16.0 (Δ 3.75 vs C1), mean top500 19.2 (Δ 3.50), mean AP 0.1318 (Δ 0.0601).

This candidate is **not eligible** and **requires the official five-seed gate**. Its advantage may be inflated because 25 candidates were compared on the same folds.

It also does **not** reach the gate-equivalent diagnostic thresholds (top243 ≥ 6: False; top500 ≥ 6: False; AP ≥ 0: True).

## Winner vs the champion (reporting only, not the ranking rule)

Champion C00: top243 16.8, top500 19.0, AP 0.0991.

| ID | Δtop243 vs C00 | Δtop500 vs C00 | ΔAP vs C00 | dominates C00 |
|---|---:|---:|---:|---|
| C08 | -0.75 | +0.25 | +0.0327 | False |
| C20 | -0.75 | +0.25 | +0.0327 | False |
| C04 | +0.00 | +0.25 | +0.0239 | True |
| C09 | -1.25 | +0.50 | +0.0352 | False |
| C18 | -1.25 | +0.50 | +0.0352 | False |

Candidates that lose nothing on either cut versus the champion: C04.

Under a strict repair-the-champion lens, the rule winner may still be worse than the
champion on top-243. The official gate compares against C1, so the pre-registered rule
above remains the decision rule for this experiment; this table is diagnostic only.

## Gate-equivalent diagnostic

Thresholds (mean over seeds 0+42, vs C1): Δtop243 ≥ 6, Δtop500 ≥ 6, ΔAP ≥ 0.

**No candidate passes all three diagnostic thresholds.**

This diagnostic is not the gate. The official gate uses five seed averages and a paired
bootstrap CI lower bound > 0 for top-243 on both folds; only that gate can make a challenger eligible.

This screen uses `seed_average=1` by protocol, whereas the official gate averages five
fold seeds. Seed averaging changes absolute gains, so the screen is fixed but is not a
guarantee that a candidate would fail (or pass) the official five-seed gate.

Candidates whose requested features were fully available in every fold run: C19.

- C19: Δtop243 +2.75, Δtop500 +4.75, ΔAP +0.0599 vs C1.

None of the clean candidates reaches the +6/+6 diagnostic.

## Failures and incomplete runs

None: all 25 candidates completed both seeds and both folds.

## Caveats (read before quoting any number)

- **Exploratory selection on the same 2025 folds**, not a valid five-seed gate. The
  winner is optimistically biased by multiple comparisons across 25 candidates.
- **Not eligible.** Only the official five-seed gate can make a challenger eligible;
  this experiment cannot.
- Fold test sets have roughly 52 positives; one top-500 hit is about 2 points of that
  metric, so differences of a few hits are within noise. No bootstrap CIs were computed
  here (`bootstrap=0`).
- No 2026 labels were used. Nothing here is a 2026 accuracy claim.
- All numbers are unverified until independently audited and registered in
  `results/claims*.json`; do not publish them before that.

