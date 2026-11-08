"""Granite-final audit: independent C1/G1/G2 on both folds x 5 seed sets + G2 label permutation (fold1, 10 shuffles).
Does not import src/. Pool = auditor's p3_pool.parquet (audited in Phase 3). Masking/TF-IDF/HGB copied from p3_rederive.py."""
import json, re, sys, numpy as np, pandas as pd
from joblib import Parallel, delayed
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.ensemble import HistGradientBoostingClassifier as HGB

R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
sys.path.insert(0, S)
from mymetrics import auc, tie_topk

p = pd.read_parquet(S + "p3_pool.parquet")
F = ["exploitdb", "metasploit", "nuclei", "poc_github"]
COLS = ["epss_f", *F, "anyx", "nx", "asg_rate", "asg_kev", "txt"]
W = re.compile(r"exploited in the wild|actively exploited|known to be exploited|has been exploited|"
               r"may have been exploited|is being exploited|CISA|KEV", re.I)
FOLDS = {"fold1": ("2024-01", "2024-12", "2024-12-31", "2025-01", "2025-09"),
         "fold2": ("2024-07", "2025-03", "2025-03-31", "2025-04", "2025-09")}
E = pd.read_parquet(R + "data_cache/granite_embeddings.parquet")
EI = pd.Index(E.cve_id); EM = np.stack(E.vector.to_numpy()).astype(np.float32)


def fold(name):
    a, b, cap, c, d = FOLDS[name]
    tr = p[(p.month >= a) & (p.month <= b)].reset_index(drop=True)
    te = p[(p.month >= c) & (p.month <= d)].reset_index(drop=True)
    kd = pd.to_datetime(tr.kev_date).to_numpy(dtype="datetime64[D]")
    me = tr.mend.to_numpy().astype("datetime64[D]")
    ytr = ((~np.isnat(kd)) & (kd > me) & (kd <= np.minimum(me + 365, np.datetime64(cap)))).astype(int)
    return tr, te, ytr


def lr():
    return LogisticRegression(C=2, class_weight="balanced", max_iter=500)


def oof_test(Xtr, Xte, ytr, seed):
    o = np.zeros(len(ytr))
    for i, j in StratifiedKFold(5, shuffle=True, random_state=seed).split(Xtr, ytr):
        o[j] = lr().fit(Xtr[i], ytr[i]).predict_proba(Xtr[j])[:, 1]
    return o, lr().fit(Xtr, ytr).predict_proba(Xte)[:, 1]


def hgb(A, B, y, seed):
    return HGB(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40, l2_regularization=5.0,
               early_stopping=False, random_state=seed).fit(A, y).predict_proba(B)[:, 1]


def mets(y, s, ids):
    o = np.lexsort((ids, -s)); r = np.empty(len(s), int); r[o] = np.arange(1, len(s) + 1); pos = np.sort(r[y == 1])
    return {"auc": float(auc(y, s)), "top500": int(y[r <= 500].sum()), "work50": int(pos[int(np.ceil(len(pos) / 2)) - 1]),
            "top500_expected": float(tie_topk(y, s, 500)[1])}


def task(name, seed, perm=None):
    tr, te, ytr = fold(name)
    if perm is not None:
        ytr = np.random.default_rng(perm).permutation(ytr)
    tf = TfidfVectorizer(ngram_range=(1, 2), min_df=8, max_features=30000, sublinear_tf=True, stop_words="english")
    Ttr = tf.fit_transform([W.sub(" ", s) for s in tr.description.fillna("")])
    Tte = tf.transform([W.sub(" ", s) for s in te.description.fillna("")])
    t_o, t_s = oof_test(Ttr, Tte, ytr, seed)
    gi, ge = EI.get_indexer(tr.cve_id), EI.get_indexer(te.cve_id); assert (gi >= 0).all() and (ge >= 0).all()
    g_o, g_s = oof_test(EM[gi], EM[ge], ytr, seed)
    base_tr, base_te = tr.assign(txt=t_o)[COLS], te.assign(txt=t_s)[COLS]
    X = {"C1": (base_tr, base_te), "G1": (tr.assign(txt=g_o)[COLS], te.assign(txt=g_s)[COLS]),
         "G2": (base_tr.assign(txt_g=g_o), base_te.assign(txt_g=g_s))}
    if perm is not None:
        X = {"G2": X["G2"]}
    y, ids = te.y.to_numpy(), te.cve_id.to_numpy()
    out = {}
    for n, (A, B) in X.items():
        s = hgb(A, B, ytr, seed); out[n] = mets(y, s, ids)
        if perm is None:
            np.save(S + f"gf_{n}_{name}_s{seed}.npy", s)
    return name, seed, perm, out


if __name__ == "__main__":
    info = {}
    for f in FOLDS:
        tr, te, ytr = fold(f)
        info[f] = {"train_rows": len(tr), "train_pos": int(ytr.sum()), "test_rows": len(te), "test_pos": int(te.y.sum()),
                   "id_overlap": len(set(tr.cve_id) & set(te.cve_id)), "train_max_month": tr.month.max(), "test_min_month": te.month.min()}
    print(info, flush=True)
    jobs = [(f, s, None) for f in FOLDS for s in range(5)] + [("fold1", 0, 2000 + i) for i in range(10)]
    out = Parallel(n_jobs=10, verbose=5)(delayed(task)(*j) for j in jobs)
    json.dump({"info": info, "runs": [{"fold": f, "seed": s, "perm": pm, "out": o} for f, s, pm, o in out]},
              open(S + "gf_rederive_result.json", "w"), indent=1)
    print("done")
