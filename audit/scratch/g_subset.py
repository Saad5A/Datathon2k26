"""Auditor re-derivation for src/model/granite_subset_eval.py (independent path: raw KEV labels, own AUC)."""
import json
import re
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"
pool = pd.read_parquet(R + "data_cache/backtest_pool.parquet")
kev = pd.read_csv(R + ".data/data/known_exploited.csv", usecols=["cve_id", "date_added"], parse_dates=["date_added"])
kev = kev.groupby("cve_id").date_added.min()
txt = pd.read_parquet(R + "data_cache/descriptions_to_embed.parquet").set_index("cve_id").text
sub = pd.read_parquet(R + "data_cache/granite_embeddings_watsonx_subset.parquet", columns=["cve_id"]).cve_id.astype(str)

da = pool.cve_id.map(kev)
se = pd.to_datetime(pool.snap_end)


def lab(cap):
    lim = (se + pd.Timedelta(days=365)).clip(upper=pd.Timestamp(cap))
    return ((da > se) & (da <= lim)).astype(int).to_numpy()


y_pool = lab("2025-12-31")
print("pool labels == raw-KEV labels:", (y_pool == pool.y.to_numpy()).all(), "base rate", y_pool.mean().round(5))

# own masking from the description column, compare with the embed input text
pat = re.compile(r"exploited in the wild|actively exploited|known to be exploited|has been exploited|"
                 r"may have been exploited|is being exploited|CISA|KEV", re.I)
own = pool.description.fillna("").map(lambda s: pat.sub(" ", s))
print("embed text == own-masked pool description:", (own.to_numpy() == txt.reindex(pool.cve_id).to_numpy()).mean())
print("residual exploitation wording in embed text:", txt.str.contains(pat).sum())

FOLDS = {"fold1": (("2024-01", "2024-12"), "2024-12-31", ("2025-01", "2025-09"), 220),
         "fold2": (("2024-07", "2025-03"), "2025-03-31", ("2025-04", "2025-09"), 150)}
need = []
masks = {}
for f, (trm, cap, tem, nneg) in FOLDS.items():
    trmask = ((pool.ym >= trm[0]) & (pool.ym <= trm[1])).to_numpy()
    temask = ((pool.ym >= tem[0]) & (pool.ym <= tem[1])).to_numpy()
    ycap = lab(cap)
    masks[f] = (trmask, temask, ycap)
    te = pool[temask]
    need += te.cve_id[y_pool[temask] == 1].tolist()
    need += te.cve_id[y_pool[temask] == 0].sample(n=nneg, random_state=0).tolist()
    need += pool.cve_id[trmask & (ycap == 1)].tolist()
evalslice = sorted(set(need) - set(sub))
print("reconstructed evalslice ids:", len(evalslice), "(meta n_rows 466)")
cov = set(sub) | set(evalslice)
print("covered ids:", len(cov), "subset 1500 unique:", sub.nunique(), "subset in pool:", sub.isin(pool.cve_id).sum())
print("subset id range:", sub.min(), sub.max(), "| pool sorted by cve_id:", pool.cve_id.is_monotonic_increasing)


def auc(y, s):
    y = np.asarray(y); r = rankdata(s); n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def lr(X, y):
    return LogisticRegression(C=2, class_weight="balanced", max_iter=500).fit(X, y)


def tf():
    return TfidfVectorizer(ngram_range=(1, 2), min_df=8, max_features=30000, sublinear_tf=True, stop_words="english")


rng = np.random.default_rng(0)
out = {}
for f, (trmask, temask, ycap) in masks.items():
    c = pool.cve_id.isin(cov).to_numpy()
    tr, te = trmask & c, temask & c
    ytr, yte = ycap[tr], y_pool[te]
    ids_tr, ids_te = set(pool.cve_id[tr]), set(pool.cve_id[te])
    from_sub_te = pool.cve_id[te].isin(sub).sum()
    fut_pos_neg = int(((y_pool[tr] == 1) & (ytr == 0)).sum())
    print(f"\n{f}: train {tr.sum()} pos {ytr.sum()} | test {te.sum()} pos {yte.sum()} of {y_pool[temask].sum()} "
          f"| test rows from first-1500 subset {from_sub_te} | id overlap {len(ids_tr & ids_te)} "
          f"| train rows capped-0 but pool-positive {fut_pos_neg} | full-fold train {trmask.sum()} pos {ycap[trmask].sum()}")
    print(f"  covered positive rate train {ytr.mean():.3f} test {yte.mean():.3f}  vs full test {y_pool[temask].mean():.4f}")
    t1 = tf(); Xtr = t1.fit_transform(txt.reindex(pool.cve_id[tr]).fillna("")); Xte = t1.transform(txt.reindex(pool.cve_id[te]).fillna(""))
    s = lr(Xtr, ytr).predict_proba(Xte)[:, 1]
    a = auc(yte, s)
    o = np.argsort(-s, kind="stable")
    print(f"  TF-IDF(subset-fit) vocab {len(t1.vocabulary_)} AUC {a:.10f} top50 {yte[o[:50]].sum()} top100 {yte[o[:100]].sum()} top500 {yte[o[:500]].sum()}")
    bs = []
    for _ in range(1000):
        i = rng.integers(0, len(yte), len(yte))
        if 0 < yte[i].sum() < len(i):
            bs.append(auc(yte[i], s[i]))
    print(f"  bootstrap 95% CI TF-IDF AUC {np.percentile(bs, 2.5):.3f}-{np.percentile(bs, 97.5):.3f}")
    # permutation: shuffle train labels
    pa = [auc(yte, lr(Xtr, rng.permutation(ytr)).predict_proba(Xte)[:, 1]) for _ in range(5)]
    print(f"  permuted-label TF-IDF AUC {np.round(pa, 3)}")
    # fairness: TF-IDF fitted on the FULL fold train, scored on the same covered test rows
    t2 = tf(); Xf = t2.fit_transform(txt.reindex(pool.cve_id[trmask]).fillna(""))
    sf = lr(Xf, ycap[trmask]).predict_proba(t2.transform(txt.reindex(pool.cve_id[te]).fillna("")))[:, 1]
    print(f"  TF-IDF(full-train fit) vocab {len(t2.vocabulary_)} AUC on covered test {auc(yte, sf):.4f}")
    # covered test with only the random negatives (drop first-1500 negatives) for case-control view
    rnd = (~pool.cve_id[te].isin(sub)).to_numpy() | (yte == 1)
    print(f"  covered test without first-1500 rows: n {rnd.sum()} pos {yte[rnd].sum()} TF-IDF(subset) AUC {auc(yte[rnd], s[rnd]):.4f} full-fit {auc(yte[rnd], sf[rnd]):.4f}")
    out[f] = a
print("\nmean TF-IDF AUC check:", out)
