"""Rerun the first-pass baselines and models on the 2025 backtest, then measure suspected problems.

Run: .venv/bin/python src/model/reproduce_first_pass.py
Writes results/first_pass_repro.json, results/first_pass_repro.meta.json, merges results/claims_model.json.

`primary` is the faithful port of model2.py, including its pandas sort. The lettered sections are
separate sensitivity measurements: they do not feed back into `primary` or pick a new model.
"""
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import pyarrow
import scipy
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, train_test_split

import metrics as M
from pool import (ASSIGNER_FEATURES, BEST_FEATURES, ROOT, SIGNAL_FEATURES, data_dir, load_kev, load_pool,
                  label_limit, make_labels, structured_features)

N_BOOT = 2000
BOOT_SEED = 0
RESULTS = ROOT / "results"
OUT = RESULTS / "first_pass_repro.json"
OUT_REL = "results/first_pass_repro.json"
SCRIPT_REL = "src/model/reproduce_first_pass.py"
BEST = "hgb_signals_assigner_text"

# First-pass table: docs/kb/02_findings_first_pass.md. Compared against, never fed into anything.
# (top500, top1000, auc, avg precision, median rank of positives)
CLAIMED = {
    "cvss3": (6, 9, .732, .0064, 7884),
    "epss": (8, 13, .707, .0309, 3376),
    "exploit_then_epss": (19, 22, .768, .0471, 2496),
    "assigner_only": (13, 15, .746, .0109, 6075),
    "hgb_signals": (20, 22, .726, .0368, 2652),
    "hgb_signals_struct": (19, 20, .803, .0627, 3551),
    "hgb_signals_assigner": (16, 24, .884, .0727, 1190),
    "hgb_signals_struct_assigner": (14, 24, .879, .1032, 1634),
    "text_only": (9, 14, .814, .0100, 3379),
    "hgb_all_text": (21, 25, .883, .1142, 1103),
    BEST: (25, 28, .886, .1050, 829),
    "leaky_ncpe": (27, 29, .913, .1315, 421),
}
LABELS = {
    "cvss3": "CVSS3", "epss": "EPSS", "exploit_then_epss": "exploit flag then EPSS",
    "assigner_only": "assigner KEV-rate only", "hgb_signals": "HGB signals",
    "hgb_signals_struct": "HGB signals+structured", "hgb_signals_assigner": "HGB signals+assigner",
    "hgb_signals_struct_assigner": "HGB signals+structured+assigner", "text_only": "text-only TF-IDF LR",
    "hgb_all_text": "HGB all + text score", BEST: "HGB signals+assigner+text score",
    "leaky_ncpe": "LEAKY + n_affected_cpes (comparison only)",
}


def baselines(df):
    return {"cvss3": df.cvss3.to_numpy(), "epss": df.epss_f.to_numpy(),
            "exploit_then_epss": (df.anyx * 10 + df.epss_f.clip(0)).to_numpy(),
            "assigner_only": df.asg_rate.to_numpy()}


def first_pass_eval(y, s):
    """model2.py's ev(): pandas default (unstable) sort, so tied rows land in arbitrary order."""
    o = pd.DataFrame({"y": y}).assign(s=s).sort_values("s", ascending=False)
    ranks = np.where(o.y.to_numpy() == 1)[0] + 1
    return {"top500": int(o.y.to_numpy()[:500].sum()), "top1000": int(o.y.to_numpy()[:1000].sum()),
            "auc": M.auc(y, s), "avg_precision": M.avg_precision(y, s),
            "median_rank": int(np.median(ranks))}


def evaluate(y, s, ids):
    """Faithful numbers, deterministic numbers and the tie picture for one score vector."""
    y = np.asarray(y)
    return {"first_pass_order": first_pass_eval(y, s), "deterministic": M.summary(y, s, ids),
            "ties_top500": M.topk_tie_aware(y, s, 500), "ties_top250": M.topk_tie_aware(y, s, 250),
            "ties_top1000": M.topk_tie_aware(y, s, 1000)}


def add_ci(results, y, scores, ids):
    """Bootstrap every method in parallel, same resamples for each."""
    names = list(scores)
    cis = joblib.Parallel(n_jobs=-1)(joblib.delayed(M.bootstrap_ci)(np.asarray(y), scores[n], ids, N_BOOT, BOOT_SEED)
                                     for n in names)
    for n, ci in zip(names, cis):
        results[n]["ci95"] = ci


def fit_lr(X, y):
    return LogisticRegression(C=2, class_weight="balanced", max_iter=500).fit(X, y)


def text_vectors(tr, te):
    tf = TfidfVectorizer(ngram_range=(1, 2), min_df=8, max_features=30000, sublinear_tf=True, stop_words="english")
    return tf.fit_transform(tr.description.fillna("")), tf.transform(te.description.fillna(""))


def text_test_score(Xtr, y, Xte):
    return fit_lr(Xtr, y).predict_proba(Xte)[:, 1]


def text_oof(Xtr, y, fold_seed=0):
    """Out-of-fold text score for the training rows, so the stacker never sees a row's own label."""
    y = np.asarray(y)
    folds = list(StratifiedKFold(5, shuffle=True, random_state=fold_seed).split(Xtr, y))
    parts = joblib.Parallel(n_jobs=5)(joblib.delayed(lambda a, c: fit_lr(Xtr[a], y[a]).predict_proba(Xtr[c])[:, 1])(a, c)
                                      for a, c in folds)
    oof = np.zeros(len(y))
    for (_, c), p in zip(folds, parts):
        oof[c] = p
    return oof


def hgb_mean(Xtr, y, Xte, seeds=(0, 1, 2), **kw):
    """Mean test score over seeds and the iterations each seed really used."""
    preds, iters = [], []
    for seed in seeds:
        m = HGB(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40, l2_regularization=5.0,
                random_state=seed, **kw).fit(Xtr, y)
        preds.append(m.predict_proba(Xte)[:, 1])
        iters.append(int(m.n_iter_))
    return np.mean(preds, axis=0), iters


def stack(df, cols, text):
    """Feature frame with the text score attached (and the leaky column renamed as in model2.py)."""
    return df.assign(txt=text, ncpe=df.n_affected_cpes)[cols]


def id_codes(df):
    """cve_id as integers in lexical order: same tie-break as sorting the strings, faster."""
    return pd.factorize(df.cve_id, sort=True)[0]


def run_primary(tr, te, ids, Xtr, Xte, oof, st):
    struct = structured_features(tr)
    base, asg = SIGNAL_FEATURES, ASSIGNER_FEATURES
    specs = {"hgb_signals": base, "hgb_signals_struct": base + struct, "hgb_signals_assigner": base + asg,
             "hgb_signals_struct_assigner": base + struct + asg}
    stacked = {"hgb_all_text": base + struct + asg + ["txt"], BEST: BEST_FEATURES,
               "leaky_ncpe": base + struct + asg + ["txt", "ncpe"]}
    scores, iters = baselines(te), {}
    for name, cols in specs.items():
        scores[name], iters[name] = hgb_mean(tr[cols], tr.y, te[cols])
    scores["text_only"] = st
    for name, cols in stacked.items():
        scores[name], iters[name] = hgb_mean(stack(tr, cols, oof), tr.y, stack(te, cols, st))
    results = {n: evaluate(te.y, s, ids) for n, s in scores.items()}
    add_ci(results, te.y, scores, ids)
    return results, scores, iters, {**specs, **stacked}


def section_a(primary):
    out = {"how_ranks_are_made_deterministic": (
        "Ranks sort by score descending, then cve_id ascending (lexical), so they do not depend on row order or machine. "
        "The expected value (random order inside the tied group) is reported beside it and is the tie-neutral number."),
        "first_pass_order_note": (
            "first_pass_top500 and the table's 'reproduced' column use the first pass's own order: pandas sort_values with "
            "the default unstable quicksort on pool row order, descending. Its tie order is arbitrary and may depend on the "
            "numpy build and CPU."),
        "methods": {}}
    for name, r in primary.items():
        t = r["ties_top500"]
        out["methods"][name] = {
            "first_pass_top500": r["first_pass_order"]["top500"], "cve_id_top500": r["deterministic"]["top500_cve_id"],
            "best_top500": t["best"], "expected_top500": t["expected"], "worst_top500": t["worst"],
            "tied_group_size_at_rank_500": t["tied_group_size"], "slots_in_tied_group": t["slots_in_tied_group"],
            "positives_in_tied_group": t["positives_in_tied_group"]}
    return out


def section_b(tr, te, ids, Xtr, Xte):
    y = make_labels(tr.date_added, tr.snap_end, cap="2024-12-31")
    oof, st = text_oof(Xtr, y), text_test_score(Xtr, y, Xte)
    s, iters = hgb_mean(stack(tr, BEST_FEATURES, oof), y, stack(te, BEST_FEATURES, st))
    r = evaluate(te.y, s, ids)
    add_ci({"x": r}, te.y, {"x": s}, ids)
    return {"model": BEST, "train_label_cap": "2024-12-31", "train_rows": len(tr), "train_positives_restricted": int(y.sum()),
            "train_positives_first_pass": int(tr.y.sum()), "train_positives_lost": int(tr.y.sum() - y.sum()),
            "hgb_n_iter_per_seed": iters, **r}


def section_c(tr, te, ids, specs, oof, st, primary, iters_auto):
    # HGB stratifies its internal validation split on y; the size is the same for any seed up to rounding.
    val = {seed: int(train_test_split(tr.y.to_numpy(), test_size=0.1, stratify=tr.y.to_numpy(), random_state=seed)[1].sum())
           for seed in range(3)}
    out = {"validation_fraction": 0.1, "train_rows": len(tr), "train_positives": int(tr.y.sum()),
           "positives_in_a_stratified_10pct_validation_split_per_seed": val,
           "note": "max_iter=150 is the documented setting; n_iter_ is what each fit actually used under early_stopping='auto'.",
           "methods": {}}
    for name, cols in specs.items():
        Xa, Xb = stack(tr, cols, oof), stack(te, cols, st)
        s, iters = hgb_mean(Xa, tr.y, Xb, early_stopping=False)
        r = evaluate(te.y, s, ids)
        out["methods"][name] = {"n_iter_per_seed_auto": iters_auto[name], "n_iter_per_seed_no_early_stop": iters,
                                "auto": primary[name]["first_pass_order"], "no_early_stop": r["first_pass_order"],
                                "no_early_stop_deterministic": r["deterministic"], "no_early_stop_ties_top500": r["ties_top500"]}
    return out


def section_d(tr, te, ids, Xtr, st, oof0):
    def run(oof, seeds):
        s, iters = hgb_mean(stack(tr, BEST_FEATURES, oof), tr.y, stack(te, BEST_FEATURES, st), seeds=seeds)
        d = M.summary(te.y.to_numpy(), s, ids)
        return {"top500_first_pass_order": first_pass_eval(te.y.to_numpy(), s)["top500"], "top500_cve_id": d["top500_cve_id"],
                "top500_expected": d["top500_expected"], "top250_cve_id": d["top250_cve_id"], "auc": d["auc"],
                "avg_precision": d["avg_precision"], "median_rank_cve_id": d["median_rank_cve_id"], "hgb_seeds": list(seeds),
                "hgb_n_iter": iters}

    hgb_seeds = [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(10)]
    oofs = [oof0] + [text_oof(Xtr, tr.y, fold_seed=i) for i in range(1, 10)]
    runs = {"both_vary": [run(oofs[i], hgb_seeds[i]) for i in range(10)],
            "hgb_only": [run(oof0, hgb_seeds[i]) for i in range(10)],
            "fold_only": [run(oofs[i], hgb_seeds[0]) for i in range(10)]}
    spread = lambda rows, key: {"min": min(r[key] for r in rows), "median": float(np.median([r[key] for r in rows])),
                                "max": max(r[key] for r in rows), "std": float(np.std([r[key] for r in rows], ddof=1)),
                                "values": [r[key] for r in rows]}
    return {"model": BEST, "seed_scheme": ("Run i uses text folds seed i (fold_only / both_vary) and HGB seeds 3i, 3i+1, 3i+2 "
                                           "(hgb_only / both_vary), each a mean of 3 HGB fits. Run 0 equals the primary run."),
            "runs": runs,
            "spread": {mode: {k: spread(rows, k) for k in ("top500_first_pass_order", "top500_cve_id", "auc", "avg_precision",
                                                           "median_rank_cve_id")} for mode, rows in runs.items()}}


def section_e(pool):
    tr = pool[(pool.ym >= "2024-07") & (pool.ym <= "2025-03")].copy()
    te = pool[(pool.ym >= "2025-04") & (pool.ym <= "2025-09")].copy()
    ids = id_codes(te)
    Xtr, Xte = text_vectors(tr, te)
    scores = baselines(te)

    def best(y):
        oof, st = text_oof(Xtr, y), text_test_score(Xtr, y, Xte)
        return hgb_mean(stack(tr, BEST_FEATURES, oof), y, stack(te, BEST_FEATURES, st))

    y_cap = make_labels(tr.date_added, tr.snap_end, cap="2025-03-31")
    scores[BEST], iters = best(tr.y)
    scores[BEST + "__train_labels_to_2025_03_31"], iters_cap = best(y_cap)
    res = {n: evaluate(te.y, s, ids) for n, s in scores.items()}
    add_ci(res, te.y, scores, ids)
    return {"train_months": "2024-07..2025-03", "test_months": "2025-04..2025-09", "train_rows": len(tr),
            "train_positives": int(tr.y.sum()), "train_positives_labels_to_2025_03_31": int(y_cap.sum()),
            "test_rows": len(te), "test_positives": int(te.y.sum()), "hgb_n_iter_per_seed": iters,
            "hgb_n_iter_per_seed_labels_capped": iters_cap, "methods": res}


def section_f(pool):
    te = pool[pool.ym >= "2025-01"]
    rows = []
    for ym, g in te.groupby("ym"):
        end = g.snap_end.iloc[0]
        lim = label_limit(pd.Series([end])).iloc[0]
        rows.append({"snapshot_month": ym, "rows": len(g), "positives": int(g.y.sum()),
                     "label_window_days": int((lim - end).days), "label_window_end": str(lim.date()),
                     "epss_missing_share": float(g.epss.isna().mean())})
    epss_missing = pool.groupby("ym").epss.apply(lambda s: float(s.isna().mean())).to_dict()
    return {"note": "All windows end at the 2025-12-31 cap in the test pool, so later months have less time to reach KEV.",
            "by_snapshot_month": rows, "epss_missing_share_all_pool_months": epss_missing,
            "kev_rows_outside_label_window_counted_negative": int((pool.date_added.notna() & (pool.y == 0)).sum())}


EXPLOIT_WORDING = (r"exploited in the wild|actively exploited|known to be exploited|has been exploited|"
                   r"may have been exploited|is being exploited|CISA|KEV")


def section_h(pool):
    """Descriptions are today's NVD text, not as-of text. Count exploitation wording by label as a leak probe."""
    hit = pool.description.fillna("").str.contains(EXPLOIT_WORDING, case=False, regex=True)
    split = np.where(pool.ym < "2025-01", "train", "test")
    out = {"pattern": EXPLOIT_WORDING, "note": ("Cannot tell from the data whether the wording was there at publication "
                                                "or added later. Measurement only; nothing is removed.")}
    for name in ("train", "test"):
        m = split == name
        out[name] = {"positives": int(pool.y[m].sum()), "positives_with_wording": int((hit & (pool.y == 1))[m].sum()),
                     "negatives": int((pool.y[m] == 0).sum()), "negatives_with_wording": int((hit & (pool.y == 0))[m].sum())}
    out["positive_ids_with_wording"] = sorted(pool.cve_id[hit & (pool.y == 1)])
    return out


def section_g(primary):
    return {name: {"point": r["deterministic"], "ci95": r["ci95"]} for name, r in primary.items()} | {
        "_note": (f"Percentile CI over {N_BOOT} row resamples, seed {BOOT_SEED}, the same resamples for every method. "
                  "_cve_id ties by id, _expected and _mid are tie-neutral; they match unless a method has ties at the cutoff.")}


def final_model_context():
    """Does the final 2026 model have B's overlap? Labels end where the scoreboard starts."""
    k = load_kev()
    sb = pd.read_csv(data_dir() / "scoreboard_2026.csv", usecols=["published", "snapshot_month"], parse_dates=["published"])
    kev_end, sb_start = k.date_added.max(), sb.published.min()
    return {"kev_last_date_added": str(kev_end.date()), "scoreboard_first_published": str(sb_start.date()),
            "scoreboard_first_snapshot_month": sb.snapshot_month.min(),
            "final_model_labels_overlap_scoreboard": bool(kev_end >= sb_start)}


def print_table(primary):
    print(f"\n{'method':44s} {'top500':>12s} {'top1000':>12s} {'AUC':>13s} {'AP':>15s} {'median rank':>13s}  (claimed/reproduced)")
    diffs = []
    for name, c in CLAIMED.items():
        r = primary[name]["first_pass_order"]
        cells = [f"{c[0]}/{r['top500']}", f"{c[1]}/{r['top1000']}", f"{c[2]:.3f}/{r['auc']:.3f}",
                 f"{c[3]:.4f}/{r['avg_precision']:.4f}", f"{c[4]}/{r['median_rank']}"]
        match = all(x.split("/")[0] == x.split("/")[1] for x in cells)
        print(f"{LABELS[name]:44s} {cells[0]:>12s} {cells[1]:>12s} {cells[2]:>13s} {cells[3]:>15s} {cells[4]:>13s}  {'same' if match else 'DIFF'}")
        diffs.append({"method": name, "label": LABELS[name], "claimed": dict(zip(("top500", "top1000", "auc", "avg_precision", "median_rank"), c)),
                      "reproduced": r, "same_at_printed_precision": match})
    return diffs


def claims_from(res):
    """Every ledger entry comes from the result dict: no number is typed here."""
    c = {}

    def add(key, text, value, unit):
        c[key] = {"text": text, "value": value, "unit": unit, "source_script": SCRIPT_REL, "output_file": OUT_REL,
                  "status": "unverified", "verified_by": None}

    p = res["pool"]
    for k, v in p.items():
        if isinstance(v, int):
            add(f"pool.{k}", f"Backtest pool: {k.replace('_', ' ')}", v, "count")
    for name, r in res["primary"].items():
        where = f"{LABELS[name]}, 2025-01..09 test pool"
        fp, d, t, ci = r["first_pass_order"], r["deterministic"], r["ties_top500"], r["ci95"]
        pre = f"primary.{name}"
        add(f"{pre}.top500_first_pass_order", f"{where}: top-500 hits, first-pass unstable sort order", fp["top500"], "count")
        add(f"{pre}.top1000_first_pass_order", f"{where}: top-1000 hits, first-pass unstable sort order", fp["top1000"], "count")
        add(f"{pre}.median_rank_first_pass_order", f"{where}: median rank of positives, first-pass sort order", fp["median_rank"], "count")
        add(f"{pre}.auc", f"{where}: AUC", fp["auc"], "fraction")
        add(f"{pre}.avg_precision", f"{where}: average precision", fp["avg_precision"], "fraction")
        add(f"{pre}.top500_cve_id", f"{where}: top-500 hits, ties by cve_id", d["top500_cve_id"], "count")
        add(f"{pre}.top250_cve_id", f"{where}: top-250 hits, ties by cve_id", d["top250_cve_id"], "count")
        add(f"{pre}.top500_best", f"{where}: top-500 hits, best order of tied rows", t["best"], "count")
        add(f"{pre}.top500_expected", f"{where}: top-500 hits, expected over tied rows", t["expected"], "count")
        add(f"{pre}.top500_worst", f"{where}: top-500 hits, worst order of tied rows", t["worst"], "count")
        add(f"{pre}.top500_tied_group", f"{where}: size of the tied group spanning rank 500", t["tied_group_size"], "count")
        add(f"{pre}.work50_cve_id", f"{where}: CVEs to review to catch 50% of positives, ties by cve_id", d["work50_cve_id"], "count")
        for key, unit in (("top500_expected", "count"), ("top250_expected", "count"), ("auc", "fraction"),
                          ("avg_precision", "fraction"), ("median_rank_mid", "count"), ("work50_mid", "count")):
            add(f"{pre}.ci95_lo.{key}", f"{where}: 95% CI lower bound, {key}", ci[key][0], unit)
            add(f"{pre}.ci95_hi.{key}", f"{where}: 95% CI upper bound, {key}", ci[key][1], unit)

    b = res["B_train_labels_restricted"]
    add("b.train_positives", "Train positives with labels restricted to KEV additions on or before 2024-12-31", b["train_positives_restricted"], "count")
    add("b.top500_first_pass_order", "Best model with restricted train labels: top-500 hits, first-pass sort order", b["first_pass_order"]["top500"], "count")
    add("b.top500_cve_id", "Best model with restricted train labels: top-500 hits, ties by cve_id", b["deterministic"]["top500_cve_id"], "count")
    add("b.auc", "Best model with restricted train labels: AUC", b["first_pass_order"]["auc"], "fraction")
    add("b.avg_precision", "Best model with restricted train labels: average precision", b["first_pass_order"]["avg_precision"], "fraction")
    add("b.median_rank", "Best model with restricted train labels: median rank, first-pass sort order", b["first_pass_order"]["median_rank"], "count")

    cm = res["C_early_stopping"]["methods"][BEST]
    for i, n in enumerate(cm["n_iter_per_seed_auto"]):
        add(f"c.best.n_iter_seed{i}", f"Best model: boosting iterations actually used by seed {i} under early_stopping='auto'", n, "count")
    add("c.best.top500_no_early_stop", "Best model, early_stopping=False: top-500 hits, first-pass sort order", cm["no_early_stop"]["top500"], "count")
    add("c.best.auc_no_early_stop", "Best model, early_stopping=False: AUC", cm["no_early_stop"]["auc"], "fraction")
    add("c.best.avg_precision_no_early_stop", "Best model, early_stopping=False: average precision", cm["no_early_stop"]["avg_precision"], "fraction")

    s = res["D_seed_noise"]["spread"]["both_vary"]["top500_cve_id"]
    add("d.top500_min", "Best model, 10 HGB+fold seed sets: lowest top-500 hits, ties by cve_id", s["min"], "count")
    add("d.top500_max", "Best model, 10 HGB+fold seed sets: highest top-500 hits, ties by cve_id", s["max"], "count")

    e = res["E_second_fold"]
    add("e.train_positives", "Second fold train positives (2024-07..2025-03 snapshots)", e["train_positives"], "count")
    add("e.train_positives_capped", "Second fold train positives with labels to 2025-03-31", e["train_positives_labels_to_2025_03_31"], "count")
    add("e.test_rows", "Second fold test rows (2025-04..2025-09 snapshots)", e["test_rows"], "count")
    add("e.test_positives", "Second fold test positives", e["test_positives"], "count")
    for name, r in e["methods"].items():
        add(f"e.{name}.top500_cve_id", f"Second fold, {name}: top-500 hits, ties by cve_id", r["deterministic"]["top500_cve_id"], "count")
        add(f"e.{name}.top500_expected", f"Second fold, {name}: top-500 hits, expected over tied rows", r["deterministic"]["top500_expected"], "count")
        add(f"e.{name}.auc", f"Second fold, {name}: AUC", r["deterministic"]["auc"], "fraction")
        add(f"e.{name}.avg_precision", f"Second fold, {name}: average precision", r["deterministic"]["avg_precision"], "fraction")

    h = res["H_description_exploit_wording"]
    for name in ("train", "test"):
        add(f"h.{name}.positives_with_wording", f"{name} positives whose description has exploitation wording", h[name]["positives_with_wording"], "count")
        add(f"h.{name}.negatives_with_wording", f"{name} negatives whose description has exploitation wording", h[name]["negatives_with_wording"], "count")
    for row in res["F_censoring"]["by_snapshot_month"]:
        add(f"f.{row['snapshot_month']}.positives", f"Test positives from snapshot month {row['snapshot_month']}", row["positives"], "count")
        add(f"f.{row['snapshot_month']}.window_days", f"Label window length in days, snapshot month {row['snapshot_month']}", row["label_window_days"], "count")
    return c


def merge_claims(new):
    """Keep an entry's audit status only if its value is unchanged; a changed value goes back to unverified."""
    path = RESULTS / "claims_model.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    for key, claim in new.items():
        prev = old.get(key)
        if prev and isinstance(prev.get("value"), (int, float)) and math.isclose(prev["value"], claim["value"], rel_tol=1e-9, abs_tol=1e-12):
            claim["status"], claim["verified_by"] = prev.get("status", "unverified"), prev.get("verified_by")
    old.update(new)
    path.write_text(json.dumps(old, indent=2) + "\n")
    return len(new)


def write_meta():
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    meta = {"script": SCRIPT_REL, "git_commit": head, "git_dirty": dirty,
            "date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / "src" / "model").glob("*.py"))},
            "python": platform.python_version(), "machine": platform.machine(),
            "libraries": {"pandas": pd.__version__, "numpy": np.__version__, "scikit-learn": sklearn.__version__,
                          "scipy": scipy.__version__, "pyarrow": pyarrow.__version__, "joblib": joblib.__version__}}
    (RESULTS / "first_pass_repro.meta.json").write_text(json.dumps(meta, indent=2) + "\n")


def main():
    t0 = time.time()
    tick = lambda msg: print(f"[{time.time() - t0:5.0f}s] {msg}", flush=True)
    pool = load_pool()
    tr, te = pool[pool.ym < "2025-01"].copy(), pool[pool.ym >= "2025-01"].copy()
    ids = id_codes(te)
    res = {"pool": {"pool_rows": len(pool), "pool_positives": int(pool.y.sum()), "train_rows": len(tr),
                    "train_positives": int(tr.y.sum()), "test_rows": len(te), "test_positives": int(te.y.sum())}}

    Xtr, Xte = text_vectors(tr, te)
    st, oof = text_test_score(Xtr, tr.y, Xte), text_oof(Xtr, tr.y)
    tick("text model fitted")
    primary, scores, iters, specs = run_primary(tr, te, ids, Xtr, Xte, oof, st)
    res["primary"] = primary
    tick("primary rows and bootstrap done")
    res["claimed_vs_reproduced"] = print_table(primary)
    res["A_ties"] = section_a(primary)
    res["B_train_labels_restricted"] = section_b(tr, te, ids, Xtr, Xte)
    tick("B done")
    res["C_early_stopping"] = section_c(tr, te, ids, specs, oof, st, primary, iters)
    tick("C done")
    res["D_seed_noise"] = section_d(tr, te, ids, Xtr, st, oof)
    tick("D done")
    res["E_second_fold"] = section_e(pool)
    tick("E done")
    res["F_censoring"] = section_f(pool)
    res["G_bootstrap"] = section_g(primary)
    res["H_description_exploit_wording"] = section_h(pool)
    res["context_final_2026_model"] = final_model_context()

    RESULTS.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=lambda x: x.item()) + "\n")
    n = merge_claims(claims_from(res))
    write_meta()
    tick(f"wrote {OUT}, its meta file and {n} claims")


if __name__ == "__main__":
    sys.exit(main())
