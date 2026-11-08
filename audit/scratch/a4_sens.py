import json, numpy as np, pandas as pd, sys
sys.path.insert(0, "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch")
from a3_best import p, run, COLS
import mymetrics as M
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"
cl = json.load(open(R + "results/claims_model.json")); res = {}
def chk(key, val, tol=1e-6):
    c = cl[key]["value"]; ok = abs(c - val) <= tol; res[key] = bool(ok)
    print(f"{key:75s} mine={val!s:22.20s} claimed={c!s:22.20s} {'OK' if ok else 'MISMATCH'}", flush=True)
def cap_labels(df, cap):
    added = pd.to_datetime(df.kev_date).to_numpy().astype("datetime64[D]"); end = df.mend.to_numpy().astype("datetime64[D]")
    lim = np.minimum(end + np.timedelta64(365, "D"), np.datetime64(cap))
    return ((added > end) & (added <= lim)).astype(int)
tr = p[p.month < "2025-01"].reset_index(drop=True); te = p[p.month >= "2025-01"].reset_index(drop=True)
y, ids = te.y.to_numpy(), te.cve_id.to_numpy()
# ---- B
yb = cap_labels(tr, "2024-12-31"); chk("b.train_positives", int(yb.sum()))
s, _ = run(tr, te, yb)
chk("b.top500_cve_id", M.top_by_id(y, s, ids)); chk("b.auc", M.auc(y, s)); chk("b.avg_precision", M.ap(y, s))
fp = pd.DataFrame({"y": y, "s": s}).sort_values("s", ascending=False).y.to_numpy()
chk("b.top500_first_pass_order", int(fp[:500].sum())); chk("b.median_rank", int(np.median(np.where(fp == 1)[0] + 1)))
# ---- E
e_tr = p[(p.month >= "2024-07") & (p.month <= "2025-03")].reset_index(drop=True)
e_te = p[(p.month >= "2025-04") & (p.month <= "2025-09")].reset_index(drop=True)
ey, eids = e_te.y.to_numpy(), e_te.cve_id.to_numpy()
chk("e.train_positives", int(e_tr.y.sum())); chk("e.train_positives_capped", int(cap_labels(e_tr, "2025-03-31").sum()))
chk("e.test_rows", len(e_te)); chk("e.test_positives", int(ey.sum()))
print("e overlap ids", len(set(e_tr.cve_id) & set(e_te.cve_id)))
cv = e_te.cvss3_score.fillna(-1).to_numpy(); ep = e_te.epss_f.to_numpy()
sc = {"cvss3": cv, "epss": ep, "exploit_then_epss": e_te.anyx.to_numpy() * 10 + np.clip(ep, 0, None), "assigner_only": e_te.asg_rate.to_numpy()}
sc["hgb_signals_assigner_text"] = run(e_tr, e_te, e_tr.y.to_numpy())[0]
sc["hgb_signals_assigner_text__train_labels_to_2025_03_31"] = run(e_tr, e_te, cap_labels(e_tr, "2025-03-31"))[0]
for n, s in sc.items():
    chk(f"e.{n}.top500_cve_id", M.top_by_id(ey, s, eids)); chk(f"e.{n}.top500_expected", M.tie_topk(ey, s, 500)[1])
    chk(f"e.{n}.auc", M.auc(ey, s)); chk(f"e.{n}.avg_precision", M.ap(ey, s))
# ---- H
W = r"exploited in the wild|actively exploited|known to be exploited|has been exploited|may have been exploited|is being exploited|CISA|KEV"
hit = p.description.fillna("").str.contains(W, case=False, regex=True)
for nm, m in (("train", p.month < "2025-01"), ("test", p.month >= "2025-01")):
    chk(f"h.{nm}.positives_with_wording", int((hit & (p.y == 1) & m).sum())); chk(f"h.{nm}.negatives_with_wording", int((hit & (p.y == 0) & m).sum()))
# ---- D seed spread (both_vary)
d = []
for i in range(10):
    s, _ = run(tr, te, tr.y.to_numpy(), seeds=(3*i, 3*i+1, 3*i+2), fold_seed=i)
    d.append((M.top_by_id(y, s, ids), M.auc(y, s)))
print("D runs", d, flush=True)
chk("d.top500_min", min(a for a, _ in d)); chk("d.top500_max", max(a for a, _ in d))
# ---- permutation null, 20 draws, single HGB seed
rng = np.random.default_rng(2026); perm = []
for i in range(20):
    s, _ = run(tr, te, rng.permutation(tr.y.to_numpy()), seeds=(0,))
    perm.append((M.auc(y, s), M.top_by_id(y, s, ids)))
a = np.array([x for x, _ in perm])
print("PERM aucs", np.round(a, 3).tolist(), "mean", a.mean(), "sd", a.std(ddof=1), "top500", [t for _, t in perm])
json.dump(res, open("/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch/a4_result.json", "w"), indent=1)
