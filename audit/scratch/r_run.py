"""Reverse-time audit: own re-derivation. Reuses the auditor pool (p3_pool.parquet, built from raw CSVs in a1/a2)
and the auditor C1 text/HGB code in p3_rederive.py (no import of src/). Labels re-derived from known_exploited.csv here."""
import json, math, sys, numpy as np, pandas as pd
from joblib import Parallel, delayed
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
sys.path.insert(0, S)
import mymetrics as M
D = R + ".data/data/"

p = pd.read_parquet(S + "p3_pool.parquet")
F = ["exploitdb", "metasploit", "nuclei", "poc_github"]
SIG = ["epss_f", *F, "anyx", "nx"]; C1 = SIG + ["asg_rate", "asg_kev", "txt"]

# ---- labels straight from raw KEV, string date compare ----
kev = pd.read_csv(D + "known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str)
kd = dict(zip(kev.cve_id, kev.date_added))
def month_end(m):
    y, mo = int(m[:4]), int(m[5:7]); return (pd.Timestamp(y, mo, 1) + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
me = {m: month_end(m) for m in p.month.unique()}
lim = {m: min((pd.Timestamp(me[m]) + pd.Timedelta(days=365)).strftime("%Y-%m-%d"), "2025-12-31") for m in me}
yraw = np.array([int(isinstance(kd.get(c), str) and me[m] < kd[c] <= lim[m]) for c, m in zip(p.cve_id, p.month)])
assert (yraw == p.y.to_numpy()).all(), "label mismatch"
tr = p[(p.month >= "2025-01") & (p.month <= "2025-09")].reset_index(drop=True)
te = p[(p.month >= "2024-01") & (p.month <= "2024-12")].reset_index(drop=True)
ytr, y, ids = tr.y.to_numpy(), te.y.to_numpy(), te.cve_id.to_numpy()
out = {"train_rows": len(tr), "train_positives": int(ytr.sum()), "test_rows": len(te), "test_positives": int(y.sum()),
       "overlap": len(set(tr.cve_id) & set(te.cve_id)),
       "label_window_days": {m: (pd.Timestamp(lim[m]) - pd.Timestamp(me[m])).days for m in sorted(me)},
       "train_pos_by_month": tr.groupby("month").y.sum().to_dict(), "test_pos_by_month": te.groupby("month").y.sum().to_dict()}


def ranks_id(s):
    o = np.lexsort((ids, -s)); r = np.empty(len(s), int); r[o] = np.arange(1, len(s) + 1); return r


def mets(s, yy=None, ii=None):
    yy = y if yy is None else yy; ii = ids if ii is None else ii
    o = np.lexsort((ii, -s)); r = np.empty(len(s), int); r[o] = np.arange(1, len(s) + 1)
    pos = np.sort(r[yy == 1]); b, e, w, sz = M.tie_topk(yy, s, 500)
    return {"auc": float(M.auc(yy, s)), "avg_precision": M.ap(yy, s), "top500_cve_id": int(yy[r <= 500].sum()),
            "top250_cve_id": int(yy[r <= 250].sum()), "work50_cve_id": int(pos[math.ceil(len(pos) / 2) - 1]),
            "median_rank_cve_id": float(np.median(pos)), "top500_best": int(b), "top500_worst": int(w),
            "top500_expected": float(e), "tied": int(sz)}


import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.ensemble import HistGradientBoostingClassifier
W = re.compile(r"exploited in the wild|actively exploited|known to be exploited|has been exploited|"
               r"may have been exploited|is being exploited|CISA|KEV", re.I)


def c1(seed):  # copied from audit/scratch/p3_rederive.py text()/model() (exact match to producer in phase-3 audit)
    tf = TfidfVectorizer(ngram_range=(1, 2), min_df=8, max_features=30000, sublinear_tf=True, stop_words="english")
    Xtr = tf.fit_transform([W.sub(" ", s) for s in tr.description.fillna("")])
    Xte = tf.transform([W.sub(" ", s) for s in te.description.fillna("")])
    lr = lambda: LogisticRegression(C=2, class_weight="balanced", max_iter=500)
    oof = np.zeros(len(tr))
    for i, j in StratifiedKFold(5, shuffle=True, random_state=seed).split(Xtr, ytr):
        oof[j] = lr().fit(Xtr[i], ytr[i]).predict_proba(Xtr[j])[:, 1]
    st = lr().fit(Xtr, ytr).predict_proba(Xte)[:, 1]
    A, B = tr.assign(txt=oof)[C1], te.assign(txt=st)[C1]
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                          l2_regularization=5.0, early_stopping=False, random_state=seed
                                          ).fit(A, ytr).predict_proba(B)[:, 1]


if __name__ == "__main__":
    sc = Parallel(n_jobs=5)(delayed(c1)(s) for s in range(5))
    np.savez(S + "r_scores.npz", *sc)
    per = [mets(s) for s in sc]
    out["C1_per_seed"] = per
    out["C1_median"] = {k: float(np.median([r[k] for r in per])) for k in per[0]}
    out["C1_min"] = {k: min(r[k] for r in per) for k in ("auc", "top500_cve_id")}
    out["C1_max"] = {k: max(r[k] for r in per) for k in ("auc", "top500_cve_id")}
    ep = te.epss.astype(float).fillna(-1).to_numpy()
    anyx = te[F].fillna(0).astype(float).max(axis=1).to_numpy()
    base = {"exploit_then_epss": anyx * 10 + np.clip(ep, 0, None), "epss": ep,
            "cvss3": te.cvss3_score.fillna(-1).to_numpy(), "assigner_only": te.asg_rate.to_numpy()}
    out["baselines"] = {n: mets(s) for n, s in base.items()}
    # bootstrap, own loop, same resamples for all
    rng = np.random.default_rng(0); idx = []
    while len(idx) < 2000:
        i = rng.integers(0, len(y), len(y))
        if y[i].sum(): idx.append(i)
    vec = {"C1": sc[0], **base}
    def bs(n):
        s = vec[n]; rows = []
        for i in idx:
            yy, ss, ii = y[i], s[i], ids[i]; o = np.lexsort((ii, -ss))
            rows.append((yy[o[:500]].sum(), M.tie_topk(yy, ss, 500)[1], M.auc(yy, ss)))
        a = np.array(rows, float)
        return n, {k: np.percentile(a[:, j], [2.5, 97.5]).tolist() for j, k in enumerate(("top500_cve_id", "top500_expected", "auc"))}, a[:, 2]
    res = Parallel(n_jobs=5)(delayed(bs)(n) for n in vec)
    out["ci"] = {n: c for n, c, _ in res}
    aucs = {n: a for n, _, a in res}
    out["paired_auc_diff_C1_minus"] = {n: np.percentile(aucs["C1"] - aucs[n], [2.5, 50, 97.5]).tolist() for n in base}
    json.dump(out, open(S + "r_result.json", "w"), indent=1, default=float)
    print(json.dumps({k: out[k] for k in ("train_rows", "train_positives", "test_rows", "test_positives", "overlap")}))
