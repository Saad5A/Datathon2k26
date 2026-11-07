"""Follow-up audit: seed-median paired bootstrap (C1 minus exploit-then-EPSS) and unseen-assigner subset, all 5 seeds,
from the auditor's own C1 score files and own metrics. Compares with p3.* claims."""
import json, sys, numpy as np, pandas as pd
from joblib import Parallel, delayed
S = "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch/"; R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"
sys.path.insert(0, S)
from mymetrics import auc, tie_topk
p = pd.read_parquet(S + "my_pool2.parquet")
F = ["exploitdb", "metasploit", "nuclei", "poc_github"]
TEST = {"fold1": ("2025-01", "2025-09"), "fold2": ("2025-04", "2025-09")}
cl = json.load(open(R + "results/claims_model.json"))

def boot_idx(y, n=2000):
    rng = np.random.default_rng(0); idx = []
    while len(idx) < n:
        i = rng.integers(0, len(y), len(y))
        if y[i].sum(): idx.append(i)
    return idx

def paired(y, a, b, idx):
    da = [auc(y[i], a[i]) - auc(y[i], b[i]) for i in idx]
    dt = [tie_topk(y[i], a[i], 500)[1] - tie_topk(y[i], b[i], 500)[1] for i in idx]
    return {"auc.diff": auc(y, a) - auc(y, b), "auc.ci95_lo": np.percentile(da, 2.5), "auc.ci95_hi": np.percentile(da, 97.5),
            "top500_expected.diff": tie_topk(y, a, 500)[1] - tie_topk(y, b, 500)[1],
            "top500_expected.ci95_lo": np.percentile(dt, 2.5), "top500_expected.ci95_hi": np.percentile(dt, 97.5),
            "share_auc_gt0": float(np.mean(np.array(da) > 0)), "share_top_lt0": float(np.mean(np.array(dt) < 0))}

rows, res = [], {}
def chk(key, val, tol=1e-6):
    c = cl[key]["value"]; ok = abs(c - val) <= tol; res[key] = bool(ok)
    rows.append(f"{key:60s} mine={val:.6f} claimed={c:.6f} {'OK' if ok else 'MISMATCH'}")

for f, (lo, hi) in TEST.items():
    te = p[(p.month >= lo) & (p.month <= hi)].reset_index(drop=True)
    te[F] = te[F].fillna(0).astype(float)
    y, ids = te.y.to_numpy(), te.cve_id.to_numpy()
    b = (te[F].max(axis=1) * 10 + te.epss.fillna(0).clip(lower=0)).to_numpy()
    sc = [np.load(S + f"p3_C1_{f}_s{s}.npy") for s in range(5)]
    idx = boot_idx(y)
    per = Parallel(n_jobs=5)(delayed(paired)(y, a, b, idx) for a in sc)
    for k in per[0]:
        if k.startswith("share"): rows.append(f"{f} {k} per seed {[round(r[k], 4) for r in per]}"); continue
        chk(f"p3.{f}.paired.{k}", float(np.median([r[k] for r in per])))
        chk(f"p3.{f}.paired.{k}.seed0", float(per[0][k]))
        rows.append(f"   per seed {k}: {[round(float(r[k]), 4) for r in per]}")
    m = (te.asg_kev == 0).to_numpy(); u = []
    for a in sc:
        o = np.lexsort((ids, -a)); top = np.zeros(len(a), bool); top[o[:500]] = True
        u.append({"rows": int(m.sum()), "positives": int(y[m].sum()), "auc": float(auc(y[m], a[m])),
                  "top500_rows_from_subset": int((top & m).sum()), "top500_hits_from_subset": int((top & m & (y == 1)).sum())})
    for k in u[0]:
        chk(f"p3.{f}.unseen_assigner.{k}", float(np.median([r[k] for r in u])))
        chk(f"p3.{f}.unseen_assigner.{k}.seed0", float(u[0][k]))
    rows.append(f"   unseen per seed: {u}")
print("\n".join(rows)); print("checked", len(res), "ok", sum(res.values()))
json.dump(res, open(S + "f_paired_result.json", "w"), indent=1)
