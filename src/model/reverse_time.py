"""Reverse-time check (LOG.md "PRE-REGISTRATION, reverse-time check"), applied literally.

Run: .venv/bin/python src/model/reverse_time.py
Writes results/reverse_time.json, results/reverse_time.meta.json, results/claims_model_reverse.json (rev.*).

Train C1 on 2025-01..2025-09 snapshots (pool labels), test on 2024-01..2024-12 snapshots (pool labels).
NOT time-safe: the training rows and their assigner features postdate the test rows and their labels.
Does not change the final model or top500.csv.
"""
import json

import joblib
import numpy as np
import pandas as pd

import metrics as M
import reproduce_first_pass as R
from candidates import CANDIDATES, N_BOOT, BOOT_SEED, SEEDS, TOO_GOOD_AUC, Fold, over_seeds, report
from pool import ROOT, kev_with_assigner, load_kev, load_pool, load_vulns
from sidecar import write_meta

SCRIPT_REL = "src/model/reverse_time.py"
OUT_REL = "results/reverse_time.json"
CLAIMS = ROOT / "results" / "claims_model_reverse.json"
LABEL = ("Reverse-time check: trained on the future of the test data. NOT time-safe and NOT an accuracy estimate; "
         "measures signal stability and optimism from training on the future.")
TRAIN, TEST = ("2025-01", "2025-09"), ("2024-01", "2024-12")
BASELINES = ["exploit_then_epss", "epss", "cvss3", "assigner_only"]
KEYS = ["top500_cve_id", "top500_best", "top500_worst", "top250_cve_id", "auc", "avg_precision",
        "median_rank_cve_id", "work50_cve_id"]
UNITS = {"auc": "fraction", "avg_precision": "fraction"}


def leakage_indicator(te):
    """2024 test positives whose assigner has >= 1 KEV addition dated in 2025, and whose own KEV date is in 2025."""
    v = load_vulns(cols=["cve_id", "published", "assigner"])
    kv = kev_with_assigner(load_kev(), v)
    asg25 = set(kv[kv.date_added.dt.year == 2025].assigner)
    pos = te[te.y == 1]
    return {"test_positives": int(len(pos)),
            "positives_whose_assigner_has_kev_additions_dated_2025": int(pos.assigner.isin(asg25).sum()),
            "positives_own_kev_date_in_2025": int((pos.date_added.dt.year == 2025).sum()),
            "positives_own_kev_date_before_2025_10": int((pos.date_added < "2025-10-01").sum()),
            "note": ("Train rows (2025 snapshots) carry asg_rate/asg_kev counted from KEV rows before their month, "
                     "which include the 2024 test positives' own KEV additions: future knowledge of the test labels "
                     "enters through the assigner features (and through the train labels' assigner mix).")}


def main():
    pool = load_pool()
    tr = pool[(pool.ym >= TRAIN[0]) & (pool.ym <= TRAIN[1])].copy()
    te = pool[(pool.ym >= TEST[0]) & (pool.ym <= TEST[1])].copy()
    overlap = len(set(tr.cve_id) & set(te.cve_id))
    fold = Fold("reverse", tr, te, tr.y.to_numpy())
    kind, cols = CANDIDATES["C1"]
    c1, scores = fold.run(kind, cols)
    base = R.baselines(te)
    res_base = {n: over_seeds([report(fold.y_te, base[n], fold.ids)]) for n in BASELINES}

    vecs = {"C1": scores[0], **{n: base[n] for n in BASELINES}}
    cis = joblib.Parallel(n_jobs=-1)(joblib.delayed(M.bootstrap_ci)(fold.y_te, vecs[n], fold.ids, N_BOOT, BOOT_SEED)
                                     for n in vecs)
    ci = {n: {k: c[k] for k in ("top500_cve_id", "top500_expected", "auc")} for n, c in zip(vecs, cis)}

    fwd = json.loads((ROOT / "results" / "model_candidates.json").read_text())
    fwd_f1 = {"source": "results/model_candidates.json (copied, not recomputed)", "fold": fwd["folds"]["fold1"],
              "C1": {"median": fwd["candidates"]["fold1"]["C1"]["median"], "min": fwd["candidates"]["fold1"]["C1"]["min"],
                     "max": fwd["candidates"]["fold1"]["C1"]["max"], "ci95_seed0": fwd["candidates"]["fold1"]["C1"]["ci95_seed0"]},
              "baselines": {n: {"median": e["median"], "ci95_seed0": e["ci95_seed0"]} for n, e in fwd["baselines"]["fold1"].items()},
              "missing": [n for n in BASELINES if n not in fwd["baselines"]["fold1"]]}

    too_good = {n: a for n, a in [("C1_max", c1["max"]["auc"])] + [(n, e["median"]["auc"]) for n, e in res_base.items()]
                if a > TOO_GOOD_AUC}
    res = {"label": LABEL, "spec": "LOG.md 'PRE-REGISTRATION, reverse-time check'",
           "train_months": "..".join(TRAIN), "test_months": "..".join(TEST),
           "train_rows": len(tr), "train_positives": int(tr.y.sum()), "test_rows": len(te), "test_positives": int(te.y.sum()),
           "train_test_cve_overlap": overlap,
           "labels": "pool labels for both sides: KEV added in (snapshot end, min(snapshot end + 365 days, 2025-12-31)]",
           "reverse": {"C1": {k: c1[k] for k in ("median", "min", "max", "per_seed")},
                       "baselines": {n: e["median"] for n, e in res_base.items()},
                       "ci95_seed0": ci},
           "forward_fold1": fwd_f1, "future_knowledge_indicator": leakage_indicator(te),
           "too_good_auc_gt_0.93": too_good,
           "notes": {"seed_sets": "C1 seed set s: text OOF folds seed s, HGB random_state s; TF-IDF and text model fitted on train rows only",
                     "ci95_seed0": f"percentile bootstrap, {N_BOOT} resamples, seed {BOOT_SEED}; C1 uses seed set 0; same resamples for every method",
                     "ties": "top500_cve_id / top250_cve_id break ties by cve_id; top500_best/worst is the tie-aware range"}}
    (ROOT / OUT_REL).write_text(json.dumps(res, indent=2, default=lambda x: x.item()) + "\n")
    write_meta(OUT_REL, SCRIPT_REL, {"label": LABEL})

    tag = "reverse-time (not time-safe)"
    where = f"{tag}: trained 2025-01..09 snapshots, tested 2024-01..12 snapshots"
    claims = {}

    def add(key, text, value, unit):
        claims["rev." + key] = {"text": text, "value": int(value) if unit == "count" else float(value), "unit": unit,
                                "source_script": SCRIPT_REL, "output_file": OUT_REL, "status": "unverified", "verified_by": None}

    for k in ("train_rows", "train_positives", "test_rows", "test_positives"):
        add(k, f"{where}: {k.replace('_', ' ')}", res[k], "count")
    for k in KEYS:
        u = UNITS.get(k, "count")
        add(f"C1.{k}.median", f"{where}, C1: {k}, median over seed sets 0-4", c1["median"][k], u)
        if k in ("top500_cve_id", "auc"):
            add(f"C1.{k}.min", f"{where}, C1: {k}, lowest of seed sets 0-4", c1["min"][k], u)
            add(f"C1.{k}.max", f"{where}, C1: {k}, highest of seed sets 0-4", c1["max"][k], u)
        for n, e in res_base.items():
            add(f"{n}.{k}", f"{where}, baseline {n}: {k} (deterministic)", e["median"][k], u)
    for n, c in ci.items():
        for k, v in c.items():
            u = UNITS.get(k, "count")
            lab = "seed set 0" if n == "C1" else "deterministic baseline"
            add(f"{n}.ci95_lo.{k}", f"{where}, {n}: bootstrap 95% CI lower bound, {k} ({lab})", v[0], u)
            add(f"{n}.ci95_hi.{k}", f"{where}, {n}: bootstrap 95% CI upper bound, {k} ({lab})", v[1], u)
    ind = res["future_knowledge_indicator"]
    for k in ("positives_whose_assigner_has_kev_additions_dated_2025", "positives_own_kev_date_in_2025"):
        add(f"indicator.{k}", f"{where}: 2024 test {k.replace('_', ' ')}", ind[k], "count")
    assert all(tag in c["text"] for c in claims.values())
    CLAIMS.write_text(json.dumps(dict(sorted(claims.items())), indent=2) + "\n")
    print(json.dumps({k: res[k] for k in ("train_rows", "train_positives", "test_rows", "test_positives",
                                          "train_test_cve_overlap", "too_good_auc_gt_0.93")}))
    print(f"wrote {OUT_REL} and {len(claims)} rev claims")


if __name__ == "__main__":
    main()
