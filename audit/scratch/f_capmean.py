"""Informational: cap rule evaluated on the seed-MEAN score (the pre-registered final 2026 score), auditor's C1 scores."""
import numpy as np, pandas as pd, sys
S = "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch/"
p = pd.read_parquet(S + "my_pool2.parquet")
for f, (a, b) in {"fold1": ("2025-01", "2025-09"), "fold2": ("2025-04", "2025-09")}.items():
    te = p[(p.month >= a) & (p.month <= b)].reset_index(drop=True); y = te.y.to_numpy()
    s = np.mean([np.load(S + f"p3_C1_{f}_s{i}.npy") for i in range(5)], axis=0)
    o = np.lexsort((te.cve_id.to_numpy(), -s)); g = te.assigner.fillna("(missing)").to_numpy()[o]
    rank_in_g = pd.Series(g).groupby(g).cumcount().to_numpy()
    out = {k: int(y[o[(rank_in_g < (k or 10**9))][:500]].sum()) for k in (None, 100, 50)}
    srt = np.sort(s)[::-1]; print(f, "seed-mean score top500 hits by cap", out, "ties at cut", int((s == srt[499]).sum()))
