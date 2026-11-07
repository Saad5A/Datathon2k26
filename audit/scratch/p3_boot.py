"""Phase 3 audit: seed-0 bootstrap CIs (candidates + baselines), paired bootstrap vs exploit-then-EPSS,
unseen-assigner subset detail, and a claim-by-claim comparison for every p3.* number I re-derived."""
import json, math, sys, numpy as np
from joblib import Parallel, delayed
sys.path.insert(0, "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch")
import p3_rederive as A
import mymetrics as M
R, S = A.R, A.S
cl = json.load(open(R + "results/claims_model.json"))
P = json.load(open(R + "results/model_candidates.json"))
mine = json.load(open(S + "p3_result.json"))
res, rows = {}, []


def chk(key, val, tol=1e-6):
    c = cl[key]["value"]; ok = abs(c - val) <= tol; res[key] = bool(ok)
    rows.append(f"{key:62s} mine={val!s:20.18s} claimed={c!s:20.18s} {'OK' if ok else 'MISMATCH'}")


def mid_desc(s):
    _, inv, cnt = np.unique(-s, return_inverse=True, return_counts=True)
    return (np.cumsum(cnt) - (cnt - 1) / 2)[inv]


def stats(y, s):
    mr = np.sort(mid_desc(s)[y == 1]); r = len(s) + 1 - mid_desc(s); n1 = y.sum(); n0 = len(y) - n1
    return {"top500_expected": M.tie_topk(y, s, 500)[1], "top250_expected": M.tie_topk(y, s, 250)[1],
            "auc": (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0), "avg_precision": M.ap(y, s),
            "median_rank_mid": float(np.median(mr)), "work50_mid": float(mr[math.ceil(len(mr) / 2) - 1])}


def boot_idx(y, n=2000):
    rng = np.random.default_rng(0); idx = []
    while len(idx) < n:
        i = rng.integers(0, len(y), len(y))
        if y[i].sum(): idx.append(i)
    return idx


def ci(y, s, idx):
    st = [stats(y[i], s[i]) for i in idx]
    return {k: np.percentile([r[k] for r in st], [2.5, 97.5]) for k in st[0]}


runs = [r for r in mine["runs"] if r["perm"] is None]
for f in A.FOLDS:
    tr, te, ytr = A.fold(f)
    y, ids = te.y.to_numpy(), te.cve_id.to_numpy()
    fm = mine[f]
    for k, v in (("train_rows", fm["train_rows"]), ("train_positives", fm["train_pos"]), ("test_rows", fm["test_rows"]),
                 ("test_positives", fm["test_pos"])):
        chk(f"p3.{f}.{k}", v)
    # point metrics, all seeds -> median/min/max for candidates
    for c in ("C1", "C2", "C3"):
        per = sorted([r for r in runs if r["fold"] == f], key=lambda r: r["seed"])
        a = [r["out"][c]["auc"] for r in per]; t = [r["out"][c]["top500"] for r in per]
        w = [r["out"][c]["work50"] for r in per]; e = [r["out"][c]["top500_expected"] for r in per]
        chk(f"p3.{f}.{c}.auc.median", float(np.median(a))); chk(f"p3.{f}.{c}.auc.min", min(a)); chk(f"p3.{f}.{c}.auc.max", max(a))
        chk(f"p3.{f}.{c}.top500_cve_id.median", float(np.median(t))); chk(f"p3.{f}.{c}.top500_cve_id.min", min(t))
        chk(f"p3.{f}.{c}.top500_cve_id.max", max(t)); chk(f"p3.{f}.{c}.work50_cve_id.median", float(np.median(w)))
        chk(f"p3.{f}.{c}.top500_expected.median", float(np.median(e)))
    # seed-0 scores
    oof, st = A.text(tr, te, ytr, 0)
    sc = {c: A.model(*A.CAND[c], tr, te, ytr, oof, st, 0) for c in ("C2", "C3")}
    sc["C1"] = np.load(S + f"p3_C1_{f}_s0.npy")
    assert np.allclose(sc["C1"], A.model(*A.CAND["C1"], tr, te, ytr, oof, st, 0))
    sc["exploit_then_epss"] = (te.anyx * 10 + te.epss_f.clip(lower=0)).to_numpy()
    sc["epss"] = te.epss_f.to_numpy(); sc["cvss3"] = te.cvss3_score.fillna(-1).to_numpy()
    for n in ("exploit_then_epss", "epss", "cvss3"):
        m = A.mets(y, sc[n], ids)
        chk(f"p3.{f}.{n}.auc.median", m["auc"]); chk(f"p3.{f}.{n}.top500_cve_id.median", m["top500"])
        chk(f"p3.{f}.{n}.work50_cve_id.median", m["work50"]); chk(f"p3.{f}.{n}.top500_expected.median", m["top500_expected"])
    idx = boot_idx(y)
    cis = Parallel(n_jobs=6)(delayed(ci)(y, sc[n], idx) for n in sc)
    for n, c in zip(sc, cis):
        for k, (lo, hi) in c.items():
            chk(f"p3.{f}.{n}.ci95_lo.{k}", lo); chk(f"p3.{f}.{n}.ci95_hi.{k}", hi)
    # paired bootstrap, seed 0 (as the producer) and the seed-median comparison for context
    a, b = sc["C1"], sc["exploit_then_epss"]
    da = np.array([stats(y[i], a[i])["auc"] - stats(y[i], b[i])["auc"] for i in idx])
    dt = np.array([M.tie_topk(y[i], a[i], 500)[1] - M.tie_topk(y[i], b[i], 500)[1] for i in idx])
    chk(f"p3.{f}.paired.auc.diff", M.auc(y, a) - M.auc(y, b))
    chk(f"p3.{f}.paired.auc.ci95_lo", np.percentile(da, 2.5)); chk(f"p3.{f}.paired.auc.ci95_hi", np.percentile(da, 97.5))
    chk(f"p3.{f}.paired.top500_expected.diff", M.tie_topk(y, a, 500)[1] - M.tie_topk(y, b, 500)[1])
    chk(f"p3.{f}.paired.top500_expected.ci95_lo", np.percentile(dt, 2.5)); chk(f"p3.{f}.paired.top500_expected.ci95_hi", np.percentile(dt, 97.5))
    rows.append(f"{f} paired share AUC diff>0 {np.mean(da > 0):.4f}; top500 diff<0 {np.mean(dt < 0):.4f}")
    # unseen-assigner subset (C1 seed 0) and the baseline on the same subset
    m = (te.asg_kev == 0).to_numpy(); r0 = A.ranks_id(a, ids); rb = A.ranks_id(b, ids)
    chk(f"p3.{f}.unseen_assigner.rows", int(m.sum())); chk(f"p3.{f}.unseen_assigner.positives", int(y[m].sum()))
    chk(f"p3.{f}.unseen_assigner.auc", M.auc(y[m], a[m]))
    chk(f"p3.{f}.unseen_assigner.top500_rows_from_subset", int(((r0 <= 500) & m).sum()))
    chk(f"p3.{f}.unseen_assigner.top500_hits_from_subset", int(((r0 <= 500) & m & (y == 1)).sum()))
    ys, as_, bs = y[m], a[m], b[m]
    sub = [M.auc(ys[i], as_[i]) for i in boot_idx(ys, 1000) if 0 < ys[i].sum() < len(i)]
    rows.append(f"{f} unseen subset: C1 seed0 AUC {M.auc(ys, as_):.4f} bootstrap95 {np.percentile(sub, [2.5, 97.5]).round(3)}; "
                f"exploit-then-EPSS AUC in subset {M.auc(ys, bs):.4f}; positives' within-subset ranks (C1) "
                f"{sorted((len(as_) + 1 - M.avg_ranks(as_))[ys == 1].astype(int).tolist())}; "
                f"positives anyx {te.anyx.to_numpy()[m][ys == 1].tolist()} epss {np.round(te.epss.to_numpy()[m][ys == 1], 3).tolist()}")
    # median-seed paired difference, for consistency with the seed-median headline
    med = float(np.median([r["out"]["C1"]["auc"] for r in runs if r["fold"] == f]))
    rows.append(f"{f} C1 seed0 AUC {M.auc(y, a):.4f} vs seed median {med:.4f}; median minus exploit-then-EPSS {med - M.auc(y, b):.4f}")

mean = {c: float(np.mean([np.median([r["out"][c]["auc"] for r in runs if r["fold"] == f]) for f in A.FOLDS])) for c in ("C1", "C2", "C3", "C2_allkev")}
for c in ("C1", "C2", "C3"):
    chk(f"p3.selection.{c}.mean_auc", mean[c])
best = max(mean[c] for c in ("C1", "C2", "C3"))
pick = [c for c in ("C3", "C2", "C1") if mean[c] >= best - 0.01][0]
rows.append(f"mean AUC {mean}; rule picks {pick}; producer selected {P['selection']['selected']}")
perm = [r["out"]["C1"]["auc"] for r in mine["runs"] if r["perm"] is not None]
rows.append(f"my permutation fold2 (10 shuffles, seeds 1000..1009): mean {np.mean(perm):.4f} sd {np.std(perm, ddof=1):.4f} max {max(perm):.4f}")
print("\n".join(rows))
print("checked", len(res), "ok", sum(res.values()))
json.dump(res, open(S + "p3_boot_result.json", "w"), indent=1)
