"""Auditor: own row bootstrap (seed 7, 1000 resamples) of the solo AUCs, to sanity-check the meta CIs (seeds differ)."""
import json, numpy as np, pandas as pd, sys
from scipy.stats import rankdata
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
sys.argv = ["x"]; ns = {}
src = open(S + "ld_1_leak.py").read().split("y = te.y.to_numpy(); claimed")[0]  # reuse feature build only
exec(src, ns)
cols, te = ns["cols"], ns["te"]; y = te.y.to_numpy()
def auc(y, s):
    r = rankdata(s); n1 = y.sum(); n0 = len(y) - n1; return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
rng = np.random.default_rng(7); B = [rng.integers(0, len(y), len(y)) for _ in range(1000)]
meta = json.load(open(R + "results/leakage_table.meta.json"))["solo_auc_ci95"]
for k, x in cols.items():
    x = np.asarray(x, float); a = auc(y, x); flip = a < 0.5
    bs = [auc(y[b], x[b]) for b in B if y[b].sum() > 0]; bs = np.array(bs); bs = 1 - bs if flip else bs
    lo, hi = np.percentile(bs, [2.5, 97.5]); print(f"{k:28s} mine [{lo:.4f},{hi:.4f}]  meta [{meta[k][0]:.4f},{meta[k][1]:.4f}]")
