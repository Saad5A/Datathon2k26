"""Compare u_run.py scores with the ledger. Own numpy metrics (mymetrics.py + bootstrap as in p3_boot.py)."""
import json, math, sys, numpy as np, pandas as pd
from joblib import Parallel, delayed
S = "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch/"; R = S[:-14]
sys.path.insert(0, S)
import mymetrics as M

cl = json.load(open(R + "results/claims_model.json"))
Z = np.load(S + "u_scores.npz")
p = pd.read_parquet(S + "p3_pool.parquet", columns=["cve_id", "month", "y"])
TE = {"primary": ("2025-01", "2025-09"), "fold1": ("2025-01", "2025-09"), "fold2": ("2025-04", "2025-09")}


def test(f):
    t = p[(p.month >= TE[f][0]) & (p.month <= TE[f][1])].reset_index(drop=True)
    return t.y.to_numpy(), t.cve_id.to_numpy()


def mid_desc(s):
    _, inv, cnt = np.unique(-s, return_inverse=True, return_counts=True)
    return (np.cumsum(cnt) - (cnt - 1) / 2)[inv]


def stats(y, s):
    mr = np.sort(mid_desc(s)[y == 1]); r = len(s) + 1 - mid_desc(s); n1 = y.sum(); n0 = len(y) - n1
    return {"top500_expected": M.tie_topk(y, s, 500)[1], "top250_expected": M.tie_topk(y, s, 250)[1],
            "auc": (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0), "avg_precision": M.ap(y, s),
            "median_rank_mid": float(np.median(mr)), "work50_mid": float(mr[math.ceil(len(mr) / 2) - 1])}


def ci(y, s):
    rng = np.random.default_rng(0); st = []
    while len(st) < 2000:
        i = rng.integers(0, len(y), len(y))
        if y[i].sum(): st.append(stats(y[i], s[i]))
    return {k: np.percentile([r[k] for r in st], [2.5, 97.5]).tolist() for k in st[0]}


def point(y, s, ids):
    o = np.lexsort((ids, -s)); r = np.empty(len(s), int); r[o] = np.arange(1, len(s) + 1)
    pos = np.sort(r[y == 1]); b, e, w, g = M.tie_topk(y, s, 500)
    d = {"auc": M.auc(y, s), "avg_precision": M.ap(y, s), "top500_cve_id": int(y[r <= 500].sum()),
         "top250_cve_id": int(y[r <= 250].sum()), "top1000_cve_id": int(y[r <= 1000].sum()),
         "top500_best": b, "top500_expected": e, "top500_worst": w, "top500_tied_group": g,
         "median_rank_cve_id": float(np.median(pos)), "work50_cve_id": float(pos[math.ceil(len(pos) / 2) - 1])}
    # tie-independence of first-pass-order numbers
    d["tied1000"] = M.tie_topk(y, s, 1000)[3]
    u, c = np.unique(s, return_counts=True); d["pos_unique_scores"] = bool(np.all(c[np.searchsorted(u, s[y == 1])] == 1))
    return d


rows, ok = [], {}


def chk(k, v, tol=1e-6):
    if k not in cl: rows.append(f"{k:64s} NOT IN LEDGER mine={v}"); return
    c = cl[k]["value"]; good = abs(float(c) - float(v)) <= tol * max(1, abs(float(c))) if "ci95" in k else abs(float(c) - float(v)) <= tol
    ok[k] = bool(good); rows.append(f"{k:64s} mine={float(v):<20.10g} claimed={float(c):<20.10g} {'OK' if good else 'MISMATCH'}")


CIK = ["top500_expected", "top250_expected", "auc", "avg_precision", "median_rank_mid", "work50_mid"]
work = []
y, ids = test("primary")
for n in ("hgb_signals_struct", "hgb_signals_struct_assigner", "hgb_all_text", "leaky_ncpe"):
    work.append((f"primary.{n}", "primary"))
for f in ("fold1", "fold2"):
    for n in ("drop_signals", "drop_assigner", "drop_text", "unmasked_text", "plus_structured", "early_stopping_on"):
        work.append((f"p3.{f}.{n}", f))
CI = dict(zip([w[0] for w in work], Parallel(n_jobs=10)(
    delayed(ci)(*test(f)[:1], Z[k.replace("p3.", "") + ".s0" if k.startswith("p3") else k]) for k, f in work)))

# sanity: my C1 here equals my Phase-3 C1 files, best_check equals harness best_scores
for f in ("fold1", "fold2"):
    for s in range(5):
        assert np.abs(Z[f"{f}.C1.s{s}"] - np.load(S + f"p3_C1_{f}_s{s}.npy")).max() < 1e-12, (f, s)
print("best_check max diff vs harness best_scores", np.abs(Z["primary.best_check"] - np.load(S + "best_scores.npy")).max())

ext = {}
for n in ("hgb_signals_struct", "hgb_signals_struct_assigner", "hgb_all_text", "leaky_ncpe"):
    k = f"primary.{n}"; d = point(y, Z[k], ids); ext[k] = d
    for m in ("auc", "avg_precision", "top500_cve_id", "top250_cve_id", "top500_best", "top500_expected", "top500_worst",
              "top500_tied_group", "work50_cve_id"):
        chk(f"{k}.{m}", d[m])
    if d["top500_tied_group"] == 1: chk(f"{k}.top500_first_pass_order", d["top500_cve_id"])
    if d["tied1000"] == 1: chk(f"{k}.top1000_first_pass_order", d["top1000_cve_id"])
    if d["pos_unique_scores"]: chk(f"{k}.median_rank_first_pass_order", d["median_rank_cve_id"])
    rows.append(f"   {k}: tied@500={d['top500_tied_group']} tied@1000={d['tied1000']} pos unique={d['pos_unique_scores']}")
    for m in CIK:
        chk(f"{k}.ci95_lo.{m}", CI[k][m][0]); chk(f"{k}.ci95_hi.{m}", CI[k][m][1])

for f in ("fold1", "fold2"):
    y, ids = test(f)
    for n in ("drop_signals", "drop_assigner", "drop_text", "unmasked_text", "plus_structured", "early_stopping_on", "C1", "C2", "C3"):
        per = [point(y, Z[f"{f}.{n}.s{s}"], ids) for s in range(5)]
        k = f"p3.{f}.{n}"; ext[k] = {m: [r[m] for r in per] for m in ("auc", "top500_cve_id", "top500_expected", "work50_cve_id", "avg_precision")}
        for m in ("top500_cve_id", "top500_expected", "top500_best", "top500_worst", "top250_cve_id", "auc", "avg_precision",
                  "median_rank_cve_id", "work50_cve_id"):
            chk(f"{k}.{m}.median", float(np.median([r[m] for r in per])))
        for m in ("top500_cve_id", "auc", "work50_cve_id"):
            for g, fn in (("min", min), ("max", max)):
                if f"{k}.{m}.{g}" in cl or n not in ("C1", "C2", "C3"): chk(f"{k}.{m}.{g}", fn(r[m] for r in per))
        if k in CI:
            for m in CIK:
                chk(f"{k}.ci95_lo.{m}", CI[k][m][0]); chk(f"{k}.ci95_hi.{m}", CI[k][m][1])

open(S + "u_check_out.txt", "w").write("\n".join(rows))
json.dump({"ok": ok, "detail": ext}, open(S + "u_check_result.json", "w"), indent=1, default=float)
print("checked", len(ok), "ok", sum(ok.values()), "mismatch", [k for k, v in ok.items() if not v])
