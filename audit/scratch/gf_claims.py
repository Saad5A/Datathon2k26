"""Granite-final audit: check every p6.granite.* claim against the auditor's own scores (gf_*_fold*_s*.npy)."""
import json, math, sys, numpy as np, pandas as pd
from joblib import Parallel, delayed
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
sys.path.insert(0, S)
import mymetrics as M
cl = json.load(open(R + "results/claims_model_granite.json"))
p = pd.read_parquet(S + "p3_pool.parquet")
TEST = {"fold1": ("2025-01", "2025-09"), "fold2": ("2025-04", "2025-09")}


def mid_desc(s):
    _, inv, cnt = np.unique(-s, return_inverse=True, return_counts=True)
    return (np.cumsum(cnt) - (cnt - 1) / 2)[inv]


def stats(y, s):
    mr = np.sort(mid_desc(s)[y == 1]); r = len(s) + 1 - mid_desc(s); n1 = y.sum(); n0 = len(y) - n1
    return {"top500_expected": M.tie_topk(y, s, 500)[1], "auc": (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)}


def boot_idx(y, n=2000):
    rng = np.random.default_rng(0); idx = []
    while len(idx) < n:
        i = rng.integers(0, len(y), len(y))
        if y[i].sum(): idx.append(i)
    return idx


def ci(y, s, idx):
    st = [stats(y[i], s[i]) for i in idx]
    return {k: np.percentile([r[k] for r in st], [2.5, 97.5]) for k in st[0]}


def point(y, s, ids):
    o = np.lexsort((ids, -s)); r = np.empty(len(s), int); r[o] = np.arange(1, len(s) + 1); pos = np.sort(r[y == 1])
    return {"auc": float(M.auc(y, s)), "top500_cve_id": int(y[r <= 500].sum()), "top500_expected": float(M.tie_topk(y, s, 500)[1]),
            "avg_precision": M.ap(y, s), "median_rank_cve_id": float(np.median(pos)),
            "work50_cve_id": float(pos[math.ceil(len(pos) / 2) - 1])}


mine = {}
for f, (a, b) in TEST.items():
    te = p[(p.month >= a) & (p.month <= b)].reset_index(drop=True); y, ids = te.y.to_numpy(), te.cve_id.to_numpy()
    idx = boot_idx(y)
    sc = {n: [np.load(S + f"gf_{n}_{f}_s{s}.npy") for s in range(5)] for n in ("C1", "G1", "G2")}
    cis = Parallel(n_jobs=3)(delayed(ci)(y, sc[n][0], idx) for n in sc)
    for (n, v), c in zip(sc.items(), cis):
        per = [point(y, s, ids) for s in v]
        for k in per[0]:
            vals = [q[k] for q in per]
            mine[f"p6.granite.{f}.{n}.{k}.median"] = float(np.median(vals))
            mine[f"p6.granite.{f}.{n}.{k}.min"] = float(min(vals)); mine[f"p6.granite.{f}.{n}.{k}.max"] = float(max(vals))
        for k, (lo, hi) in c.items():
            mine[f"p6.granite.{f}.{n}.ci95_lo.{k}"] = float(lo); mine[f"p6.granite.{f}.{n}.ci95_hi.{k}"] = float(hi)
for n in ("C1", "G1", "G2"):
    mine[f"p6.granite.selection.{n}.mean_auc"] = (mine[f"p6.granite.fold1.{n}.auc.median"] + mine[f"p6.granite.fold2.{n}.auc.median"]) / 2
res = {}
for k, c in cl.items():
    if k not in mine:
        res[k] = "UNCHECKED"; continue
    res[k] = "PASS" if abs(mine[k] - c["value"]) <= (0 if c["unit"] == "count" and float(c["value"]).is_integer() else 1e-6) else f"FAIL mine={mine[k]} claimed={c['value']}"
bad = {k: v for k, v in res.items() if v != "PASS"}
print(len(res), "claims;", sum(v == "PASS" for v in res.values()), "PASS"); print(json.dumps(bad, indent=1))
json.dump({"results": res, "mine": mine}, open(S + "gf_claims_result.json", "w"), indent=1)
