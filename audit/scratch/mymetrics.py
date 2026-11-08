import numpy as np
def avg_ranks(s):
    o = np.argsort(s, kind="mergesort"); ss = s[o]; r = np.empty(len(s))
    _, start, counts = np.unique(ss, return_index=True, return_counts=True)
    for st, ct in zip(start, counts): r[o[st:st+ct]] = st + (ct + 1) / 2
    return r
def auc(y, s):
    r = avg_ranks(np.asarray(s, float)); y = np.asarray(y); n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
def ap(y, s):
    _, inv = np.unique(-np.asarray(s, float), return_inverse=True)
    tp = np.bincount(inv, weights=y); n = np.bincount(inv)
    return float(np.sum(tp / np.sum(y) * np.cumsum(tp) / np.cumsum(n)))
def tie_topk(y, s, k):
    cut = np.sort(s)[::-1][k - 1]; above, tied = s > cut, s == cut
    slots = k - above.sum(); pt = y[tied].sum(); sz = tied.sum(); pa = y[above].sum()
    return pa + min(slots, pt), pa + slots * pt / sz, pa + max(0, slots - (sz - pt)), sz
def top_by_id(y, s, ids, k=500):
    o = np.lexsort((ids, -s)); return int(y[o[:k]].sum())
