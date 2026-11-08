"""Independent retrain of signals+assigner+text, permutation test, wording-overlap check."""
import json, re, sys, numpy as np, pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.ensemble import HistGradientBoostingClassifier
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
sys.path.insert(0, S)
p = pd.read_parquet(S + "my_pool2.parquet")
F = ["exploitdb", "metasploit", "nuclei", "poc_github"]
p[F] = p[F].fillna(0).astype(float)
p["epss_f"] = p.epss.fillna(-1).astype(float); p["anyx"] = p[F].max(axis=1); p["nx"] = p[F].sum(axis=1)
COLS = ["epss_f", *F, "anyx", "nx", "asg_rate", "asg_kev", "txt"]
for c in COLS: assert c not in ("nvd_status", "n_affected_cpes", "n_references", "cvss3_score", "cvss3_source")

def auc(y, s):
    from scipy.stats import rankdata
    r = rankdata(s); n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)

def run(tr, te, ytr, seeds=(0, 1, 2), fold_seed=0):
    tf = TfidfVectorizer(ngram_range=(1, 2), min_df=8, max_features=30000, sublinear_tf=True, stop_words="english")
    Xtr = tf.fit_transform(tr.description.fillna("")); Xte = tf.transform(te.description.fillna(""))
    lr = lambda: LogisticRegression(C=2, class_weight="balanced", max_iter=500)
    oof = np.zeros(len(tr))
    for a, b in StratifiedKFold(5, shuffle=True, random_state=fold_seed).split(Xtr, ytr):
        oof[b] = lr().fit(Xtr[a], ytr[a]).predict_proba(Xtr[b])[:, 1]
    txt_te = lr().fit(Xtr, ytr).predict_proba(Xte)[:, 1]
    A = tr.assign(txt=oof)[COLS]; B = te.assign(txt=txt_te)[COLS]
    pr = [HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                         l2_regularization=5.0, random_state=s).fit(A, ytr).predict_proba(B)[:, 1] for s in seeds]
    return np.mean(pr, axis=0), txt_te

def top_by_id(y, s, ids, k=500):
    o = np.lexsort((ids, -s)); return int(y[o[:k]].sum()), o

if __name__ == "__main__":
    tr = p[p.month < "2025-01"].reset_index(drop=True); te = p[p.month >= "2025-01"].reset_index(drop=True)
    y, ids = te.y.to_numpy(), te.cve_id.to_numpy()
    s, txt = run(tr, te, tr.y.to_numpy())
    np.save(S + "best_scores.npy", s)
    h, o = top_by_id(y, s, ids)
    print("BEST retrain: top500_cve_id", h, "top250", int(y[o[:250]].sum()), "auc", auc(y, s), "text-only auc", auc(y, txt))
    # wording overlap
    W = r"exploited in the wild|actively exploited|known to be exploited|has been exploited|may have been exploited|is being exploited|CISA|KEV"
    hit = te.description.fillna("").str.contains(W, case=False, regex=True).to_numpy()
    in500 = np.zeros(len(te), bool); in500[o[:500]] = True
    print("test wording rows", hit.sum(), "positives with wording", int((hit & (y == 1)).sum()),
          "wording positives in top500", int((hit & (y == 1) & in500).sum()), "wording rows in top500", int((hit & in500).sum()))
    print("AUC excluding wording rows", auc(y[~hit], s[~hit]), "top500 hits without wording positives", int((in500 & (y == 1) & ~hit).sum()))
    # permutation test: shuffle train labels
    rng = np.random.default_rng(123)
    for i in range(3):
        sp, _ = run(tr, te, rng.permutation(tr.y.to_numpy()), seeds=(0,))
        print(f"PERM {i}: auc {auc(y, sp):.4f} top500 {top_by_id(y, sp, ids)[0]}")
