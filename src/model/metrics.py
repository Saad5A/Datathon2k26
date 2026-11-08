"""Ranking metrics: pure functions on arrays. Self-check: .venv/bin/python src/model/metrics.py

Convention: a higher score ranks first, rank 1 is the top. A `ranks` array is 1-based and made by
`ranks_by_id` (deterministic: ties broken by cve_id ascending) or `mid_ranks` (order-free: tied rows
share the average rank). Top-k counts on tied scores also have `topk_tie_aware`.
"""
import math

import numpy as np
from scipy.stats import rankdata
from sklearn.metrics import average_precision_score, roc_auc_score


def ranks_by_id(s, ids):
    """1-based ranks, score descending, ties by `ids` ascending. Deterministic on any machine."""
    order = np.lexsort((ids, -np.asarray(s, dtype=float)))
    ranks = np.empty(len(order), dtype=np.int64)
    ranks[order] = np.arange(1, len(order) + 1)
    return ranks


def mid_ranks(s):
    """1-based ranks where tied rows share their average rank."""
    return rankdata(-np.asarray(s, dtype=float), method="average")


def hits_at_k(y, ranks, k):
    return int(np.sum(np.asarray(y)[np.asarray(ranks) <= k]))


def topk_tie_aware(y, s, k):
    """Best, expected and worst top-k hits over every order of the rows tied at the cutoff.

    Expected = hits above the tie + free slots * share of positives in the tie (random tie order).
    """
    y, s = np.asarray(y), np.asarray(s, dtype=float)
    if k >= len(s):
        n = int(y.sum())
        return {"best": n, "expected": float(n), "worst": n, "tied_group_size": 0,
                "positives_in_tied_group": 0, "slots_in_tied_group": 0}
    cutoff = np.partition(s, len(s) - k)[len(s) - k]  # k-th largest
    above, tied = s > cutoff, s == cutoff
    slots = k - int(above.sum())
    size, pos_tied, pos_above = int(tied.sum()), int(y[tied].sum()), int(y[above].sum())
    return {"best": pos_above + min(slots, pos_tied),
            "expected": pos_above + slots * pos_tied / size,
            "worst": pos_above + max(0, slots - (size - pos_tied)),
            "tied_group_size": size,
            "positives_in_tied_group": pos_tied,
            "slots_in_tied_group": slots}


def auc(y, s):
    return float(roc_auc_score(y, s))


def avg_precision(y, s):
    return float(average_precision_score(y, s))


def median_rank(y, ranks):
    """Median rank of the positives."""
    return float(np.median(np.asarray(ranks)[np.asarray(y) == 1]))


def work_to_catch(y, ranks, frac=0.5):
    """How far down the ranking you must go to catch `frac` of the positives (the work-saved number)."""
    pos = np.sort(np.asarray(ranks)[np.asarray(y) == 1])
    return float(pos[math.ceil(frac * len(pos)) - 1])


def summary(y, s, ids):
    """All order-dependent metrics two ways: `_cve_id` (ties by id) and `_expected`/`_mid` (tie-free)."""
    by_id, mid = ranks_by_id(s, ids), mid_ranks(s)
    return {
        "top250_cve_id": hits_at_k(y, by_id, 250),
        "top250_expected": topk_tie_aware(y, s, 250)["expected"],
        "top500_cve_id": hits_at_k(y, by_id, 500),
        "top500_expected": topk_tie_aware(y, s, 500)["expected"],
        "top1000_cve_id": hits_at_k(y, by_id, 1000),
        "top1000_expected": topk_tie_aware(y, s, 1000)["expected"],
        "auc": auc(y, s),
        "avg_precision": avg_precision(y, s),
        "median_rank_cve_id": median_rank(y, by_id),
        "median_rank_mid": median_rank(y, mid),
        "work50_cve_id": work_to_catch(y, by_id),
        "work50_mid": work_to_catch(y, mid),
    }


def bootstrap_ci(y, s, ids, n_boot=2000, seed=0):
    """Percentile 95% CI of every `summary` metric, resampling rows with replacement.

    `ids` must be sortable numbers or strings. A fixed seed gives every method the same resamples, so
    intervals across methods are paired. Resamples with no positive would break AUC: redrawn.
    """
    y, s, ids = np.asarray(y), np.asarray(s, dtype=float), np.asarray(ids)
    rng = np.random.default_rng(seed)
    rows = []
    while len(rows) < n_boot:
        i = rng.integers(0, len(y), len(y))
        if y[i].sum() == 0:
            continue
        rows.append(summary(y[i], s[i], ids[i]))
    return {key: [float(np.percentile([r[key] for r in rows], 2.5)),
                  float(np.percentile([r[key] for r in rows], 97.5))] for key in rows[0]}


if __name__ == "__main__":
    # 6 rows. Scores: .9 > .8 > .5 = .5 = .5 > .1. Positives: a (.9), d (.5), f (.1).
    ids = np.array(["a", "b", "c", "d", "e", "f"])
    s = np.array([.9, .8, .5, .5, .5, .1])
    y = np.array([1, 0, 0, 1, 0, 1])

    r = ranks_by_id(s, ids)
    assert r.tolist() == [1, 2, 3, 4, 5, 6]
    assert ranks_by_id(s[::-1], ids[::-1]).tolist() == [6, 5, 4, 3, 2, 1]  # row order does not matter
    assert mid_ranks(s).tolist() == [1, 2, 4, 4, 4, 6]

    assert [hits_at_k(y, r, k) for k in (1, 2, 3, 4, 6)] == [1, 1, 1, 2, 3]

    # k=3: above the tie a, b (1 hit); one slot in a tie of 3 holding 1 positive.
    t = topk_tie_aware(y, s, 3)
    assert (t["best"], t["worst"], t["tied_group_size"], t["slots_in_tied_group"]) == (2, 1, 3, 1)
    assert abs(t["expected"] - (1 + 1 / 3)) < 1e-12
    # k=2 ends exactly above the tie: the cutoff group is just b, no ambiguity.
    t = topk_tie_aware(y, s, 2)
    assert (t["best"], t["expected"], t["worst"], t["tied_group_size"]) == (1, 1.0, 1, 1)
    # k=4: two slots in the tie: best 2, worst 1 (the two negatives fill it), expected 1 + 2/3.
    t = topk_tie_aware(y, s, 4)
    assert (t["best"], t["worst"]) == (2, 1) and abs(t["expected"] - (1 + 2 / 3)) < 1e-12
    # k beyond the data: every positive counts.
    assert topk_tie_aware(y, s, 99)["best"] == 3

    # Positive vs negative pairs (negatives b .8, c .5, e .5): a beats all 3 = 3; d loses to b and ties
    # c and e = 2 * .5 = 1; f loses to all = 0. AUC = 4 / 9.
    assert abs(auc(y, s) - 4 / 9) < 1e-12
    # Recall rises 1/3 at each positive's threshold; precision there: .9 -> 1/1, .5 -> 2/5, .1 -> 3/6.
    assert abs(avg_precision(y, s) - (1 + 2 / 5 + 3 / 6) / 3) < 1e-12

    assert median_rank(y, r) == 4  # positives at 1, 4, 6
    assert median_rank(y, mid_ranks(s)) == 4
    assert work_to_catch(y, r) == 4  # ceil(.5 * 3) = 2nd positive
    assert work_to_catch(y, r, frac=1.0) == 6
    assert work_to_catch([1, 1, 0, 0], [1, 2, 3, 4]) == 1  # ceil(.5 * 2) = 1st

    # A constant column is one tie: id-order hits differ from the tie-free expectation.
    s0 = np.zeros(4)
    y0 = np.array([0, 0, 1, 1])
    i0 = np.array(["a", "b", "c", "d"])
    assert hits_at_k(y0, ranks_by_id(s0, i0), 2) == 0
    t = topk_tie_aware(y0, s0, 2)
    assert (t["best"], t["expected"], t["worst"]) == (2, 1.0, 0)

    # Bootstrap: fixed seed repeats exactly; a large sample's CI brackets the point estimate.
    rng = np.random.default_rng(1)
    ybig = (rng.random(2000) < .05).astype(int)
    sbig = ybig * .5 + rng.random(2000)
    idbig = np.arange(2000)
    a = bootstrap_ci(ybig, sbig, idbig, n_boot=200, seed=7)
    assert a == bootstrap_ci(ybig, sbig, idbig, n_boot=200, seed=7)
    assert a["auc"][0] < auc(ybig, sbig) < a["auc"][1]
    assert a["top250_cve_id"][0] <= hits_at_k(ybig, ranks_by_id(sbig, idbig), 250) <= a["top250_cve_id"][1]
    print("metrics self-check OK")
