import json, sys, numpy as np, pandas as pd
sys.path.insert(0, "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch")
from a3_best import p, COLS
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.ensemble import HistGradientBoostingClassifier as H
import mymetrics as M
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"
cl = json.load(open(R + "results/claims_model.json")); res = {}
def chk(key, val, tol=1e-6):
    c = cl[key]["value"]; ok = abs(c - val) <= tol; res[key] = bool(ok)
    print(f"{key:50s} mine={val!s:22.20s} claimed={c!s:22.20s} {'OK' if ok else 'MISMATCH'}", flush=True)
te = p[p.month >= "2025-01"]
for m, g in te.groupby("month"):
    end = pd.Timestamp(m + "-01") + pd.offsets.MonthEnd(0)
    chk(f"f.{m}.positives", int(g.y.sum())); chk(f"f.{m}.window_days", (min(end + pd.Timedelta(days=365), pd.Timestamp("2025-12-31")) - end).days)
tr = p[p.month < "2025-01"].reset_index(drop=True); te = te.reset_index(drop=True); ytr = tr.y.to_numpy(); y = te.y.to_numpy()
tf = TfidfVectorizer(ngram_range=(1, 2), min_df=8, max_features=30000, sublinear_tf=True, stop_words="english")
Xtr = tf.fit_transform(tr.description.fillna("")); Xte = tf.transform(te.description.fillna(""))
lr = lambda: LogisticRegression(C=2, class_weight="balanced", max_iter=500)
oof = np.zeros(len(tr))
for a, b in StratifiedKFold(5, shuffle=True, random_state=0).split(Xtr, ytr): oof[b] = lr().fit(Xtr[a], ytr[a]).predict_proba(Xtr[b])[:, 1]
st = lr().fit(Xtr, ytr).predict_proba(Xte)[:, 1]
A, B = tr.assign(txt=oof)[COLS], te.assign(txt=st)[COLS]
kw = dict(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40, l2_regularization=5.0)
for s in range(3): chk(f"c.best.n_iter_seed{s}", H(random_state=s, **kw).fit(A, ytr).n_iter_)
s = np.mean([H(random_state=r, early_stopping=False, **kw).fit(A, ytr).predict_proba(B)[:, 1] for r in range(3)], axis=0)
fp = pd.DataFrame({"y": y, "s": s}).sort_values("s", ascending=False).y.to_numpy()
chk("c.best.top500_no_early_stop", int(fp[:500].sum())); chk("c.best.auc_no_early_stop", M.auc(y, s)); chk("c.best.avg_precision_no_early_stop", M.ap(y, s))
print("c no-early-stop top500 by cve_id", M.top_by_id(y, s, te.cve_id.to_numpy()))
json.dump(res, open(R + "audit/scratch/a6_result.json", "w"), indent=1)
