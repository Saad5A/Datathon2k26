#!/usr/bin/env python
"""Bounded, pre-registered repair experiment around the AutoRank champion.

See PROTOCOL.md in this folder. This script only *evaluates* the frozen 24
candidate genomes plus C1 with evaluate_genome; it never writes the audited
results files or anything under cloud/autorank/.
"""
from __future__ import annotations

import os

# Must be set before numpy / sklearn are imported.
for _var in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ.setdefault(_var, "1")

import argparse
import csv
import json
import multiprocessing as mp
import platform
import subprocess
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloud.autorank.evaluate import C1_GENOME, evaluate_genome  # noqa: E402
from cloud.autorank.models import complexity  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
FOLDS = ("primary", "rolling")
SEEDS = (0, 42)
METRIC_KEYS = ("top243", "top500", "top161", "auc", "avg_precision", "median_rank", "work50")
MAX_WORKERS = 4


# ---------------------------------------------------------------------------
# Frozen candidate list (matches PROTOCOL.md section 3 exactly)
# ---------------------------------------------------------------------------

BASE_FEATURES = ["assigner24", "signals", "temporal"]
F_TEXT = BASE_FEATURES + ["text_tfidf"]
F_ASSIGNER = BASE_FEATURES + ["assigner"]
F_TEXT_ASSIGNER = BASE_FEATURES + ["text_tfidf", "assigner"]
F_ASSIGNER_TEXT = BASE_FEATURES + ["assigner", "text_tfidf"]
F_C14 = ["signals", "assigner", "text_tfidf", "assigner24"]
F_C14_TEMPORAL = F_C14 + ["temporal"]


def _genome(features, model="gam", params=None, cap=75, flag_quota=400, month="none"):
    return {
        "features": list(features),
        "model": model,
        "params": dict(params) if params is not None else {"n_knots": 4, "C": 1.0},
        "postprocess": {
            "cap": cap,
            "month_allocation": month,
            "flag_quota": flag_quota,
            "seed_average": 1,
        },
    }


def frozen_candidates() -> list[tuple[str, dict]]:
    """Return the 24 (id, genome) pairs, in the pre-registered order."""
    gam = lambda **kw: {"n_knots": kw.get("n_knots", 4), "C": kw.get("C", 1.0)}  # noqa: E731
    cands: list[tuple[str, dict]] = [
        ("C00", _genome(BASE_FEATURES)),
        ("C01", _genome(F_TEXT)),
        ("C02", _genome(F_ASSIGNER)),
        ("C03", _genome(F_TEXT_ASSIGNER)),
        ("C04", _genome(F_TEXT, params=gam(C=0.1))),
        ("C05", _genome(F_TEXT, params=gam(C=0.3))),
        ("C06", _genome(F_TEXT, params=gam(C=3.0))),
        ("C07", _genome(F_TEXT, params=gam(n_knots=6))),
        ("C08", _genome(F_ASSIGNER_TEXT, params=gam(C=0.1))),
        ("C09", _genome(F_ASSIGNER_TEXT, params=gam(C=0.3))),
        ("C10", _genome(F_ASSIGNER_TEXT, params=gam(n_knots=6))),
        (
            "C11",
            _genome(
                BASE_FEATURES,
                model="hgb",
                params={
                    "max_depth": 3,
                    "learning_rate": 0.05,
                    "max_iter": 150,
                    "min_samples_leaf": 40,
                    "l2_regularization": 5.0,
                },
            ),
        ),
        (
            "C12",
            _genome(
                BASE_FEATURES,
                model="extra_trees",
                params={
                    "n_estimators": 200,
                    "max_depth": 10,
                    "min_samples_leaf": 5,
                    "max_features": "sqrt",
                },
            ),
        ),
        ("C13", _genome(BASE_FEATURES, model="logistic", params={"C": 0.3})),
        ("C14", _genome(F_C14, params=gam(C=0.3), cap=100)),
        ("C15", _genome(F_C14, params=gam(C=0.3), cap=50)),
        ("C16", _genome(F_C14, params=gam(C=0.3), cap=None)),
        ("C17", _genome(F_C14_TEMPORAL, params=gam(C=0.3), cap=100)),
        ("C18", _genome(F_C14_TEMPORAL, params=gam(C=0.3), cap=75)),
        ("C19", _genome(["signals", "assigner"], params=gam(C=0.1), cap=50)),
        (
            "C20",
            _genome(
                ["signals", "assigner", "assigner24", "text_tfidf", "temporal"],
                params=gam(C=0.1),
            ),
        ),
        ("C21", _genome(F_TEXT, cap=50)),
        ("C22", _genome(F_TEXT, flag_quota=None)),
        ("C23", _genome(F_ASSIGNER, params=gam(C=0.1))),
        ("C24", _genome(F_ASSIGNER, params=gam(C=0.3))),
    ]
    expected = [f"C{i:02d}" for i in range(25)]
    got = [cid for cid, _ in cands]
    assert got == expected, f"candidate list drifted: {got}"
    for cid, genome in cands:
        assert genome["postprocess"]["seed_average"] == 1, cid
        assert genome["postprocess"]["month_allocation"] == "none", cid
    return cands


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _run_task(task):
    cid, genome, seed = task
    started = time.time()
    try:
        result = evaluate_genome(deepcopy(genome), folds=FOLDS, seed=seed, bootstrap=0)
    except Exception as exc:  # noqa: BLE001 - a failed candidate is data
        result = {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "per_fold": {},
        }
    result["candidate_id"] = cid
    result["seed"] = seed
    result["seconds"] = round(time.time() - started, 2)
    return result


def _collect(task_results, candidate_ids) -> dict[str, list[dict]]:
    runs: dict[str, list[dict]] = {cid: [] for cid in candidate_ids}
    for res in task_results:
        runs.setdefault(res["candidate_id"], []).append(res)
    for cid in runs:
        runs[cid].sort(key=lambda r: r["seed"])
    return runs


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def _fold_rows(runs: list[dict]) -> list[dict]:
    rows = []
    for run in runs:
        if run.get("status") != "ok":
            continue
        for fold, m in run.get("per_fold", {}).items():
            if all(k in m for k in ("top243", "top500", "avg_precision")):
                rows.append({"seed": run["seed"], "fold": fold, "metrics": m})
    return rows


def _aggregate(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    return {key: float(_mean(row["metrics"][key] for row in rows)) for key in METRIC_KEYS}


def build_record(cid, genome, runs, baseline_agg):
    rows = _fold_rows(runs)
    complete = len(rows) == len(SEEDS) * len(FOLDS)
    n_ok_runs = sum(1 for r in runs if r.get("status") == "ok")
    if complete:
        status = "ok"
    elif n_ok_runs:
        status = "partial"
    else:
        status = "error"

    agg = _aggregate(rows)
    per_seed = {}
    for seed in SEEDS:
        seed_rows = [r for r in rows if r["seed"] == seed]
        per_seed[str(seed)] = _aggregate(seed_rows)
    per_fold = {}
    for fold in FOLDS:
        fold_rows = [r for r in rows if r["fold"] == fold]
        per_fold[fold] = _aggregate(fold_rows)

    deltas = None
    deltas_per_seed = {}
    if agg is not None and baseline_agg is not None:
        deltas = {
            "top243": agg["top243"] - baseline_agg["top243"],
            "top500": agg["top500"] - baseline_agg["top500"],
            "avg_precision": agg["avg_precision"] - baseline_agg["avg_precision"],
        }
        for seed in SEEDS:
            seed_agg = per_seed.get(str(seed))
            if seed_agg is not None:
                deltas_per_seed[str(seed)] = {
                    "top243": seed_agg["top243"] - baseline_agg["top243"],
                    "top500": seed_agg["top500"] - baseline_agg["top500"],
                    "avg_precision": seed_agg["avg_precision"] - baseline_agg["avg_precision"],
                }

    errors = [
        {"seed": r.get("seed"), "error": r.get("error", "missing fold metrics")}
        for r in runs
        if r.get("status") != "ok"
    ]
    expected_runs = len(SEEDS)
    if len(runs) < expected_runs:
        errors.append(
            {
                "seed": None,
                "error": f"not_run: only {len(runs)}/{expected_runs} seed runs collected",
            }
        )

    return {
        "candidate_id": cid,
        "genome": genome,
        "complexity": complexity(genome),
        "status": status,
        "n_ok_runs": n_ok_runs,
        "n_fold_rows": len(rows),
        "aggregate": agg,
        "per_seed": per_seed,
        "per_fold": per_fold,
        "deltas": deltas,
        "deltas_per_seed": deltas_per_seed,
        "gate_equiv": {
            "top243_ge_6": bool(deltas and deltas["top243"] >= 6.0),
            "top500_ge_6": bool(deltas and deltas["top500"] >= 6.0),
            "ap_ge_0": bool(deltas and deltas["avg_precision"] >= 0.0),
            "all": bool(
                deltas
                and deltas["top243"] >= 6.0
                and deltas["top500"] >= 6.0
                and deltas["avg_precision"] >= 0.0
            ),
        },
        "seconds": round(sum(r.get("seconds", 0.0) for r in runs), 2),
        "runs": runs,
        "errors": errors,
    }


def rank_records(records: list[dict]) -> list[dict]:
    ranked = [r for r in records if r["status"] == "ok" and r["deltas"] is not None]
    for r in ranked:
        d = r["deltas"]
        r["rank_key"] = min(d["top243"], d["top500"])
    ranked.sort(
        key=lambda r: (
            -min(r["deltas"]["top243"], r["deltas"]["top500"]),
            -r["deltas"]["avg_precision"],
            r["complexity"],
            r["candidate_id"],
        )
    )
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    return ranked


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:  # noqa: BLE001
            pass
    return obj


def _fmt(value, digits=1):
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _fmt_signed(value, digits=2):
    if value is None:
        return "n/a"
    return f"{value:+.{digits}f}"


def write_csv(path: Path, baseline: dict, records: list[dict]) -> None:
    fields = [
        "candidate_id",
        "status",
        "rank",
        "model",
        "features",
        "params",
        "cap",
        "flag_quota",
        "month_allocation",
        "seed_average",
        "complexity",
        "mean_top243",
        "delta_top243",
        "mean_top500",
        "delta_top500",
        "mean_avg_precision",
        "delta_avg_precision",
        "delta_vs_champion_top243",
        "delta_vs_champion_top500",
        "delta_vs_champion_ap",
        "dominates_champion",
        "mean_top161",
        "mean_auc",
        "mean_median_rank",
        "mean_work50",
        "delta_top243_seed0",
        "delta_top243_seed42",
        "delta_top500_seed0",
        "delta_top500_seed42",
        "gate_equiv_top243",
        "gate_equiv_top500",
        "gate_equiv_ap",
        "gate_equiv_all",
        "seconds",
        "errors",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for rec in [baseline] + records:
            agg = rec["aggregate"] or {}
            d = rec["deltas"] or {}
            ds = rec["deltas_per_seed"]
            dch = rec.get("deltas_vs_champion") or {}
            g = rec["gate_equiv"]
            post = rec["genome"]["postprocess"]
            writer.writerow(
                {
                    "candidate_id": rec["candidate_id"],
                    "status": rec["status"],
                    "rank": rec.get("rank", ""),
                    "model": rec["genome"]["model"],
                    "features": " ".join(rec["genome"]["features"]),
                    "params": json.dumps(rec["genome"]["params"], sort_keys=True),
                    "cap": post.get("cap"),
                    "flag_quota": post.get("flag_quota"),
                    "month_allocation": post.get("month_allocation"),
                    "seed_average": post.get("seed_average"),
                    "complexity": rec["complexity"],
                    "mean_top243": _fmt(agg.get("top243")),
                    "delta_top243": _fmt(d.get("top243"), 2),
                    "mean_top500": _fmt(agg.get("top500")),
                    "delta_top500": _fmt(d.get("top500"), 2),
                    "mean_avg_precision": _fmt(agg.get("avg_precision"), 4),
                    "delta_avg_precision": _fmt(d.get("avg_precision"), 4),
                    "delta_vs_champion_top243": _fmt(dch.get("top243"), 2),
                    "delta_vs_champion_top500": _fmt(dch.get("top500"), 2),
                    "delta_vs_champion_ap": _fmt(dch.get("avg_precision"), 4),
                    "dominates_champion": rec.get("dominates_champion", ""),
                    "mean_top161": _fmt(agg.get("top161")),
                    "mean_auc": _fmt(agg.get("auc"), 4),
                    "mean_median_rank": _fmt(agg.get("median_rank")),
                    "mean_work50": _fmt(agg.get("work50")),
                    "delta_top243_seed0": _fmt(ds.get("0", {}).get("top243"), 2),
                    "delta_top243_seed42": _fmt(ds.get("42", {}).get("top243"), 2),
                    "delta_top500_seed0": _fmt(ds.get("0", {}).get("top500"), 2),
                    "delta_top500_seed42": _fmt(ds.get("42", {}).get("top500"), 2),
                    "gate_equiv_top243": g["top243_ge_6"],
                    "gate_equiv_top500": g["top500_ge_6"],
                    "gate_equiv_ap": g["ap_ge_0"],
                    "gate_equiv_all": g["all"],
                    "seconds": rec["seconds"],
                    "errors": " | ".join(str(e["error"]) for e in rec["errors"]),
                }
            )


def write_report(path: Path, meta, baseline, records, ranked, elapsed, timed_out, feature_availability) -> None:
    lines: list[str] = []
    add = lines.append
    add("# Repair experiment around the AutoRank champion — exploratory report")
    add("")
    add(f"- Generated: {meta['generated_utc']}")
    add(f"- Git commit: `{meta['git_commit']}`")
    add(f"- Protocol: `experiments/repair_champion/PROTOCOL.md` (pre-registered)")
    add(f"- Candidates: {len(records)} (`C00`–`C24`; see PROTOCOL.md section 10 on the brief's \"24\" label)")
    add(f"- Folds: primary + rolling; seeds: 0, 42; bootstrap: 0; `seed_average=1`")
    add(f"- Wall clock: {elapsed:.1f}s" + (" (STOPPED AT DEADLINE — PARTIAL)" if timed_out else ""))
    add("")
    add("> **This is exploratory selection on the same 2025 folds that produced the")
    add("> champion, not a valid five-seed gate. Nothing here is eligible. Any")
    add("> challenger requires the official gate before adoption.**")
    add("")

    base_agg = baseline["aggregate"] or {}
    add("## Baseline (C1, seed_average=1)")
    add("")
    add("| top243 | top500 | top161 | AP | AUC | median rank |")
    add("|---:|---:|---:|---:|---:|---:|")
    add(
        "| {t243} | {t500} | {t161} | {ap} | {auc} | {mr} |".format(
            t243=_fmt(base_agg.get("top243")),
            t500=_fmt(base_agg.get("top500")),
            t161=_fmt(base_agg.get("top161")),
            ap=_fmt(base_agg.get("avg_precision"), 4),
            auc=_fmt(base_agg.get("auc"), 4),
            mr=_fmt(base_agg.get("median_rank")),
        )
    )
    add("")
    if baseline["status"] != "ok":
        add(f"**WARNING: baseline was not complete ({baseline['status']}); deltas are unreliable.**")
        add("")

    completed = sum(1 for r in records if r["status"] == "ok")
    add("## Coverage")
    add("")
    add(f"- Candidates completed (all 4 seed x fold runs): **{completed}/{len(records)}**")
    add(f"- Ranked candidates: **{len(ranked)}**")
    if timed_out:
        add("- The run hit the internal deadline; unfinished candidates are reported as partial/not_run.")
    add("")

    missing_by_cache = {
        key: info["dropped"] for key, info in feature_availability.items() if info["dropped"]
    }
    if missing_by_cache:
        add("## Data caveat: inconsistent cached fold schemas (important)")
        add("")
        add("The four local fold caches do not all contain the `assigner24` columns")
        add("(`asg24_rate`, `asg24_kev`, `asg24_kev_log`). `evaluate_genome` silently drops")
        add("requested feature groups that are missing from a fold, and records them in")
        add("`features_dropped`. In this run:")
        add("")
        for key, groups in missing_by_cache.items():
            add(f"- `{key}`: requested but missing -> `{', '.join(groups)}`")
        add("")
        add("Consequences:")
        add("")
        add("- 24 of the 25 candidates request `assigner24`; C19 is the only one that does not.")
        add("  Those 24 effectively ran with a different feature set in 3 of their 4 fold runs.")
        add("- In particular, the nominal champion **C00 was evaluated without `assigner24`**")
        add("  in 3 of 4 runs. This screen therefore does not reproduce the full champion, and")
        add("  its absolute numbers should not be equated with the quoted champion/gate numbers.")
        add("- The pre-registered ranking is reported exactly as executed on these fixed caches.")
        add("  No cache was modified (that is outside this experiment's write scope). The official")
        add("  gate must run on consistently built folds, and a fresh-cache rerun is needed before")
        add("  drawing conclusions about the true champion or about absolute gains.")
        add("")
    else:
        add("## Data caveat: cached fold schemas")
        add("")
        add("All requested feature groups were available in all four cached folds.")
        add("")

    add("## Full table (ranked, then unranked)")
    add("")
    add(
        "| Rank | ID | Status | top243 | Δ243 | top500 | Δ500 | AP | ΔAP | minΔ | complexity | notes |"
    )
    add("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    ordered = ranked + [r for r in records if r not in ranked]
    for rec in ordered:
        agg = rec["aggregate"] or {}
        d = rec["deltas"] or {}
        note = ""
        if rec["errors"]:
            note = "error: " + "; ".join(str(e["error"]) for e in rec["errors"])[:80]
        add(
            "| {rank} | {cid} | {status} | {t243} | {d243} | {t500} | {d500} | {ap} | {dap} | {mind} | {cx} | {note} |".format(
                rank=rec.get("rank", "–"),
                cid=rec["candidate_id"],
                status=rec["status"],
                t243=_fmt(agg.get("top243")),
                d243=_fmt(d.get("top243"), 2),
                t500=_fmt(agg.get("top500")),
                d500=_fmt(d.get("top500"), 2),
                ap=_fmt(agg.get("avg_precision"), 4),
                dap=_fmt(d.get("avg_precision"), 4),
                mind=_fmt(min(d["top243"], d["top500"]) if d else None, 2),
                cx=_fmt(rec["complexity"], 4),
                note=note,
            )
        )
    add("")

    add("## Top 5 by the pre-registered rule")
    add("")
    add("Rule: maximize `min(Δtop243, Δtop500)`; tie-break higher `ΔAP`; then lower complexity; then candidate ID.")
    add("")
    if not ranked:
        add("No candidate completed, so there is no ranking.")
    for rec in ranked[:5]:
        d = rec["deltas"]
        add(
            f"{rec['rank']}. **{rec['candidate_id']}** — top243 {_fmt(rec['aggregate']['top243'])} "
            f"(Δ {_fmt(d['top243'], 2)}), top500 {_fmt(rec['aggregate']['top500'])} "
            f"(Δ {_fmt(d['top500'], 2)}), AP {_fmt(rec['aggregate']['avg_precision'], 4)} "
            f"(Δ {_fmt(d['avg_precision'], 4)}), complexity {rec['complexity']}"
        )
    add("")

    add("## Pre-registered winner")
    add("")
    if ranked:
        winner = ranked[0]
        d = winner["deltas"]
        g = winner["gate_equiv"]
        add(
            f"**{winner['candidate_id']}** (exploratory winner under the fixed rule): "
            f"mean top243 {_fmt(winner['aggregate']['top243'])} (Δ {_fmt(d['top243'], 2)} vs C1), "
            f"mean top500 {_fmt(winner['aggregate']['top500'])} (Δ {_fmt(d['top500'], 2)}), "
            f"mean AP {_fmt(winner['aggregate']['avg_precision'], 4)} (Δ {_fmt(d['avg_precision'], 4)})."
        )
        add("")
        add(
            "This candidate is **not eligible** and **requires the official five-seed gate**. "
            f"Its advantage may be inflated because {len(records)} candidates were compared on the same folds."
        )
        if not g["all"]:
            add("")
            add(
                "It also does **not** reach the gate-equivalent diagnostic thresholds "
                f"(top243 ≥ 6: {g['top243_ge_6']}; top500 ≥ 6: {g['top500_ge_6']}; AP ≥ 0: {g['ap_ge_0']})."
            )
    else:
        add("No winner can be declared: no candidate completed.")
    add("")

    add("## Winner vs the champion (reporting only, not the ranking rule)")
    add("")
    champ = next((r for r in records if r["candidate_id"] == "C00"), None)
    if champ is not None and champ["aggregate"] is not None and ranked:
        add(
            f"Champion C00: top243 {_fmt(champ['aggregate']['top243'])}, "
            f"top500 {_fmt(champ['aggregate']['top500'])}, "
            f"AP {_fmt(champ['aggregate']['avg_precision'], 4)}."
        )
        add("")
        add("| ID | Δtop243 vs C00 | Δtop500 vs C00 | ΔAP vs C00 | dominates C00 |")
        add("|---|---:|---:|---:|---|")
        for rec in ranked[:5]:
            dch = rec.get("deltas_vs_champion") or {}
            add(
                f"| {rec['candidate_id']} | {_fmt_signed(dch.get('top243'))} | "
                f"{_fmt_signed(dch.get('top500'))} | {_fmt_signed(dch.get('avg_precision'), 4)} | "
                f"{rec['dominates_champion']} |"
            )
        add("")
        dominating = [
            r["candidate_id"]
            for r in records
            if r.get("dominates_champion") and r["candidate_id"] != "C00"
        ]
        add(
            "Candidates that lose nothing on either cut versus the champion: "
            + (", ".join(dominating) if dominating else "none")
            + "."
        )
        add("")
        add("Under a strict repair-the-champion lens, the rule winner may still be worse than the")
        add("champion on top-243. The official gate compares against C1, so the pre-registered rule")
        add("above remains the decision rule for this experiment; this table is diagnostic only.")
    else:
        add("Champion-relative comparison unavailable.")
    add("")

    passing = [r for r in records if r["gate_equiv"]["all"]]
    add("## Gate-equivalent diagnostic")
    add("")
    add("Thresholds (mean over seeds 0+42, vs C1): Δtop243 ≥ 6, Δtop500 ≥ 6, ΔAP ≥ 0.")
    add("")
    if passing:
        add("Candidates passing all three diagnostic thresholds (still **not eligible**):")
        add("")
        for rec in passing:
            add(f"- {rec['candidate_id']}: see table")
    else:
        add("**No candidate passes all three diagnostic thresholds.**")
    add("")
    add("This diagnostic is not the gate. The official gate uses five seed averages and a paired")
    add("bootstrap CI lower bound > 0 for top-243 on both folds; only that gate can make a challenger eligible.")
    add("")
    add("This screen uses `seed_average=1` by protocol, whereas the official gate averages five")
    add("fold seeds. Seed averaging changes absolute gains, so the screen is fixed but is not a")
    add("guarantee that a candidate would fail (or pass) the official five-seed gate.")
    add("")

    clean = []
    for rec in records:
        dropped_any = any(
            m.get("features_dropped")
            for run in rec["runs"]
            for m in run.get("per_fold", {}).values()
        )
        if not dropped_any:
            clean.append(rec)
    if clean:
        add(
            "Candidates whose requested features were fully available in every fold run: "
            + ", ".join(r["candidate_id"] for r in clean)
            + "."
        )
        add("")
        for rec in clean:
            d = rec["deltas"] or {}
            add(
                f"- {rec['candidate_id']}: Δtop243 {_fmt_signed(d.get('top243'))}, "
                f"Δtop500 {_fmt_signed(d.get('top500'))}, "
                f"ΔAP {_fmt_signed(d.get('avg_precision'), 4)} vs C1."
            )
        add("")
        clean_passing = [
            r["candidate_id"] for r in clean if r["gate_equiv"]["all"]
        ]
        if clean_passing:
            add(
                "Clean candidates passing the diagnostic (still not eligible): "
                + ", ".join(clean_passing)
                + "."
            )
        else:
            add("None of the clean candidates reaches the +6/+6 diagnostic.")
        add("")
    add("## Failures and incomplete runs")
    add("")
    failed = [r for r in records if r["status"] != "ok"]
    if failed:
        for rec in failed:
            add(f"- **{rec['candidate_id']}** ({rec['status']}):")
            for err in rec["errors"]:
                add(f"  - seed {err['seed']}: {err['error']}")
    else:
        add(f"None: all {len(records)} candidates completed both seeds and both folds.")
    add("")

    add("## Caveats (read before quoting any number)")
    add("")
    add("- **Exploratory selection on the same 2025 folds**, not a valid five-seed gate. The")
    add(f"  winner is optimistically biased by multiple comparisons across {len(records)} candidates.")
    add("- **Not eligible.** Only the official five-seed gate can make a challenger eligible;")
    add("  this experiment cannot.")
    add("- Fold test sets have roughly 52 positives; one top-500 hit is about 2 points of that")
    add("  metric, so differences of a few hits are within noise. No bootstrap CIs were computed")
    add("  here (`bootstrap=0`).")
    add("- No 2026 labels were used. Nothing here is a 2026 accuracy claim.")
    add("- All numbers are unverified until independently audited and registered in")
    add("  `results/claims*.json`; do not publish them before that.")
    add("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--deadline-seconds", type=float, default=1740.0)
    parser.add_argument("--bootstrap", type=int, default=0)
    args = parser.parse_args()

    workers = max(1, min(int(args.workers), MAX_WORKERS))
    if args.bootstrap != 0:
        raise SystemExit("PROTOCOL fixes bootstrap=0; refusing to change it")

    started = time.time()
    candidates = frozen_candidates()
    candidate_ids = [cid for cid, _ in candidates]

    baseline_genome = deepcopy(C1_GENOME)
    baseline_genome["postprocess"]["seed_average"] = 1

    tasks = [("C1", baseline_genome, seed) for seed in SEEDS]
    tasks += [(cid, genome, seed) for cid, genome in candidates for seed in SEEDS]

    print(
        f"[repair] {len(candidates)} candidates + C1, {len(SEEDS)} seeds x {len(FOLDS)} folds; "
        f"workers={workers}, deadline={args.deadline_seconds:.0f}s",
        flush=True,
    )

    raw: list[dict] = []
    timed_out = False
    ctx = mp.get_context("fork")
    pool = ctx.Pool(processes=workers)
    try:
        it = pool.imap_unordered(_run_task, tasks, chunksize=1)
        while len(raw) < len(tasks):
            remaining = args.deadline_seconds - (time.time() - started)
            if remaining <= 0:
                raise TimeoutError
            try:
                res = it.next(timeout=remaining)
            except TimeoutError:
                timed_out = True
                break
            raw.append(res)
            print(
                f"[repair] {len(raw)}/{len(tasks)} runs done: "
                f"{res['candidate_id']} seed={res['seed']} {res['status']} "
                f"({res.get('seconds', 0):.1f}s)",
                flush=True,
            )
    finally:
        pool.terminate()
        pool.join()

    elapsed = time.time() - started
    run_map = _collect(raw, ["C1"] + candidate_ids)

    baseline_record = build_record("C1", baseline_genome, run_map["C1"], None)
    baseline_agg = baseline_record["aggregate"]
    records = [
        build_record(cid, genome, run_map[cid], baseline_agg) for cid, genome in candidates
    ]
    # Champion-relative view: reporting only, not part of the pre-registered rule.
    champion = next((r for r in records if r["candidate_id"] == "C00"), None)
    for rec in records:
        if champion is None or champion["aggregate"] is None or rec["aggregate"] is None:
            rec["deltas_vs_champion"] = None
            rec["dominates_champion"] = False
        else:
            dch = {
                key: rec["aggregate"][key] - champion["aggregate"][key]
                for key in ("top243", "top500", "avg_precision")
            }
            rec["deltas_vs_champion"] = dch
            rec["dominates_champion"] = dch["top243"] >= 0.0 and dch["top500"] >= 0.0
    # Which requested feature groups each cached fold actually provides.
    availability: dict[str, dict[str, set]] = {}
    for rec in [baseline_record] + records:
        requested = set(rec["genome"]["features"])
        for run in rec["runs"]:
            if run.get("status") != "ok":
                continue
            for fold, m in run["per_fold"].items():
                key = f"{fold}_seed{run['seed']}"
                slot = availability.setdefault(key, {"requested": set(), "dropped": set()})
                slot["requested"] |= requested
                slot["dropped"] |= set(m.get("features_dropped", []))
    feature_availability = {
        key: {"requested": sorted(val["requested"]), "dropped": sorted(val["dropped"])}
        for key, val in sorted(availability.items())
    }
    ranked = rank_records(records)
    top5 = [
        {
            "rank": r["rank"],
            "candidate_id": r["candidate_id"],
            "aggregate": r["aggregate"],
            "deltas": r["deltas"],
            "complexity": r["complexity"],
        }
        for r in ranked[:5]
    ]

    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:  # noqa: BLE001
        git_commit = "unknown"

    meta = {
        "experiment": "repair_champion",
        "protocol": "experiments/repair_champion/PROTOCOL.md",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": git_commit,
        "command": " ".join([sys.executable] + sys.argv),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "folds": list(FOLDS),
        "seeds": list(SEEDS),
        "bootstrap": 0,
        "seed_average_forced": 1,
        "workers": workers,
        "deadline_seconds": args.deadline_seconds,
        "wall_clock_seconds": round(elapsed, 1),
        "timed_out": timed_out,
        "tasks_total": len(tasks),
        "tasks_completed": len(raw),
        "candidates_total": len(candidates),
        "candidates_completed": sum(1 for r in records if r["status"] == "ok"),
        "candidate_id_range": "C00-C24",
        "candidate_count_note": (
            "The brief labels the fixed list '24' but enumerates C00..C24 = 25 genomes; "
            "all 25 enumerated IDs were evaluated and none was added or removed."
        ),
    }

    results = {
        "meta": meta,
        "ranking_rule": (
            "maximize min(delta_top243, delta_top500); tie-break higher delta_avg_precision; "
            "then lower complexity; then lexicographic candidate id"
        ),
        "gate_equiv_rule": "mean delta_top243 >= 6 and mean delta_top500 >= 6 and mean delta_ap >= 0 vs C1",
        "baseline": baseline_record,
        "candidates": records,
        "ranked": [r["candidate_id"] for r in ranked],
        "top5": top5,
        "feature_availability": feature_availability,
        "failures": [
            {"candidate_id": r["candidate_id"], "status": r["status"], "errors": r["errors"]}
            for r in records
            if r["status"] != "ok"
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "results.json").open("w", encoding="utf-8") as fh:
        json.dump(_jsonable(results), fh, indent=2)
    write_csv(OUT_DIR / "candidates.csv", baseline_record, records)
    write_report(
        OUT_DIR / "report.md",
        meta,
        baseline_record,
        records,
        ranked,
        elapsed,
        timed_out,
        feature_availability,
    )

    print(
        f"[repair] done: {meta['candidates_completed']}/{len(candidates)} candidates complete, "
        f"{len(ranked)} ranked, {elapsed:.1f}s, timed_out={timed_out}",
        flush=True,
    )
    if ranked:
        print("[repair] top 5:", flush=True)
        for r in ranked[:5]:
            d = r["deltas"]
            print(
                f"  {r['rank']}. {r['candidate_id']} "
                f"top243 {r['aggregate']['top243']:.1f} (d {d['top243']:+.2f}) "
                f"top500 {r['aggregate']['top500']:.1f} (d {d['top500']:+.2f}) "
                f"AP {r['aggregate']['avg_precision']:.4f} (d {d['avg_precision']:+.4f})",
                flush=True,
            )
        passing = [r["candidate_id"] for r in records if r["gate_equiv"]["all"]]
        print(f"[repair] gate-equivalent (diagnostic only): {passing or 'none'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
