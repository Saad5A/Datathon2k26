"""Phase 7 audit: fresh refit of C1 on all labelled pool rows (auditor pool), score scoreboard, occlusion per signal group.
Does not import src/. Reuses p3_rederive definitions (auditor code) for text pipeline and HGB params."""
import sys, numpy as np, pandas as pd
from joblib import Parallel, delayed
from sklearn.ensemble import HistGradientBoostingClassifier
S = "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch/"; D = "/Users/aahmad/Working/datathon/code/Datathon2k26/.data/data/"
sys.path.insert(0, S)
import p3_rederive as P

pool = P.p
F = P.F
sb = pd.read_csv(D + "scoreboard_2026.csv", dtype={"cve_id": str, "snapshot_month": str, "published": str})
v = pd.read_csv(D + "vulnerabilities.csv", usecols=["cve_id", "published", "assigner", "description"], dtype=str)
sb = sb.merge(v[["cve_id", "assigner", "description"]], on="cve_id", how="left")
kev = pd.read_csv(D + "known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str)
sb[F] = sb[F].fillna(0).astype(float); sb["epss_f"] = sb.epss.fillna(-1).astype(float)
sb["anyx"] = sb[F].max(axis=1); sb["nx"] = sb[F].sum(axis=1)
v21 = v[v.published.str[:10] >= "2021-01-01"]
ka = kev.merge(v21[["cve_id", "assigner"]], on="cve_id", how="inner")
vd = v21.assign(d=v21.published.str[:10])
rate, cnt = np.zeros(len(sb)), np.zeros(len(sb))
for m in sorted(sb.snapshot_month.unique()):
    st = m + "-01"
    kc = ka[ka.date_added < st].assigner.value_counts(); pc = vd[vd.d < st].assigner.value_counts()
    idx = np.where(sb.snapshot_month == m)[0]; a = sb.assigner.iloc[idx]
    k = a.map(kc).fillna(0); cnt[idx] = k.to_numpy(); rate[idx] = (k / (a.map(pc).fillna(0) + 20)).fillna(0).to_numpy()
sb["asg_rate"], sb["asg_kev"] = rate, cnt
ytr = pool.y.to_numpy()
kind, cols = P.CAND["C1"]
GROUPS = {"epss": ["epss_f"], "public_exploit_code": F + ["anyx", "nx"], "assigner_kev_history": ["asg_rate", "asg_kev"],
          "description_text": ["txt"]}


def run(seed):
    oof, st = P.text(pool, sb, ytr, seed)
    A, B = pool.assign(txt=oof)[cols], sb.assign(txt=st)[cols]
    m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                       l2_regularization=5.0, early_stopping=False, random_state=seed).fit(A, ytr)
    out = {"actual": m.predict_proba(B)[:, 1], "st": st}
    for g, cs in GROUPS.items():
        B2 = B.copy()
        for c in cs:
            B2[c] = 0.0 if c in F + ["anyx", "nx"] else float(A[c].median())
        out[g] = m.predict_proba(B2)[:, 1]
    out["neutral"] = {c: float(A[c].median()) for c in cols}
    return out


res = Parallel(n_jobs=5)(delayed(run)(s) for s in range(5))
np.savez(S + "p7_scores.npz", actual=np.array([r["actual"] for r in res]), st=res[0]["st"],
         **{g: np.mean([r[g] for r in res], axis=0) for g in GROUPS})
sb[["cve_id", "published", "snapshot_month", "assigner", "epss", "anyx", "nx", "asg_rate", "asg_kev"]].to_parquet(S + "p7_sb.parquet")
print("neutral seed0", res[0]["neutral"]); print("done")
