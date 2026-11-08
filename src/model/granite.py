"""Granite text score vs TF-IDF (LOG.md "PRE-REGISTRATION, Granite text and per-assigner cap"), applied literally.

Run: .venv/bin/python src/model/granite.py
     (test only: --emb <synthetic.parquet> --out-dir <scratch dir> --subset 0.05; never point a test at results/)
Input data_cache/granite_embeddings.parquet (cve_id, vector float32[768], from cloud/embed_granite.py on the masked
descriptions). Writes results/granite_comparison.json (+ .meta.json) and results/claims_model_granite.json (p6.granite.*).

G1 = C1 with the text score from an L2 logistic regression on the Granite vectors instead of TF-IDF; G2 = C1 with both
text scores. The text LR is the harness one (C=2, balanced) with 5-fold OOF on train, fit on train only. Same folds,
labels, HGB settings, 5 seed sets as Phase 3; C1 is refitted here as the reference. Rule: take the higher mean AUC of
G1/G2 (G1 on an exact tie); adopt it if that mean AUC over the two folds >= C1's - 0.01, else keep TF-IDF (C1).
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

import candidates as C
import metrics as M
import reproduce_first_pass as R
from pool import ROOT, data_dir, load_kev, load_pool

SCRIPT_REL = "src/model/granite.py"
EMB = ROOT / "data_cache" / "granite_embeddings.parquet"
DIM = 768
MARGIN = 0.01
PREFIX = "p6.granite."


class Embeddings:
    def __init__(self, path):
        path = Path(path)
        if not path.exists():
            sys.exit(f"Granite embeddings not found: {path} (produce it with cloud/embed_granite.py, see cloud/README.md)")
        df = pd.read_parquet(path)
        if list(df.columns[:2]) != ["cve_id", "vector"]:
            sys.exit(f"{path}: expected columns cve_id, vector; got {list(df.columns)}")
        if not df.cve_id.is_unique:
            sys.exit(f"{path}: duplicate cve_id rows")
        self.mat = np.stack(df.vector.to_numpy()).astype(np.float32)
        if self.mat.shape[1] != DIM or not np.isfinite(self.mat).all():
            sys.exit(f"{path}: vectors must be finite float32[{DIM}], got shape {self.mat.shape}")
        self.index = pd.Index(df.cve_id)
        self.path = str(path)

    def require(self, ids, what):
        missing = pd.Index(ids).difference(self.index)
        if len(missing):
            sys.exit(f"{self.path}: {len(missing)} {what} ids have no vector (e.g. {list(missing[:3])}); coverage must be complete")

    def rows(self, ids):
        i = self.index.get_indexer(ids)
        assert (i >= 0).all()
        return self.mat[i]


def select(mean_auc):
    best = "G1" if mean_auc["G1"] >= mean_auc["G2"] else "G2"
    return best, (best if mean_auc[best] >= mean_auc["C1"] - MARGIN else "C1")


def self_check():
    assert select({"C1": .87, "G1": .865, "G2": .80}) == ("G1", "G1")  # within 0.01: adopted
    assert select({"C1": .87, "G1": .80, "G2": .859}) == ("G2", "C1")  # more than 0.01 below: keep TF-IDF
    assert select({"C1": .87, "G1": .86, "G2": .86}) == ("G1", "G1")  # exact tie G1/G2 -> G1; exactly C1 - 0.01 adopts
    assert select({"C1": .80, "G1": .81, "G2": .90}) == ("G2", "G2")


def granite_text(Etr, y, Ete, seed):
    """(train OOF score, test score) from the harness text LR on the vectors."""
    return R.text_oof(Etr, np.asarray(y), fold_seed=seed), R.text_test_score(Etr, np.asarray(y), Ete)


def subset(tr, te, y_tr, frac):
    """Test helper: every positive plus `frac` of the negatives."""
    rng = np.random.default_rng(0)
    kt = (y_tr == 1) | (rng.random(len(tr)) < frac)
    ke = (te.y.to_numpy() == 1) | (rng.random(len(te)) < frac)
    return tr[kt].copy(), te[ke].copy(), y_tr[kt]


def claims_from(res, out_rel):
    c = {}

    def add(key, text, value, unit):
        c[PREFIX + key] = {"text": text, "value": value, "unit": unit, "source_script": SCRIPT_REL, "output_file": out_rel,
                           "status": "unverified", "verified_by": None}

    for f, fr in res["folds"].items():
        for n, e in fr["models"].items():
            lab = f"Granite comparison {f} (test {fr['test_months']}), {n}"
            for k, u in (("auc", "fraction"), ("top500_cve_id", "count"), ("top500_expected", "count"),
                         ("avg_precision", "fraction"), ("median_rank_cve_id", "count"), ("work50_cve_id", "count")):
                add(f"{f}.{n}.{k}.median", f"{lab}: {k}, median over seed sets 0-4", e["median"][k], u)
            for k, u in (("auc", "fraction"), ("top500_cve_id", "count")):
                add(f"{f}.{n}.{k}.min", f"{lab}: {k}, lowest of seed sets 0-4", e["min"][k], u)
                add(f"{f}.{n}.{k}.max", f"{lab}: {k}, highest of seed sets 0-4", e["max"][k], u)
            for k, u in (("auc", "fraction"), ("top500_expected", "count")):
                add(f"{f}.{n}.ci95_lo.{k}", f"{lab}: bootstrap 95% CI lower bound, {k} (seed set 0)", e["ci95_seed0"][k][0], u)
                add(f"{f}.{n}.ci95_hi.{k}", f"{lab}: bootstrap 95% CI upper bound, {k} (seed set 0)", e["ci95_seed0"][k][1], u)
    for n, v in res["selection"]["mean_auc_over_folds"].items():
        add(f"selection.{n}.mean_auc", f"Granite comparison {n}: mean over the two folds of the seed-median AUC", v, "fraction")
    return c


def write_claims(new, path):
    old = json.loads(path.read_text()) if path.exists() else {}
    for key, claim in new.items():
        prev = old.get(key)
        if prev and prev["text"] == claim["text"] and math.isclose(prev["value"], claim["value"], rel_tol=1e-9, abs_tol=1e-12):
            claim["status"], claim["verified_by"] = prev["status"], prev["verified_by"]
    path.write_text(json.dumps(new, indent=2) + "\n")
    return len(new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb", default=str(EMB))
    ap.add_argument("--out-dir", default=str(C.RESULTS))
    ap.add_argument("--subset", type=float, default=None, help="TEST ONLY: keep all positives and this share of negatives")
    a = ap.parse_args()
    out_dir = Path(a.out_dir).resolve()
    test_mode = a.subset is not None or Path(a.emb).resolve() != EMB.resolve()
    if test_mode and out_dir == C.RESULTS.resolve():
        sys.exit("--subset or a non-default --emb is a test: give --out-dir outside results/")
    t0 = time.time()
    tick = lambda msg: print(f"[{time.time() - t0:5.0f}s] {msg}", flush=True)

    self_check()
    emb = Embeddings(a.emb)
    pool, kev = load_pool(), load_kev()
    emb.require(pool.cve_id, "pool")
    emb.require(pd.read_csv(data_dir() / "scoreboard_2026.csv", usecols=["cve_id"], dtype={"cve_id": str}).cve_id, "scoreboard")
    tick("embeddings loaded, coverage complete")

    kind, cols = C.CANDIDATES["C1"]
    phase3 = json.loads((C.RESULTS / "model_candidates.json").read_text())
    res = {"embeddings": a.emb, "test_mode": test_mode, "subset": a.subset, "folds": {}}
    for f, spec in C.FOLDS.items():
        tr, te, y_tr = C.fold_data(pool, kev, spec)
        if a.subset is not None:
            tr, te, y_tr = subset(tr, te, y_tr, a.subset)
        fold = C.Fold(f, tr, te, y_tr)
        Etr, Ete = emb.rows(tr.cve_id), emb.rows(te.cve_id)
        scores = {"C1": [], "G1": [], "G2": []}
        for seed in C.SEEDS:
            g_oof, g_st = granite_text(Etr, y_tr, Ete, seed)
            t_oof, t_st = fold.text(seed)
            frames = {"C1": (C.frame(tr, cols, t_oof, kind), C.frame(te, cols, t_st, kind)),
                      "G1": (C.frame(tr, cols, g_oof, kind), C.frame(te, cols, g_st, kind)),
                      "G2": (C.frame(tr, cols, t_oof, kind).assign(txt_g=g_oof), C.frame(te, cols, t_st, kind).assign(txt_g=g_st))}
            for n, (Xa, Xb) in frames.items():
                scores[n].append(C.fit_score(kind, Xa, y_tr, Xb, seed))
        models = {n: C.over_seeds([C.report(fold.y_te, s, fold.ids) for s in v]) for n, v in scores.items()}
        if not test_mode:  # the C1 refit must be Phase 3's C1
            assert [r["auc"] for r in models["C1"]["per_seed"]] == [r["auc"] for r in phase3["candidates"][f]["C1"]["per_seed"]]
        cis = joblib.Parallel(n_jobs=-1)(joblib.delayed(M.bootstrap_ci)(fold.y_te, scores[n][0], fold.ids, C.N_BOOT, C.BOOT_SEED)
                                         for n in models)
        for n, ci in zip(models, cis):
            models[n]["ci95_seed0"] = ci
        res["folds"][f] = {"test_months": "..".join(spec["test"]), "train_rows": len(tr), "train_positives": int(y_tr.sum()),
                           "test_rows": len(te), "test_positives": int(fold.y_te.sum()), "models": models}
        tick(f"{f} done")

    mean_auc = {n: float(np.mean([res["folds"][f]["models"][n]["median"]["auc"] for f in C.FOLDS])) for n in ("C1", "G1", "G2")}
    best, adopted = select(mean_auc)
    res["selection"] = {"rule": ("higher mean AUC (two folds, seed medians) of G1/G2, G1 on an exact tie; adopt it if >= C1 - 0.01, "
                                 "else keep TF-IDF (C1). Top-500 etc. reported, not used to choose."),
                        "mean_auc_over_folds": mean_auc, "best_granite": best, "adopted": adopted,
                        "final_py_flag": None if adopted == "C1" else f"--text {adopted}"}
    tick(f"selection: {res['selection']}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "granite_comparison.json"
    out.write_text(json.dumps(res, indent=2, default=lambda x: x.item()) + "\n")
    C.write_meta(script=SCRIPT_REL, out=str(out_dir / "granite_comparison.meta.json"))  # absolute path overrides RESULTS
    out_rel = str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out)
    n = write_claims(claims_from(res, out_rel), out_dir / "claims_model_granite.json")
    tick(f"wrote {out}, its meta and {n} claims")


if __name__ == "__main__":
    main()
