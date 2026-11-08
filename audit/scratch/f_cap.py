"""Follow-up audit: per-assigner cap re-derived from the auditor's own C1 scores (p3_C1_*.npy), own re-ranking loop."""
import json, sys, numpy as np, pandas as pd
S = "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch/"
sys.path.insert(0, S)
p = pd.read_parquet(S + "my_pool2.parquet")
TEST = {"fold1": ("2025-01", "2025-09"), "fold2": ("2025-04", "2025-09")}

def capped(s, asg, ids, k, n=500, tieorder=None):
    # plain python walk: score desc, then tie key asc
    key = ids if tieorder is None else tieorder
    order = sorted(range(len(s)), key=lambda i: (-s[i], key[i]))
    used, out = {}, []
    for i in order:
        a = asg[i]
        if k is not None and used.get(a, 0) >= k:
            continue
        used[a] = used.get(a, 0) + 1; out.append(i)
        if len(out) == n: break
    return out

res = {}
for f, (a, b) in TEST.items():
    te = p[(p.month >= a) & (p.month <= b)].reset_index(drop=True)
    y = te.y.to_numpy(); ids = te.cve_id.tolist(); asg = te.assigner.fillna("(missing)").tolist()
    res[f] = {}
    for kn, k in (("none", None), ("100", 100), ("50", 50)):
        per = []
        for sd in range(5):
            s = np.load(S + f"p3_C1_{f}_s{sd}.npy")
            top = capped(s.tolist(), asg, ids, k)
            nties = len(s) - len(np.unique(s))
            # expected over tie orders: exact if cut region has no ties; else MC
            if nties:
                rng = np.random.default_rng(123)
                exp = float(np.mean([y[capped(s.tolist(), asg, ids, k, tieorder=rng.permutation(len(s)).tolist())].sum() for _ in range(50)]))
            else:
                exp = float(y[top].sum())
            sh = pd.Series([asg[i] for i in top]).value_counts()
            per.append({"by_id": int(y[top].sum()), "expected": exp, "ties": nties, "max_share": float(sh.iloc[0] / len(top)), "n": len(top)})
        res[f][kn] = {"per_seed": per, "median_expected": float(np.median([r["expected"] for r in per])),
                      "median_by_id": float(np.median([r["by_id"] for r in per])),
                      "median_share": float(np.median([r["max_share"] for r in per]))}
        print(f, kn, res[f][kn]["median_expected"], [(r["by_id"], r["expected"], r["ties"], r["max_share"]) for r in per], flush=True)
mean = {k: (res["fold1"][k]["median_expected"] + res["fold2"][k]["median_expected"]) / 2 for k in ("none", "100", "50")}
best = max(mean.values()); chosen = next(k for k in ("50", "100", "none") if mean[k] >= best - 1)
res["mean"], res["chosen"] = mean, chosen
print(mean, chosen)
json.dump(res, open(S + "f_cap_result.json", "w"), indent=1)
