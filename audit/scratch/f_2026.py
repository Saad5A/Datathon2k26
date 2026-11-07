"""Follow-up audit: 2026 preview assigner shares, auditor's own pipeline (p3_rederive functions, own pool, own assigner history)."""
import json, sys, numpy as np, pandas as pd
from joblib import Parallel, delayed
S = "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch/"; D = "/Users/aahmad/Working/datathon/code/Datathon2k26/.data/data/"
sys.path.insert(0, S)
import p3_rederive as P   # rebuilds p3_pool on import (harmless, deterministic)
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


pool = P.p
sb = pd.read_csv(D + "scoreboard_2026.csv", dtype={"cve_id": str, "snapshot_month": str})
v = pd.read_csv(D + "vulnerabilities.csv", usecols=["cve_id", "published", "assigner", "description"], dtype=str)
sb = sb.merge(v[["cve_id", "assigner", "description"]], on="cve_id", how="left")
print("rows", len(sb), "missing assigner", sb.assigner.isna().sum(), "dup", sb.cve_id.duplicated().sum())
kev = pd.read_csv(D + "known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str)
print("scoreboard CVEs already in KEV:", sb.cve_id.isin(kev.cve_id).sum(), "kev max", kev.date_added.max())
F = P.F
sb[F] = sb[F].fillna(0).astype(float); sb["epss_f"] = sb.epss.fillna(-1).astype(float)
sb["anyx"] = sb[F].max(axis=1); sb["nx"] = sb[F].sum(axis=1)
# assigner history: string-date comparisons, strictly before the snapshot month's first day
v21 = v[v.published.str[:10] >= "2021-01-01"]  # same 2021+ history as the training rows (harness/D1)
ka = kev.merge(v21[["cve_id", "assigner"]], on="cve_id", how="left").dropna(subset=["assigner"])
vd = v21.assign(d=v21.published.str[:10])
rate, cnt = np.zeros(len(sb)), np.zeros(len(sb))
for m in sorted(sb.snapshot_month.unique()):
    st = m + "-01"
    kc = ka[ka.date_added < st].assigner.value_counts(); pc = vd[vd.d < st].assigner.value_counts()
    idx = np.where(sb.snapshot_month == m)[0]; a = sb.assigner.iloc[idx]
    k = a.map(kc).fillna(0); cnt[idx] = k.to_numpy(); rate[idx] = (k / (a.map(pc) + 20)).fillna(0).to_numpy()
sb["asg_rate"], sb["asg_kev"] = rate, cnt
sb["y"] = 0
ytr = pool.y.to_numpy()
kind, cols = P.CAND["C1"]

def run(seed):
    oof, st = P.text(pool, sb, ytr, seed)
    return P.model(kind, cols, pool, sb, ytr, oof, st, seed)

scores = Parallel(n_jobs=5)(delayed(run)(s) for s in range(5))
np.save(S + "f_2026_scores.npy", np.array(scores))
asg, ids = sb.assigner.tolist(), sb.cve_id.tolist()
out = {}
for kn, k in (("none", None), ("100", 100), ("50", 50)):
    per = []
    for s in scores:
        top = capped(s.tolist(), asg, ids, k)
        per.append(pd.Series([asg[i] for i in top]).value_counts() / len(top))
    out[kn] = {"largest_per_seed": [float(x.iloc[0]) for x in per], "largest_name": [x.index[0] for x in per],
               "n_assigners": [len(x) for x in per], "seed0_top5": per[0].head(5).round(4).to_dict(),
               "median_largest": float(np.median([x.iloc[0] for x in per]))}
    print(kn, out[kn], flush=True)
# averaged-score variant (informational)
json.dump(out, open(S + "f_2026_result.json", "w"), indent=1)
