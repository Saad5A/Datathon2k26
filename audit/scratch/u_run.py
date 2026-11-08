"""Remaining-claims audit: first-pass structured/leaky rows, C1 ablations, C2/C3 per-seed scores.
Own code path: auditor pool (p3_pool.parquet), structured features rebuilt from the raw CSV with numpy/Counter,
no import from src/. Saves every score vector to u_scores.npz; metrics are done in u_check.py."""
import re, sys, collections, numpy as np, pandas as pd
from joblib import Parallel, delayed
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
p = pd.read_parquet(S + "p3_pool.parquet")
VEC = ["attack_vector", "attack_complexity", "privileges_required", "user_interaction", "scope",
       "confidentiality_impact", "integrity_impact", "availability_impact"]
raw = pd.read_csv(R + ".data/data/vulnerabilities.csv", usecols=["cve_id", *VEC, "cwe_ids", "n_affected_cpes"],
                  dtype={c: str for c in ["cve_id", *VEC, "cwe_ids"]})
raw = raw.set_index("cve_id")
assert raw.index.is_unique
for c in [*VEC, "cwe_ids", "n_affected_cpes"]:
    p[c] = raw[c].reindex(p.cve_id).to_numpy()
p["cwe1"] = [("" if not isinstance(x, str) else x).split(";")[0] for x in p.cwe_ids]

# ---- first-pass structured features, vocabularies over the whole pool (as the first pass did) ----
FP = ["cvss3"]
p["cvss3"] = p.cvss3_score.fillna(-1.0)
for c in VEC:
    vals = p[c].to_numpy(object); ok = np.array([isinstance(x, str) for x in vals])
    cats = np.array(sorted(set(vals[ok])), dtype=object)
    code = np.full(len(p), -1, np.int8); code[ok] = np.searchsorted(cats, vals[ok].astype(str))
    p[c + "_c"] = code; FP.append(c + "_c")
cnt = collections.Counter(p.cwe1)
top40 = [c for c, _ in cnt.most_common(40)]
srt = sorted(cnt.values(), reverse=True); print("cwe count at 40/41:", srt[39], srt[40])
for c in top40:
    p["cwe_" + c] = (p.cwe1 == c).astype(int); FP.append("cwe_" + c)
p["ncpe"] = p.n_affected_cpes.astype(float)

SIG = ["epss_f", "exploitdb", "metasploit", "nuclei", "poc_github", "anyx", "nx"]
ASG = ["asg_rate", "asg_kev"]
W = re.compile(r"exploited in the wild|actively exploited|known to be exploited|has been exploited|"
               r"may have been exploited|is being exploited|CISA|KEV", re.I)
FOLDS = {"fold1": ("2024-01", "2024-12", "2024-12-31", "2025-01", "2025-09"),
         "fold2": ("2024-07", "2025-03", "2025-03-31", "2025-04", "2025-09")}


def get(name):
    if name == "primary":
        tr = p[p.month < "2025-01"].reset_index(drop=True); te = p[p.month >= "2025-01"].reset_index(drop=True)
        return tr, te, tr.y.to_numpy()
    a, b, cap, c, d = FOLDS[name]
    tr = p[(p.month >= a) & (p.month <= b)].reset_index(drop=True); te = p[(p.month >= c) & (p.month <= d)].reset_index(drop=True)
    kd = pd.to_datetime(tr.kev_date).to_numpy(dtype="datetime64[D]"); me = tr.mend.to_numpy().astype("datetime64[D]")
    ytr = ((~np.isnat(kd)) & (kd > me) & (kd <= np.minimum(me + 365, np.datetime64(cap)))).astype(int)
    return tr, te, ytr


def text(name, seed, mask):
    tr, te, ytr = get(name)
    f = (lambda s: W.sub(" ", s)) if mask else (lambda s: s)
    tf = TfidfVectorizer(ngram_range=(1, 2), min_df=8, max_features=30000, sublinear_tf=True, stop_words="english")
    Xtr = tf.fit_transform([f(s) for s in tr.description.fillna("")]); Xte = tf.transform([f(s) for s in te.description.fillna("")])
    lr = lambda: LogisticRegression(C=2, class_weight="balanced", max_iter=500)
    oof = np.zeros(len(tr))
    for i, j in StratifiedKFold(5, shuffle=True, random_state=seed).split(Xtr, ytr):
        oof[j] = lr().fit(Xtr[i], ytr[i]).predict_proba(Xtr[j])[:, 1]
    return (name, seed, mask), (oof, lr().fit(Xtr, ytr).predict_proba(Xte)[:, 1])


def hgb(A, y, B, seed, es):
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                          l2_regularization=5.0, early_stopping=es, random_state=seed).fit(A, y).predict_proba(B)[:, 1]


def struct3(tr, te):
    """Phase 3 plus_structured: cvss3 blank->0 + indicator, one-hot vector fields ('blank' for NaN), top-40 cwe1, train vocab."""
    def cats(c): return sorted(set(tr[c].fillna("blank").astype(str)))
    voc = {c: cats(c) for c in VEC}; cw = [c for c, _ in collections.Counter(tr.cwe1).most_common(40)]
    def build(df):
        d = {"s_cvss3": df.cvss3_score.fillna(0).to_numpy(), "s_cvss3_missing": df.cvss3_score.isna().astype(int).to_numpy()}
        for c in VEC:
            v = df[c].fillna("blank").astype(str).to_numpy()
            for k in voc[c]: d[f"s_{c}_{k}"] = (v == k).astype(float)
        for k in cw: d[f"s_cwe_{k}"] = (df.cwe1 == k).astype(int).to_numpy()
        return pd.DataFrame(d)
    return build(tr), build(te)


if __name__ == "__main__":
    jobs = [("primary", 0, False)] + [(f, s, m) for f in FOLDS for s in range(5) for m in (True, False)]
    T = dict(Parallel(n_jobs=10, verbose=2)(delayed(text)(*j) for j in jobs))
    out = {}
    # first-pass rows: unmasked text, fold seed 0, HGB seeds 0,1,2, early stopping 'auto', mean of predictions
    tr, te, ytr = get("primary"); oof, st = T[("primary", 0, False)]
    A, B = tr.assign(txt=oof), te.assign(txt=st)
    spec = {"hgb_signals_struct": SIG + FP, "hgb_signals_struct_assigner": SIG + FP + ASG,
            "hgb_all_text": SIG + FP + ASG + ["txt"], "leaky_ncpe": SIG + FP + ASG + ["txt", "ncpe"],
            "best_check": SIG + ASG + ["txt"]}
    for n, cols in spec.items():
        out[f"primary.{n}"] = np.mean([hgb(A[cols], ytr, B[cols], s, "auto") for s in (0, 1, 2)], axis=0)
        print(n, flush=True)
    C1 = SIG + ASG + ["txt"]; C2 = SIG + ["asg24_rate", "asg24_kev", "txt"]
    abl = {"drop_signals": (ASG + ["txt"], True, False, False), "drop_assigner": (SIG + ["txt"], True, False, False),
           "drop_text": (SIG + ASG, True, False, False), "unmasked_text": (C1, False, False, False),
           "plus_structured": (C1, True, True, False), "early_stopping_on": (C1, True, False, True), "C1": (C1, True, False, False)}
    for f in FOLDS:
        tr, te, ytr = get(f); X3 = struct3(tr, te)
        for s in range(5):
            for n, (cols, mask, st_, es) in abl.items():
                oof, sc = T[(f, s, mask)]
                A, B = tr.assign(txt=oof)[cols].reset_index(drop=True), te.assign(txt=sc)[cols].reset_index(drop=True)
                if st_: A, B = pd.concat([A, X3[0]], axis=1), pd.concat([B, X3[1]], axis=1)
                out[f"{f}.{n}.s{s}"] = hgb(A, ytr, B, s, es)
            oof, sc = T[(f, s, True)]
            A, B = tr.assign(txt=oof)[C2], te.assign(txt=sc)[C2]
            out[f"{f}.C2.s{s}"] = hgb(A, ytr, B, s, False)
            A, B = A.copy(), B.copy()
            for X, D in ((A, tr), (B, te)):
                X["epss_f"] = D.epss.fillna(0).to_numpy(); X["epss_missing"] = D.epss.isna().astype(int).to_numpy()
            scl = StandardScaler().fit(A)
            out[f"{f}.C3.s{s}"] = LogisticRegression(max_iter=5000).fit(scl.transform(A), ytr).predict_proba(scl.transform(B))[:, 1]
            print(f, s, flush=True)
    np.savez(S + "u_scores.npz", **out)
    print("saved", len(out))
