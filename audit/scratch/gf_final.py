"""Granite-final audit: independent G2 refit on all labelled pool rows, score the 2026 scoreboard, occlusion per group.
Does not import src/. Pool = auditor p3_pool.parquet; scoreboard features built from raw CSVs as in p7_rederive.py."""
import re, numpy as np, pandas as pd
from joblib import Parallel, delayed
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"; D = R + ".data/data/"
pool = pd.read_parquet(S + "p3_pool.parquet"); assert int(pool.y.sum()) == 117 and len(pool) == 75148
F = ["exploitdb", "metasploit", "nuclei", "poc_github"]
COLS = ["epss_f", *F, "anyx", "nx", "asg_rate", "asg_kev", "txt", "txt_g"]
W = re.compile(r"exploited in the wild|actively exploited|known to be exploited|has been exploited|"
               r"may have been exploited|is being exploited|CISA|KEV", re.I)
sb = pd.read_csv(D + "scoreboard_2026.csv", dtype={"cve_id": str, "snapshot_month": str, "published": str})
v = pd.read_csv(D + "vulnerabilities.csv", usecols=["cve_id", "published", "assigner", "description"], dtype=str)
sb = sb.merge(v[["cve_id", "assigner", "description"]], on="cve_id", how="left")
kev = pd.read_csv(D + "known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str)
sb[F] = sb[F].fillna(0).astype(float); sb["epss_f"] = sb.epss.fillna(-1).astype(float)
sb["anyx"] = sb[F].max(axis=1); sb["nx"] = sb[F].sum(axis=1)
v21 = v[v.published.str[:10] >= "2021-01-01"]
ka = kev.merge(v21[["cve_id", "assigner"]], on="cve_id", how="inner"); vd = v21.assign(d=v21.published.str[:10])
rate, cnt = np.zeros(len(sb)), np.zeros(len(sb))
for m in sorted(sb.snapshot_month.unique()):
    st = m + "-01"
    kc = ka[ka.date_added < st].assigner.value_counts(); pc = vd[vd.d < st].assigner.value_counts()
    idx = np.where(sb.snapshot_month == m)[0]; a = sb.assigner.iloc[idx]
    k = a.map(kc).fillna(0); cnt[idx] = k.to_numpy(); rate[idx] = (k / (a.map(pc).fillna(0) + 20)).fillna(0).to_numpy()
sb["asg_rate"], sb["asg_kev"] = rate, cnt
E = pd.read_parquet(R + "data_cache/granite_embeddings.parquet"); EI = pd.Index(E.cve_id)
EM = np.stack(E.vector.to_numpy()).astype(np.float32)
Gtr, Gte = EM[EI.get_indexer(pool.cve_id)], EM[EI.get_indexer(sb.cve_id)]
y = pool.y.to_numpy()
tf = TfidfVectorizer(ngram_range=(1, 2), min_df=8, max_features=30000, sublinear_tf=True, stop_words="english")
Ttr = tf.fit_transform([W.sub(" ", s) for s in pool.description.fillna("")])
Tte = tf.transform([W.sub(" ", s) for s in sb.description.fillna("")])
lr = lambda: LogisticRegression(C=2, class_weight="balanced", max_iter=500)
t_st = lr().fit(Ttr, y).predict_proba(Tte)[:, 1]; g_st = lr().fit(Gtr, y).predict_proba(Gte)[:, 1]
GROUPS = {"epss": ["epss_f"], "public_exploit_code": F + ["anyx", "nx"], "assigner_kev_history": ["asg_rate", "asg_kev"],
          "description_text": ["txt", "txt_g"]}


def oof(X, seed):
    o = np.zeros(len(y))
    for i, j in StratifiedKFold(5, shuffle=True, random_state=seed).split(X, y):
        o[j] = lr().fit(X[i], y[i]).predict_proba(X[j])[:, 1]
    return o


def run(seed):
    A = pool.assign(txt=oof(Ttr, seed), txt_g=oof(Gtr, seed))[COLS]; B = sb.assign(txt=t_st, txt_g=g_st)[COLS]
    m = HGB(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40, l2_regularization=5.0,
            early_stopping=False, random_state=seed).fit(A, y)
    out = {"actual": m.predict_proba(B)[:, 1], "neutral": {c: float(A[c].median()) for c in COLS}}
    for g, cs in GROUPS.items():
        out[g] = m.predict_proba(B.assign(**{c: (0.0 if c in F + ["anyx", "nx"] else float(A[c].median())) for c in cs}))[:, 1]
    return out


res = Parallel(n_jobs=5)(delayed(run)(s) for s in range(5))
np.savez(S + "gf_final_scores.npz", actual=np.array([r["actual"] for r in res]), st=t_st, g_st=g_st,
         **{g: np.mean([r[g] for r in res], axis=0) for g in GROUPS})
sb[["cve_id", "published", "snapshot_month", "assigner", "epss", "anyx", "nx", "asg_rate", "asg_kev"]].to_parquet(S + "gf_sb.parquet")
print("neutral seed0", res[0]["neutral"]); print("done")
