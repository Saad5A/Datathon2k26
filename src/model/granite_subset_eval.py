"""Honest Granite-vs-TF-IDF comparison on a partial watsonx embedding slice.

Unlike granite.py (which requires full pool+scoreboard coverage), this script
intersects available embeddings with each backtest fold and reports metrics only
on covered rows. Suitable for the Lite-plan ~1.5k–2.5k vector cache.

  python src/model/granite_subset_eval.py

Writes results/granite_subset_comparison.json and merges claims into
results/claims_model_granite_subset.json (prefix p6.granite_subset.).
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

import candidates as C
import reproduce_first_pass as R
from pool import ROOT, load_kev, load_pool

SCRIPT = "src/model/granite_subset_eval.py"
OUT = ROOT / "results" / "granite_subset_comparison.json"
CLAIMS = ROOT / "results" / "claims_model_granite_subset.json"
EMB_PATHS = [
    ROOT / "data_cache" / "granite_embeddings_watsonx_subset.parquet",
    ROOT / "data_cache" / "granite_embeddings_watsonx_evalslice.parquet",
    ROOT / "data_cache" / "granite_embeddings.parquet",
]


def load_embeddings():
    frames = []
    used = []
    for p in EMB_PATHS:
        if p.exists():
            frames.append(pd.read_parquet(p))
            used.append(str(p.relative_to(ROOT)))
    if not frames:
        sys.exit("No granite embedding parquet found under data_cache/")
    df = pd.concat(frames, ignore_index=True).drop_duplicates("cve_id", keep="last")
    mat = np.stack(df.vector.to_numpy()).astype(np.float32)
    return pd.Index(df.cve_id.astype(str)), mat, used


def metrics(y, s):
    y = np.asarray(y).astype(int)
    s = np.asarray(s, dtype=float)
    out = {
        "n": int(len(y)),
        "n_pos": int(y.sum()),
        "auc": None,
        "avg_precision": None,
        "top50_hits": None,
        "top100_hits": None,
        "top500_hits": None,
        "recall_at_50": None,
        "recall_at_100": None,
        "recall_at_500": None,
    }
    if y.sum() == 0 or y.sum() == len(y):
        return out
    out["auc"] = float(roc_auc_score(y, s))
    out["avg_precision"] = float(average_precision_score(y, s))
    order = np.argsort(-s, kind="stable")
    for k in (50, 100, 500):
        kk = min(k, len(order))
        hits = int(y[order[:kk]].sum())
        out[f"top{k}_hits"] = hits
        out[f"recall_at_{k}"] = float(hits / y.sum())
    return out


def main():
    t0 = time.time()
    idx, mat, used = load_embeddings()
    pool, kev = load_pool(), load_kev()
    have = set(idx)
    res = {
        "embeddings_files": used,
        "n_vectors": int(len(idx)),
        "folds": {},
        "note": (
            "Partial watsonx Lite slice: metrics are only on CVEs with embeddings. "
            "This is not the full pre-registered granite.py adoption test."
        ),
    }

    for fname, spec in C.FOLDS.items():
        tr, te, y_tr = C.fold_data(pool, kev, spec)
        tr_m = tr.cve_id.astype(str).isin(have).to_numpy()
        te_m = te.cve_id.astype(str).isin(have).to_numpy()
        tr_c, te_c = tr.loc[tr_m].copy(), te.loc[te_m].copy()
        y_tr_c = np.asarray(y_tr)[tr_m]
        y_te_c = te_c.y.to_numpy()
        fold_info = {
            "train_covered": int(tr_m.sum()),
            "train_pos_covered": int(y_tr_c.sum()),
            "test_covered": int(te_m.sum()),
            "test_pos_covered": int(y_te_c.sum()),
            "test_pos_total": int(te.y.sum()),
            "models": {},
        }
        if tr_m.sum() < 30 or te_m.sum() < 20 or y_tr_c.sum() < 5 or y_te_c.sum() < 1:
            fold_info["skipped"] = "insufficient covered positives/rows for a fair LR comparison"
            res["folds"][fname] = fold_info
            print(f"{fname}: SKIPPED {fold_info}")
            continue

        # Build embedding matrices in fold row order
        loc = {c: i for i, c in enumerate(idx)}
        Etr = mat[[loc[c] for c in tr_c.cve_id.astype(str)]]
        Ete = mat[[loc[c] for c in te_c.cve_id.astype(str)]]

        # TF-IDF text scores on the covered subset (fit on covered train only)
        Xtr, Xte = R.text_vectors(C.masked(tr_c), C.masked(te_c))
        tfidf_scores = []
        gran_scores = []
        for seed in range(5):
            # TF-IDF LR
            oof = R.text_oof(Xtr, y_tr_c, fold_seed=seed)
            st = R.text_test_score(Xtr, y_tr_c, Xte)
            tfidf_scores.append(st)
            # Granite LR on vectors
            g_oof = R.text_oof(Etr, y_tr_c, fold_seed=seed)
            g_st = R.text_test_score(Etr, y_tr_c, Ete)
            gran_scores.append(g_st)
            _ = oof, g_oof  # OOF computed for parity with harness; test metrics use st/g_st

        tfidf_mean = np.mean(tfidf_scores, axis=0)
        gran_mean = np.mean(gran_scores, axis=0)
        fold_info["models"]["tfidf_text_lr"] = metrics(y_te_c, tfidf_mean)
        fold_info["models"]["granite_text_lr"] = metrics(y_te_c, gran_mean)
        fold_info["models"]["delta_auc_granite_minus_tfidf"] = (
            None
            if fold_info["models"]["tfidf_text_lr"]["auc"] is None
            or fold_info["models"]["granite_text_lr"]["auc"] is None
            else fold_info["models"]["granite_text_lr"]["auc"] - fold_info["models"]["tfidf_text_lr"]["auc"]
        )
        res["folds"][fname] = fold_info
        print(f"{fname}: {json.dumps(fold_info['models'], indent=2)}")

    # Simple adoption hint on available folds
    deltas = [
        fr["models"].get("delta_auc_granite_minus_tfidf")
        for fr in res["folds"].values()
        if fr.get("models") and fr["models"].get("delta_auc_granite_minus_tfidf") is not None
    ]
    if deltas:
        mean_delta = float(np.mean(deltas))
        res["selection_hint"] = {
            "mean_delta_auc_granite_minus_tfidf": mean_delta,
            "prefer": "granite_text_lr" if mean_delta >= -0.01 else "tfidf_text_lr",
            "rule": "Prefer Granite text LR if mean AUC delta >= -0.01 vs TF-IDF on covered folds; else keep TF-IDF.",
        }
    else:
        res["selection_hint"] = {"prefer": "tfidf_text_lr", "reason": "no fold had enough covered positives"}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")

    # Claims (unverified until auditor)
    claims = {}
    if CLAIMS.exists():
        claims = json.loads(CLAIMS.read_text(encoding="utf-8"))
    claims["p6.granite_subset.n_vectors"] = {
        "text": "Watsonx Granite embedding vectors available for subset evaluation",
        "value": int(len(idx)),
        "unit": "count",
        "source_script": SCRIPT,
        "output_file": "results/granite_subset_comparison.json",
        "status": "unverified",
        "verified_by": None,
    }
    if deltas:
        claims["p6.granite_subset.mean_delta_auc"] = {
            "text": "Mean (Granite text LR AUC - TF-IDF text LR AUC) on embedding-covered fold slices",
            "value": float(np.mean(deltas)),
            "unit": "fraction",
            "source_script": SCRIPT,
            "output_file": "results/granite_subset_comparison.json",
            "status": "unverified",
            "verified_by": None,
        }
    CLAIMS.write_text(json.dumps(claims, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
