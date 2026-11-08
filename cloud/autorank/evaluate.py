"""Evaluate one genome on the time-safe folds."""
from __future__ import annotations

import json

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from . import data, features, metrics
from .config import FOLDS
from .models import complexity, fit_predict


def _rank_scores(order: np.ndarray) -> np.ndarray:
    s = np.empty(len(order), dtype=float)
    s[order] = -np.arange(len(order), dtype=float)
    return s


def evaluate_genome(
    genome: dict,
    folds: tuple[str, ...] = ("primary", "rolling"),
    seed: int = 0,
    bootstrap: int = 100,
) -> dict:
    per_fold: dict[str, dict] = {}
    try:
        for fold in folds:
            n_seeds = int(genome["postprocess"].get("seed_average", 1) or 1)
            scores = None
            te0 = None
            groups0 = None
            for i in range(n_seeds):
                tr, te = data.load_fold(fold, seed=seed + i)
                groups = features.resolve_groups(tr, genome["features"])
                groups = [g for g in groups if all(c in te.columns for c in features.feature_columns([g]))]
                if not groups:
                    raise ValueError("no feature groups available")
                Xtr = features.matrix(tr, groups)
                Xte = features.matrix(te, groups)
                ytr = tr["positive"].to_numpy(dtype=np.int8)
                pred = fit_predict(
                    genome["model"], genome["params"], Xtr, ytr, Xte, seed=seed + i
                )
                if scores is None:
                    scores = pred.copy()
                    te0 = te
                    groups0 = groups
                else:
                    scores += pred
            scores /= n_seeds
            te = te0
            groups = groups0
            yte = te["positive"].to_numpy(dtype=np.int8)
            post = genome["postprocess"]
            order = features.select_top(
                te,
                scores,
                groups,
                cap=post.get("cap"),
                month_allocation=post.get("month_allocation", "none"),
                flag_quota=post.get("flag_quota"),
                limit=500,
            )
            m = features.order_metrics(yte, order)
            rs = _rank_scores(order)
            m["auc"] = float(roc_auc_score(yte, rs))
            m["avg_precision"] = float(average_precision_score(yte, rs))
            if bootstrap:
                m["ci_top243"] = metrics.bootstrap_topk(yte, rs, k=243, n_boot=bootstrap, seed=seed)
                m["ci_top500"] = metrics.bootstrap_topk(yte, rs, k=500, n_boot=bootstrap, seed=seed)
            m["fold"] = fold
            m["features_used"] = groups
            m["features_dropped"] = [g for g in genome["features"] if g not in groups]
            per_fold[fold] = m
        ok = [m for m in per_fold.values() if "top243" in m]
        mean = {
            key: float(np.mean([m[key] for m in ok]))
            for key in ("top243", "top500", "top161", "auc", "avg_precision", "median_rank", "work50")
        }
        mean["complexity"] = complexity(genome)
        return {"status": "ok", "per_fold": per_fold, "mean": mean}
    except Exception as exc:  # noqa: BLE001 - a failed genome is data, not a crash
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}", "per_fold": per_fold}


C1_GENOME = {
    "features": ["signals", "assigner", "text_tfidf"],
    "model": "hgb",
    "params": {
        "max_depth": 3,
        "learning_rate": 0.05,
        "max_iter": 150,
        "min_samples_leaf": 40,
        "l2_regularization": 5.0,
    },
    "postprocess": {
        "cap": 50,
        "month_allocation": "none",
        "flag_quota": None,
        "seed_average": 1,
    },
}

# The honest adoption gate uses the audited five-seed protocol.
C1_CONTROL = json.loads(json.dumps(C1_GENOME))
C1_CONTROL["postprocess"]["seed_average"] = 5


def with_seed_average(genome: dict, n: int) -> dict:
    out = json.loads(json.dumps(genome))
    out["postprocess"]["seed_average"] = int(n)
    return out


def evaluate_c1(
    folds: tuple[str, ...] = ("primary", "rolling"),
    seed: int = 0,
    bootstrap: int = 200,
    five_seed: bool = True,
) -> dict:
    genome = C1_CONTROL if five_seed else C1_GENOME
    return evaluate_genome(genome, folds=folds, seed=seed, bootstrap=bootstrap)


def rank_scores(order: np.ndarray) -> np.ndarray:
    s = np.empty(len(order), dtype=float)
    s[order] = -np.arange(len(order), dtype=float)
    return s


def predict_order(genome: dict, fold: str, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Return (y_test, final_row_order) for one fold; used by the five-seed gate."""
    n_seeds = int(genome["postprocess"].get("seed_average", 1) or 1)
    scores = None
    te0 = None
    groups0 = None
    for i in range(n_seeds):
        tr, te = data.load_fold(fold, seed=seed + i)
        groups = features.resolve_groups(tr, genome["features"])
        groups = [g for g in groups if all(c in te.columns for c in features.feature_columns([g]))]
        if not groups:
            raise ValueError("no feature groups available")
        Xtr = features.matrix(tr, groups)
        Xte = features.matrix(te, groups)
        ytr = tr["positive"].to_numpy(dtype=np.int8)
        pred = fit_predict(genome["model"], genome["params"], Xtr, ytr, Xte, seed=seed + i)
        if scores is None:
            scores = pred.copy()
            te0 = te
            groups0 = groups
        else:
            scores += pred
    scores /= n_seeds
    post = genome["postprocess"]
    order = features.select_top(
        te0,
        scores,
        groups0,
        cap=post.get("cap"),
        month_allocation=post.get("month_allocation", "none"),
        flag_quota=post.get("flag_quota"),
        limit=500,
    )
    return te0["positive"].to_numpy(dtype=np.int8), order
