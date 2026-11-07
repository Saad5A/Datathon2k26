import json, math, sys, numpy as np, pandas as pd
sys.path.insert(0, "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch")
from a3_best import p, COLS
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier as H
import mymetrics as M
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
cl = json.load(open(R + "results/claims_model.json")); res = {}
def chk(key, val, tol=1e-6):
    c = cl[key]["value"]; ok = abs(c - val) <= tol; res[key] = bool(ok)
    print(f"{key:70s} mine={val!s:22.20s} claimed={c!s:22.20s} {'OK' if ok else 'MISMATCH'}", flush=True)
tr = p[p.month < "2025-01"].reset_index(drop=True); te = p[p.month >= "2025-01"].reset_index(drop=True)
y, ids = te.y.to_numpy(), te.cve_id.to_numpy(); ytr = tr.y.to_numpy()
tf = TfidfVectorizer(ngram_range=(1, 2), min_df=8, max_features=30000, sublinear_tf=True, stop_words="english")
Xtr = tf.fit_transform(tr.description.fillna("")); Xte = tf.transform(te.description.fillna(""))
txt = LogisticRegression(C=2, class_weight="balanced", max_iter=500).fit(Xtr, ytr).predict_proba(Xte)[:, 1]
def hgb(cols):
    return np.mean([H(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40, l2_regularization=5.0,
                      random_state=s).fit(tr[cols], ytr).predict_proba(te[cols])[:, 1] for s in (0, 1, 2)], axis=0)
sig = COLS[:7]; asg = ["asg_rate", "asg_kev"]
ep = te.epss_f.to_numpy()
scores = {"cvss3": te.cvss3_score.fillna(-1).to_numpy(), "epss": ep, "exploit_then_epss": te.anyx.to_numpy() * 10 + np.clip(ep, 0, None),
          "assigner_only": te.asg_rate.to_numpy(), "text_only": txt, "hgb_signals": hgb(sig), "hgb_signals_assigner": hgb(sig + asg),
          "hgb_signals_assigner_text": np.load(S + "best_scores.npy")}
for n in ("text_only", "hgb_signals", "hgb_signals_assigner"):
    s = scores[n]; o = np.lexsort((ids, -s)); rk = np.empty(len(o), int); rk[o] = np.arange(1, len(o) + 1)
    pos = np.sort(rk[y == 1]); b, e, w, sz = M.tie_topk(y, s, 500)
    for k, v in {"auc": M.auc(y, s), "avg_precision": M.ap(y, s), "top500_cve_id": int(y[o[:500]].sum()), "top250_cve_id": int(y[o[:250]].sum()),
                 "top500_best": b, "top500_expected": e, "top500_worst": w, "top500_tied_group": sz, "work50_cve_id": pos[math.ceil(len(pos) / 2) - 1]}.items():
        chk(f"primary.{n}.{k}", v)
    fp = pd.DataFrame({"y": y, "s": s}).sort_values("s", ascending=False).y.to_numpy()
    chk(f"primary.{n}.top500_first_pass_order", int(fp[:500].sum())); chk(f"primary.{n}.top1000_first_pass_order", int(fp[:1000].sum()))
    chk(f"primary.{n}.median_rank_first_pass_order", int(np.median(np.where(fp == 1)[0] + 1)))
# best model remaining point claims
s = scores["hgb_signals_assigner_text"]; o = np.lexsort((ids, -s)); rk = np.empty(len(o), int); rk[o] = np.arange(1, len(o) + 1)
pos = np.sort(rk[y == 1]); b, e, w, sz = M.tie_topk(y, s, 500)
for k, v in {"auc": M.auc(y, s), "avg_precision": M.ap(y, s), "top500_cve_id": int(y[o[:500]].sum()), "top250_cve_id": int(y[o[:250]].sum()),
             "top500_best": b, "top500_expected": e, "top500_worst": w, "top500_tied_group": sz, "work50_cve_id": pos[math.ceil(len(pos) / 2) - 1]}.items():
    chk(f"primary.hgb_signals_assigner_text.{k}", v)
fp = pd.DataFrame({"y": y, "s": s}).sort_values("s", ascending=False).y.to_numpy()
chk("primary.hgb_signals_assigner_text.top500_first_pass_order", int(fp[:500].sum()))
chk("primary.hgb_signals_assigner_text.top1000_first_pass_order", int(fp[:1000].sum()))
chk("primary.hgb_signals_assigner_text.median_rank_first_pass_order", int(np.median(np.where(fp == 1)[0] + 1)))

# ---- bootstrap: same scheme (default_rng(0), integers(0,n,n), 2000 draws, percentile 2.5/97.5), my own metric code
def mid_desc(s):
    u, inv, cnt = np.unique(-s, return_inverse=True, return_counts=True)
    endr = np.cumsum(cnt); return (endr - (cnt - 1) / 2)[inv]
def auc_fast(yy, s):
    r = len(s) + 1 - mid_desc(s); n1 = yy.sum(); n0 = len(yy) - n1
    return (r[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
def stats(yy, s):
    mr = np.sort(mid_desc(s)[yy == 1]); npos = len(mr)
    return {"top500_expected": M.tie_topk(yy, s, 500)[1], "top250_expected": M.tie_topk(yy, s, 250)[1], "auc": auc_fast(yy, s),
            "avg_precision": M.ap(yy, s), "median_rank_mid": float(np.median(mr)), "work50_mid": float(mr[math.ceil(npos / 2) - 1])}
rng = np.random.default_rng(0); idx = []
while len(idx) < 2000:
    i = rng.integers(0, len(y), len(y))
    if y[i].sum() == 0: continue
    idx.append(i)
for n, s in scores.items():
    rows = [stats(y[i], s[i]) for i in idx]
    for k in rows[0]:
        lo, hi = np.percentile([r[k] for r in rows], [2.5, 97.5])
        chk(f"primary.{n}.ci95_lo.{k}", lo); chk(f"primary.{n}.ci95_hi.{k}", hi)
json.dump(res, open(S + "a5_result.json", "w"), indent=1)
