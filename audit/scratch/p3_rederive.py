"""Phase 3 audit: independent re-derivation of C1/C2/C3 on both folds, 5 seed sets, plus permutation and subsets.
Does not import src/. Pool = auditor's my_pool2.parquet (verified equal to the producer cache in the harness audit)."""
import json, re, sys, numpy as np, pandas as pd
from joblib import Parallel, delayed
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
sys.path.insert(0, S)
from mymetrics import auc, tie_topk

p = pd.read_parquet(S + "my_pool2.parquet")
F = ["exploitdb", "metasploit", "nuclei", "poc_github"]
p[F] = p[F].fillna(0).astype(float)
p["epss_f"] = p.epss.fillna(-1).astype(float); p["anyx"] = p[F].max(axis=1); p["nx"] = p[F].sum(axis=1)
SIG = ["epss_f", *F, "anyx", "nx"]

# ---- 24-month assigner window, string dates ----
v = pd.read_parquet(S + "vuln_min.parquet")
v["d"] = v.published.str[:10]
kev = pd.read_csv(R + ".data/data/known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str)
assert kev.date_added.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
kev = kev.merge(v[["cve_id", "assigner", "d"]], on="cve_id", how="left")


def window(m, kv):
    start = m + "-01"; lo = f"{int(m[:4]) - 2}{m[4:]}-01"
    kc = kv[(kv.date_added >= lo) & (kv.date_added < start) & kv.assigner.notna()].assigner.value_counts()
    pc = v[(v.d >= lo) & (v.d < start)].assigner.value_counts()
    return kc, pc, lo, start


def add24(kv, suffix):
    rate, cnt = np.zeros(len(p)), np.zeros(len(p))
    for m in sorted(p.month.unique()):
        kc, pc, _, _ = window(m, kv)
        idx = np.where(p.month == m)[0]; a = p.assigner.iloc[idx]
        k = a.map(kc).fillna(0); cnt[idx] = k.to_numpy(); rate[idx] = (k / (a.map(pc).fillna(0) + 20)).to_numpy()
    p["asg24_rate" + suffix], p["asg24_kev" + suffix] = rate, cnt


kev21 = kev[kev.d >= "2021-01-01"]          # producer's stated definition (CVE published 2021+)
add24(kev21, ""); add24(kev, "_all")       # variant: every KEV addition in the window
p.to_parquet(S + "p3_pool.parquet")

W = re.compile(r"exploited in the wild|actively exploited|known to be exploited|has been exploited|"
               r"may have been exploited|is being exploited|CISA|KEV", re.I)
FOLDS = {"fold1": ("2024-01", "2024-12", "2024-12-31", "2025-01", "2025-09"),
         "fold2": ("2024-07", "2025-03", "2025-03-31", "2025-04", "2025-09")}
CAND = {"C1": ("hgb", SIG + ["asg_rate", "asg_kev", "txt"]), "C2": ("hgb", SIG + ["asg24_rate", "asg24_kev", "txt"]),
        "C3": ("lr", SIG + ["asg24_rate", "asg24_kev", "txt"]),
        "C2_allkev": ("hgb", SIG + ["asg24_rate_all", "asg24_kev_all", "txt"])}


def fold(name):
    a, b, cap, c, d = FOLDS[name]
    tr = p[(p.month >= a) & (p.month <= b)].reset_index(drop=True)
    te = p[(p.month >= c) & (p.month <= d)].reset_index(drop=True)
    kd = pd.to_datetime(tr.kev_date).to_numpy(dtype="datetime64[D]")
    me = tr.mend.to_numpy().astype("datetime64[D]")
    lim = np.minimum(me + 365, np.datetime64(cap))
    ytr = ((~np.isnat(kd)) & (kd > me) & (kd <= lim)).astype(int)
    return tr, te, ytr


def lr_text():
    return LogisticRegression(C=2, class_weight="balanced", max_iter=500)


def text(tr, te, ytr, seed):
    tf = TfidfVectorizer(ngram_range=(1, 2), min_df=8, max_features=30000, sublinear_tf=True, stop_words="english")
    Xtr = tf.fit_transform([W.sub(" ", s) for s in tr.description.fillna("")])
    Xte = tf.transform([W.sub(" ", s) for s in te.description.fillna("")])
    oof = np.zeros(len(tr))
    for i, j in StratifiedKFold(5, shuffle=True, random_state=seed).split(Xtr, ytr):
        oof[j] = lr_text().fit(Xtr[i], ytr[i]).predict_proba(Xtr[j])[:, 1]
    return oof, lr_text().fit(Xtr, ytr).predict_proba(Xte)[:, 1]


def model(kind, cols, tr, te, ytr, oof, st, seed):
    A, B = tr.assign(txt=oof)[cols].copy(), te.assign(txt=st)[cols].copy()
    if kind == "hgb":
        return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                              l2_regularization=5.0, early_stopping=False, random_state=seed
                                              ).fit(A, ytr).predict_proba(B)[:, 1]
    for X, D in ((A, tr), (B, te)):
        X["epss_f"] = D.epss.fillna(0).to_numpy(); X["epss_missing"] = D.epss.isna().astype(int).to_numpy()
    sc = StandardScaler().fit(A)
    return LogisticRegression(max_iter=5000).fit(sc.transform(A), ytr).predict_proba(sc.transform(B))[:, 1]


def ranks_id(s, ids):
    o = np.lexsort((ids, -s)); r = np.empty(len(s), int); r[o] = np.arange(1, len(s) + 1); return r


def mets(y, s, ids):
    r = ranks_id(s, ids); pos = np.sort(r[y == 1])
    return {"auc": float(auc(y, s)), "top500": int((y[r <= 500]).sum()), "work50": int(pos[int(np.ceil(len(pos) / 2)) - 1]),
            "top500_expected": float(tie_topk(y, s, 500)[1])}


def task(name, seed, perm=None):
    tr, te, ytr = fold(name)
    if perm is not None:
        ytr = np.random.default_rng(perm).permutation(ytr)
    oof, st = text(tr, te, ytr, seed)
    y, ids = te.y.to_numpy(), te.cve_id.to_numpy()
    out = {}
    for c, (kind, cols) in CAND.items():
        if perm is not None and c != "C1":
            continue
        s = model(kind, cols, tr, te, ytr, oof, st, seed)
        out[c] = mets(y, s, ids)
        if c == "C1":
            m = (te.asg_kev == 0).to_numpy()
            out[c]["unseen_rows"], out[c]["unseen_pos"] = int(m.sum()), int(y[m].sum())
            out[c]["unseen_auc"] = float(auc(y[m], s[m]))
            if perm is None:
                np.save(S + f"p3_C1_{name}_s{seed}.npy", s)
    return name, seed, perm, out


if __name__ == "__main__":
    res = {}
    for f in FOLDS:
        tr, te, ytr = fold(f)
        y, ids = te.y.to_numpy(), te.cve_id.to_numpy()
        res[f] = {"train_rows": len(tr), "train_pos": int(ytr.sum()), "train_pos_uncapped": int(tr.y.sum()),
                  "test_rows": len(te), "test_pos": int(y.sum()),
                  "exploit_then_epss": mets(y, (te.anyx * 10 + te.epss_f.clip(lower=0)).to_numpy(), ids),
                  "id_overlap": len(set(tr.cve_id) & set(te.cve_id))}
        print(f, {k: v for k, v in res[f].items()}, flush=True)
    jobs = [(f, s, None) for f in FOLDS for s in range(5)] + [("fold2", 0, 1000 + i) for i in range(10)]
    out = Parallel(n_jobs=10, verbose=5)(delayed(task)(*j) for j in jobs)
    res["runs"] = [{"fold": f, "seed": s, "perm": pm, "out": o} for f, s, pm, o in out]
    json.dump(res, open(S + "p3_result.json", "w"), indent=1)
    print("done")
