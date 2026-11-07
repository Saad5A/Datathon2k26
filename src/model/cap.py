"""Per-assigner cap on the top 500 (LOG.md "PRE-REGISTRATION, Granite text and per-assigner cap"), applied literally.

Run: .venv/bin/python src/model/cap.py
Writes results/assigner_cap.json (+ .meta.json), merges p5.cap.* into results/claims_model.json.

Cap k: walk down the scores (ties by the tie-break key), skip a CVE once its assigner already has k slots, stop at 500.
k in {none, 100, 50} on both Phase 3 folds with C1, seed medians. Rule: highest mean expected top-500 hits over the
two folds; anything within 1 hit of the best counts as a tie and the strictest such cap wins.
The 2026 part is a PREVIEW of assigner shares only: it writes no scores and no top500 file.
"""
import json
import time

import joblib
import numpy as np
import pandas as pd

import candidates as C
import metrics as M
import reproduce_first_pass as R
from pool import FLAGS, ROOT, assigner_history, data_dir, kev_with_assigner, load_kev, load_pool, load_vulns

SCRIPT_REL = "src/model/cap.py"
OUT_REL = "results/assigner_cap.json"
CAPS = {"none": None, "100": 100, "50": 50}
STRICTNESS = ["50", "100", "none"]  # strictest first
TIE_HITS = 1.0
N_TIE_DRAWS = 200
TOP = 500
MODEL = "C1"


def capped_top(scores, groups, k, tiebreak, n=TOP):
    """Row indices of the capped top n: score descending, ties by `tiebreak` ascending, at most k rows per group."""
    order = np.lexsort((tiebreak, -np.asarray(scores, dtype=float)))
    if k is not None:
        g = groups[order]
        order = order[pd.Series(g).groupby(g).cumcount().to_numpy() < k]
    return order[:n]


def shares(groups_named, idx):
    return (pd.Series(groups_named[idx]).value_counts() / len(idx)).to_dict()


def evaluate(y, s, ids, assigner, k):
    """Hits with ties by cve_id, and the expected hits over random orders of tied scores (Monte Carlo, seed 0)."""
    groups = pd.factorize(assigner)[0]
    by_id = capped_top(s, groups, k, ids)
    if len(np.unique(s)) == len(s):
        expected = float(y[by_id].sum())  # no ties: every tie order gives the same list
    else:
        rng = np.random.default_rng(0)
        expected = float(np.mean([y[capped_top(s, groups, k, rng.permutation(len(s)))].sum() for _ in range(N_TIE_DRAWS)]))
    sh = shares(assigner, by_id)
    top = max(sh, key=sh.get)
    return {"top500_cve_id": int(y[by_id].sum()), "top500_expected": expected, "largest_assigner": top,
            "largest_assigner_share": float(sh[top]), "n_assigners": len(sh)}


def self_check():
    s = np.array([.9, .8, .7, .6, .5, .5])
    g = np.array([0, 0, 0, 1, 1, 2])
    ids = np.arange(6)
    assert capped_top(s, g, None, ids, n=4).tolist() == [0, 1, 2, 3]
    assert capped_top(s, g, 2, ids, n=4).tolist() == [0, 1, 3, 4]  # third row of group 0 skipped
    assert capped_top(s, g, 1, ids, n=4).tolist() == [0, 3, 5]  # fewer than n when every group is full
    assert capped_top(s, g, 1, ids[::-1].copy(), n=3).tolist() == [0, 3, 5]
    # Uncapped Monte Carlo expectation agrees with the exact tie-aware formula.
    y = np.array([0, 0, 0, 0, 1, 0])
    e = evaluate(y, s, ids, np.array(list("aaabbc")), None)
    assert e["top500_cve_id"] == 1
    yb = np.array([0, 0, 0, 0, 0, 1])
    rng = np.random.default_rng(0)
    mc = np.mean([yb[capped_top(s, g, None, rng.permutation(6), n=5)].sum() for _ in range(2000)])
    assert abs(mc - M.topk_tie_aware(yb, s, 5)["expected"]) < 0.05


def score_2026(pool):
    """C1 fitted on every labelled pool row (pool labels: KEV to 2025-12-31), scored on scoreboard_2026.csv."""
    sb = pd.read_csv(data_dir() / "scoreboard_2026.csv", dtype={"cve_id": str})
    v = load_vulns(cols=["cve_id", "published", "assigner", "description"])
    sb = sb.merge(v[["cve_id", "assigner", "description"]], on="cve_id", how="left", validate="one_to_one")
    assert sb.assigner.notna().all() and len(sb) == 72670
    for f in FLAGS:
        sb[f] = sb[f].fillna(0)
    sb["anyx"], sb["nx"], sb["epss_f"] = sb[FLAGS].max(axis=1), sb[FLAGS].sum(axis=1), sb.epss.fillna(-1)
    kv = kev_with_assigner(load_kev(), v)
    hist = {}
    for m in sorted(sb.snapshot_month.unique()):
        start = pd.Timestamp(m + "-01")
        hist[m] = assigner_history(kv[kv.date_added < start], v[v.published < start], m)
    sb["asg_rate"] = [hist[m][0].get(a, 0) for m, a in zip(sb.snapshot_month, sb.assigner)]
    sb["asg_kev"] = [hist[m][1].get(a, 0) for m, a in zip(sb.snapshot_month, sb.assigner)]
    kind, cols = C.CANDIDATES[MODEL]
    Xtr, Xte = R.text_vectors(C.masked(pool), C.masked(sb))
    st = R.text_test_score(Xtr, pool.y, Xte)
    out = []
    for seed in C.SEEDS:
        oof = R.text_oof(Xtr, pool.y, fold_seed=seed)
        out.append(C.fit_score(kind, C.frame(pool, cols, oof, kind), pool.y, C.frame(sb, cols, st, kind), seed))
    return sb, out


def claims_from(res):
    c = {}

    def add(key, text, value, unit):
        c["p5.cap." + key] = {"text": text, "value": value, "unit": unit, "source_script": SCRIPT_REL, "output_file": OUT_REL,
                              "status": "unverified", "verified_by": None}

    for f, fr in res["folds"].items():
        where = f"Assigner cap, {MODEL}, Phase 3 {f} (test {fr['test_months']})"
        for k, e in fr["caps"].items():
            for key, unit in (("top500_expected", "count"), ("top500_cve_id", "count"), ("largest_assigner_share", "fraction")):
                add(f"{f}.k{k}.{key}", f"{where}, cap k={k}: {key}, median over seed sets 0-4", e["seed_median"][key], unit)
            add(f"{f}.k{k}.top500_expected.min", f"{where}, cap k={k}: top500_expected, lowest of seed sets 0-4", e["seed_min"]["top500_expected"], "count")
            add(f"{f}.k{k}.top500_expected.max", f"{where}, cap k={k}: top500_expected, highest of seed sets 0-4", e["seed_max"]["top500_expected"], "count")
    for k, v in res["selection"]["mean_expected_top500_over_folds"].items():
        add(f"selection.k{k}.mean_expected_top500", f"Assigner cap k={k}: mean over the two folds of the seed-median expected top-500 hits", v, "count")
    add("selection.chosen_k", "Assigner cap chosen by the pre-registered rule (0 = no cap)",
        CAPS[res["selection"]["chosen"]] or 0, "count")
    for k, e in res["preview_2026"]["caps"].items():
        add(f"preview2026.k{k}.largest_assigner_share",
            f"PREVIEW 2026 top 500 ({MODEL} refit on 2024-01..2025-09, not the final file), cap k={k}: largest assigner share, median over seed sets 0-4",
            e["largest_assigner_share_seed_median"], "fraction")
    return c


def main():
    t0 = time.time()
    tick = lambda msg: print(f"[{time.time() - t0:5.0f}s] {msg}", flush=True)
    self_check()
    pool = load_pool()
    kev = load_kev()
    kind, cols = C.CANDIDATES[MODEL]
    phase3 = json.loads((ROOT / C.OUT_REL).read_text())
    res = {"rule": ("k in {none, 100, 50}; highest mean over the two folds of the seed-median expected top-500 hits; "
                    "within 1 hit of the best, choose the strictest cap"), "model": MODEL, "folds": {}}
    for f, spec in C.FOLDS.items():
        tr, te, y_tr = C.fold_data(pool, kev, spec)
        fold = C.Fold(f, tr, te, y_tr)
        _, scores = fold.run(kind, cols)
        # Consistency with Phase 3: the uncapped list is the same list.
        assert [M.hits_at_k(fold.y_te, M.ranks_by_id(s, fold.ids), TOP) for s in scores] == \
            [r["top500_cve_id"] for r in phase3["candidates"][f][MODEL]["per_seed"]]
        asg = te.assigner.fillna("(missing)").to_numpy()
        per = joblib.Parallel(n_jobs=-1)(joblib.delayed(evaluate)(fold.y_te, s, fold.ids, asg, k)
                                         for k in CAPS.values() for s in scores)
        caps = {}
        for i, k in enumerate(CAPS):
            rows = per[i * len(scores):(i + 1) * len(scores)]
            num = [key for key in rows[0] if key != "largest_assigner"]
            caps[k] = {"seed_median": {key: float(np.median([r[key] for r in rows])) for key in num},
                       "seed_min": {key: min(r[key] for r in rows) for key in num},
                       "seed_max": {key: max(r[key] for r in rows) for key in num}, "per_seed": rows}
        res["folds"][f] = {"test_months": "..".join(spec["test"]), "test_positives": int(fold.y_te.sum()), "caps": caps}
        tick(f"{f}: " + ", ".join(f"k={k} exp {caps[k]['seed_median']['top500_expected']}" for k in CAPS))

    mean_exp = {k: float(np.mean([res["folds"][f]["caps"][k]["seed_median"]["top500_expected"] for f in C.FOLDS])) for k in CAPS}
    best = max(mean_exp.values())
    eligible = [k for k in STRICTNESS if mean_exp[k] >= best - TIE_HITS]
    res["selection"] = {"mean_expected_top500_over_folds": mean_exp, "best": best, "eligible_within_1_hit": eligible,
                        "chosen": eligible[0]}
    tick(f"chosen k={eligible[0]} {mean_exp}")

    sb, scores = score_2026(pool)
    asg = sb.assigner.to_numpy()
    groups, ids = pd.factorize(asg)[0], R.id_codes(sb)
    prev = {}
    for k, kv in CAPS.items():
        per = [shares(asg, capped_top(s, groups, kv, ids)) for s in scores]
        largest = [max(p.values()) for p in per]
        top5 = sorted(per[0].items(), key=lambda x: -x[1])[:5]
        prev[k] = {"largest_assigner_share_seed_median": float(np.median(largest)), "largest_assigner_share_per_seed": largest,
                   "largest_assigner_per_seed": [max(p, key=p.get) for p in per], "n_assigners_per_seed": [len(p) for p in per],
                   "top5_assigner_shares_seed_set_0": dict(top5)}
    res["preview_2026"] = {"note": (f"{MODEL} refitted on all labelled pool rows 2024-01..2025-09 (labels: KEV to 2025-12-31), "
                                    "scored on scoreboard_2026.csv (signals from that file, assigner history as of each snapshot_month "
                                    "from KEV rows dated before it, description masked). Shares only; no scores or top-500 file written. "
                                    "Ties by cve_id. Not an accuracy claim."),
                           "rows_scored": len(sb), "train_rows": len(pool), "train_positives": int(pool.y.sum()), "caps": prev}
    tick("2026 preview done")
    (ROOT / OUT_REL).write_text(json.dumps(res, indent=2, default=lambda x: x.item()) + "\n")
    C.write_meta(script=SCRIPT_REL, out="assigner_cap.meta.json")
    tick(f"wrote {OUT_REL} and {C.merge_claims(claims_from(res), prefix='p5.cap.')} p5.cap claims")


if __name__ == "__main__":
    main()
