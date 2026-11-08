"""Tie ranges for first-pass-order claims; paired bootstrap for what n_affected_cpes adds; ablation seed ranges."""
import json, sys, numpy as np
S = "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch/"; sys.path.insert(0, S)
import mymetrics as M
import pandas as pd
Z = np.load(S + "u_scores.npz"); ext = json.load(open(S + "u_check_result.json"))["detail"]
_p = pd.read_parquet(S + "p3_pool.parquet", columns=["cve_id", "month", "y"])
def test(f):
    t = _p[_p.month >= "2025-01"].reset_index(drop=True); return t.y.to_numpy(), t.cve_id.to_numpy()

y, ids = test("primary")
out = {}
for n in ("hgb_signals_struct", "hgb_signals_struct_assigner", "hgb_all_text", "leaky_ncpe"):
    s = Z[f"primary.{n}"]
    hi = np.array([(s > v).sum() + 1 for v in s[y == 1]]); lo = np.array([(s >= v).sum() for v in s[y == 1]])
    out[n] = {"top500_best_worst": M.tie_topk(y, s, 500)[:3:2], "top1000_best_worst": M.tie_topk(y, s, 1000)[:3:2],
              "median_rank_range_approx": [float(np.median(hi)), float(np.median(lo))]}
best = Z["primary.best_check"]
rng = np.random.default_rng(0); idx = []
while len(idx) < 2000:
    i = rng.integers(0, len(y), len(y))
    if y[i].sum(): idx.append(i)
for a, b in (("leaky_ncpe", "hgb_all_text"), ("leaky_ncpe", "best_check")):
    sa, sb = Z[f"primary.{a}"], Z[f"primary.{b}"]
    da = [M.auc(y[i], sa[i]) - M.auc(y[i], sb[i]) for i in idx]
    dt = [M.tie_topk(y[i], sa[i], 500)[1] - M.tie_topk(y[i], sb[i], 500)[1] for i in idx]
    out[f"{a}-{b}"] = {"auc_diff": M.auc(y, sa) - M.auc(y, sb), "auc_ci": np.percentile(da, [2.5, 97.5]).tolist(),
                       "top500_exp_diff": M.tie_topk(y, sa, 500)[1] - M.tie_topk(y, sb, 500)[1],
                       "top500_ci": np.percentile(dt, [2.5, 97.5]).tolist(), "p_auc_le0": float(np.mean(np.array(da) <= 0))}
out["best_check"] = {"auc": M.auc(y, best), "top500_id": M.top_by_id(y, best, ids)}
for k, v in ext.items():
    if k.startswith("p3"):
        out[k] = {m: [round(min(x), 4), round(max(x), 4)] for m, x in v.items()}
json.dump(out, open(S + "u_extra_result.json", "w"), indent=1, default=float)
for k, v in out.items(): print(k, v)
