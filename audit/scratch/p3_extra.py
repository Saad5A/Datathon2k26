"""Phase 3 audit, extra: exact permutation re-run with the producer's shuffle seeds 0..19 (both folds), and the
remaining point metrics of C1 (all 5 saved seed vectors) and the 3 baselines with my own metric code."""
import json, math, sys, numpy as np
from joblib import Parallel, delayed
sys.path.insert(0, "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch")
import p3_rederive as A
import mymetrics as M
R, S = A.R, A.S
cl = json.load(open(R + "results/claims_model.json")); res, rows = {}, []


def chk(key, val, tol=1e-6):
    c = cl[key]["value"]; ok = abs(c - val) <= tol; res[key] = bool(ok)
    rows.append(f"{key:62s} mine={val!s:20.18s} claimed={c!s:20.18s} {'OK' if ok else 'MISMATCH'}")


def allm(y, s, ids):
    r = A.ranks_id(s, ids); pos = np.sort(r[y == 1]); b, e, w, _ = M.tie_topk(y, s, 500)
    return {"top500_cve_id": int(y[r <= 500].sum()), "top250_cve_id": int(y[r <= 250].sum()), "auc": M.auc(y, s),
            "avg_precision": M.ap(y, s), "median_rank_cve_id": float(np.median(pos)),
            "work50_cve_id": float(pos[math.ceil(len(pos) / 2) - 1]), "top500_best": b, "top500_expected": e, "top500_worst": w}


for f in A.FOLDS:
    tr, te, ytr = A.fold(f); y, ids = te.y.to_numpy(), te.cve_id.to_numpy()
    per = [allm(y, np.load(S + f"p3_C1_{f}_s{s}.npy"), ids) for s in range(5)]
    for k in per[0]:
        chk(f"p3.{f}.C1.{k}.median", float(np.median([p[k] for p in per])))
    base = {"exploit_then_epss": (te.anyx * 10 + te.epss_f.clip(lower=0)).to_numpy(), "epss": te.epss_f.to_numpy(),
            "cvss3": te.cvss3_score.fillna(-1).to_numpy()}
    for n, s in base.items():
        for k, v in allm(y, s, ids).items():
            chk(f"p3.{f}.{n}.{k}.median", v)
        for k in ("top500_cve_id", "auc"):
            v = allm(y, s, ids)[k]; chk(f"p3.{f}.{n}.{k}.min", v); chk(f"p3.{f}.{n}.{k}.max", v)

out = Parallel(n_jobs=10)(delayed(A.task)(f, 0, i) for f in A.FOLDS for i in range(20))
for f in A.FOLDS:
    a = [o["C1"]["auc"] for ff, _, _, o in out if ff == f]
    chk(f"p3.{f}.permutation.auc_mean", float(np.mean(a))); chk(f"p3.{f}.permutation.auc_sd", float(np.std(a, ddof=1)))
    chk(f"p3.{f}.permutation.auc_max", float(max(a)))
    rows.append(f"{f} permutation (producer shuffle seeds 0..19): {np.round(a, 3).tolist()}")
print("\n".join(rows)); print("checked", len(res), "ok", sum(res.values()))
json.dump(res, open(S + "p3_extra_result.json", "w"), indent=1)
