"""Metrics for AutoRank Lab."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


def hits_at_k(y: np.ndarray, score: np.ndarray, k: int, ids: np.ndarray | None = None) -> int:
    y = np.asarray(y, dtype=np.int8)
    s = np.asarray(score, dtype=float)
    if ids is None:
        order = np.argsort(-s, kind="mergesort")
    else:
        order = np.lexsort((np.asarray(ids), -s))
    return int(y[order[:k]].sum())


def median_rank(y: np.ndarray, score: np.ndarray, ids: np.ndarray | None = None) -> float:
    y = np.asarray(y, dtype=np.int8)
    s = np.asarray(score, dtype=float)
    if ids is None:
        order = np.argsort(-s, kind="mergesort")
    else:
        order = np.lexsort((np.asarray(ids), -s))
    ranks = np.empty(len(y), dtype=np.int64)
    ranks[order] = np.arange(1, len(y) + 1)
    return float(np.median(ranks[y == 1]))


def work_to_catch(y: np.ndarray, score: np.ndarray, frac: float = 0.5) -> int | None:
    y = np.asarray(y, dtype=np.int8)
    s = np.asarray(score, dtype=float)
    order = np.argsort(-s, kind="mergesort")
    cum = np.cumsum(y[order])
    need = frac * y.sum()
    if y.sum() == 0:
        return None
    return int(np.searchsorted(cum, need, side="left") + 1)


def summary(y: np.ndarray, score: np.ndarray, ids: np.ndarray | None = None) -> dict:
    y = np.asarray(y, dtype=np.int8)
    s = np.asarray(score, dtype=float)
    if y.sum() == 0:
        raise ValueError("no positives")
    return {
        "top500": hits_at_k(y, s, 500, ids),
        "top250": hits_at_k(y, s, 250, ids),
        "top243": hits_at_k(y, s, 243, ids),
        "top161": hits_at_k(y, s, 161, ids),
        "auc": float(roc_auc_score(y, s)),
        "avg_precision": float(average_precision_score(y, s)),
        "median_rank": median_rank(y, s, ids),
        "work50": work_to_catch(y, s, 0.5),
        "n": int(len(y)),
        "positives": int(y.sum()),
    }


def bootstrap_topk(
    y: np.ndarray,
    score: np.ndarray,
    ids: np.ndarray | None = None,
    k: int = 500,
    n_boot: int = 500,
    seed: int = 0,
) -> dict:
    y = np.asarray(y, dtype=np.int8)
    s = np.asarray(score, dtype=float)
    id_arr = np.asarray(ids) if ids is not None else None
    rng = np.random.default_rng(seed)
    vals = []
    n = len(y)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        vals.append(hits_at_k(y[idx], s[idx], k, None if id_arr is None else id_arr[idx]))
    vals = np.asarray(vals)
    return {
        "mean": float(vals.mean()),
        "lo": float(np.percentile(vals, 2.5)),
        "hi": float(np.percentile(vals, 97.5)),
    }


def paired_topk_diff(
    y: np.ndarray,
    score_a: np.ndarray,
    score_b: np.ndarray,
    ids: np.ndarray | None = None,
    k: int = 243,
    n_boot: int = 1000,
    seed: int = 0,
) -> dict:
    """Paired bootstrap difference a - b in hits@k (same resampled rows)."""
    y = np.asarray(y, dtype=np.int8)
    a = np.asarray(score_a, dtype=float)
    b = np.asarray(score_b, dtype=float)
    id_arr = np.asarray(ids) if ids is not None else None
    rng = np.random.default_rng(seed)
    diffs = []
    n = len(y)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yy = y[idx]
        ids_b = None if id_arr is None else id_arr[idx]
        diffs.append(hits_at_k(yy, a[idx], k, ids_b) - hits_at_k(yy, b[idx], k, ids_b))
    d = np.asarray(diffs)
    return {
        "diff": float(hits_at_k(y, a, k, id_arr) - hits_at_k(y, b, k, id_arr)),
        "lo": float(np.percentile(d, 2.5)),
        "hi": float(np.percentile(d, 97.5)),
        "p_gt0": float((d > 0).mean()),
        "p_lt0": float((d < 0).mean()),
    }
