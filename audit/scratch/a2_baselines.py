"""Assigner history + baseline metrics, auditor's code path (numpy only for metrics)."""
import json, numpy as np, pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"
S = R + "audit/scratch/"
p = pd.read_parquet(S + "my_pool.parquet")
v = pd.read_parquet(S + "vuln_min.parquet")
print("published sample", v.published.iloc[-3:].tolist())
cv = pd.read_csv(R + ".data/data/vulnerabilities.csv", usecols=["cve_id", "cvss3_score"])
p = p.merge(cv, on="cve_id", how="left")
kev = pd.read_csv(R + ".data/data/known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str)

# ---- assigner history: loop per month with plain string comparisons on dates ----
v21 = v[v.published.str[:10] >= "2021-01-01"]
asg_of = dict(zip(v21.cve_id, v21.assigner))
kev["asg"] = kev.cve_id.map(asg_of)
rate, cnt = np.zeros(len(p)), np.zeros(len(p))
for m in sorted(p.month.unique()):
    first = m + "-01"
    kc = kev[(kev.date_added < first) & kev.asg.notna()].asg.value_counts()
    pc = v21[v21.published.str[:10] < first].assigner.value_counts()
    idx = np.where(p.month == m)[0]
    a = p.assigner.iloc[idx]
    cnt[idx] = a.map(kc).fillna(0).to_numpy()
    rate[idx] = (a.map(kc).fillna(0) / (a.map(pc) + 20)).fillna(0).to_numpy()
p["asg_rate"], p["asg_kev"] = rate, cnt
# Spot check two months by hand for Microsoft
for m in ("2024-06", "2025-03"):
    a = "secure@microsoft.com"
    k = ((kev.date_added < m + "-01") & (kev.asg == a)).sum()
    n = ((v21.published.str[:10] < m + "-01") & (v21.assigner == a)).sum()
    later = ((kev.date_added >= m + "-01") & (kev.asg == a)).sum()
    got = p[(p.month == m) & (p.assigner == a)].asg_rate.iloc[0]
    print(f"{m} microsoft kev_before={k} kev_on_or_after={later} published_before={n} rate={k/(n+20):.6f} pool={got:.6f}")

# ---- compare with producer cache ----
c = pd.read_parquet(R + "data_cache/backtest_pool.parquet")
print("same row order as cache:", (c.cve_id.to_numpy() == p.cve_id.to_numpy()).all())
c = c.set_index("cve_id").loc[p.cve_id]
print("y equal", (c.y.to_numpy() == p.y.to_numpy()).all())
print("asg_rate max abs diff", np.abs(c.asg_rate.to_numpy() - rate).max(), "asg_kev equal", (c.asg_kev.to_numpy() == cnt).all())
print("epss equal", np.allclose(c.epss_f.to_numpy(), p.epss.fillna(-1).astype(float).to_numpy()))
for f in ("exploitdb", "metasploit", "nuclei", "poc_github"):
    assert (c[f].to_numpy() == p[f].fillna(0).astype(float).to_numpy()).all(), f
print("flags equal")
print("cvss3 equal", np.allclose(c.cvss3.to_numpy(), p.cvss3_score.fillna(-1).to_numpy()))
p.to_parquet(S + "my_pool2.parquet")

# ---- metrics, plain numpy ----
def avg_ranks(s):
    o = np.argsort(s, kind="mergesort"); ss = s[o]
    r = np.empty(len(s)); i = 0
    _, start, counts = np.unique(ss, return_index=True, return_counts=True)
    for st, ct in zip(start, counts):
        r[o[st:st+ct]] = st + (ct + 1) / 2
    return r  # ascending ranks, 1-based
def auc(y, s):
    r = avg_ranks(s); n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
def ap(y, s):
    vals, inv = np.unique(-s, return_inverse=True)  # groups in descending score
    tp = np.bincount(inv, weights=y); n = np.bincount(inv)
    TP, N = np.cumsum(tp), np.cumsum(n)
    return float(np.sum(tp / y.sum() * TP / N))
def tie_topk(y, s, k):
    srt = np.sort(s)[::-1]; cut = srt[k - 1]
    above, tied = s > cut, s == cut
    slots = k - above.sum(); pt = y[tied].sum(); sz = tied.sum(); pa = y[above].sum()
    return pa + min(slots, pt), pa + slots * pt / sz, pa + max(0, slots - (sz - pt)), sz
def by_id(y, s, ids, k):
    o = sorted(range(len(s)), key=lambda i: (-s[i], ids[i]))
    return int(y[o[:k]].sum()), o
def ci_of(name, key):
    return None

te = p[p.month >= "2025-01"].reset_index(drop=True)
y = te.y.to_numpy(); ids = te.cve_id.to_numpy()
anyx = te[["exploitdb", "metasploit", "nuclei", "poc_github"]].fillna(0).astype(float).max(axis=1).to_numpy()
ep = te.epss.fillna(-1).astype(float).to_numpy()
scores = {"cvss3": te.cvss3_score.fillna(-1).to_numpy(), "epss": ep,
          "exploit_then_epss": anyx * 10 + np.clip(ep, 0, None), "assigner_only": te.asg_rate.to_numpy()}
cl = json.load(open(R + "results/claims_model.json"))
out = {}
for n, s in scores.items():
    h500, o = by_id(y, s, ids, 500); h250 = int(y[o[:250]].sum())
    rk = np.empty(len(o), int); rk[o] = np.arange(1, len(o) + 1)
    pos = np.sort(rk[y == 1]); work50 = pos[int(np.ceil(0.5 * len(pos))) - 1]
    b, e, w, sz = tie_topk(y, s, 500)
    mine = {"auc": auc(y, s), "avg_precision": ap(y, s), "top500_cve_id": h500, "top250_cve_id": h250,
            "top500_best": b, "top500_expected": e, "top500_worst": w, "top500_tied_group": sz, "work50_cve_id": work50}
    # first-pass order: pandas default sort on the pool row order
    fp = pd.DataFrame({"y": y, "s": s}).sort_values("s", ascending=False).y.to_numpy()
    mine["top500_first_pass_order"] = int(fp[:500].sum()); mine["top1000_first_pass_order"] = int(fp[:1000].sum())
    mine["median_rank_first_pass_order"] = int(np.median(np.where(fp == 1)[0] + 1))
    for k, val in mine.items():
        cv_ = cl[f"primary.{n}.{k}"]["value"]
        ok = abs(cv_ - val) <= 1e-6
        print(f"{n:18s} {k:30s} mine={val!s:22.20s} claimed={cv_!s:22.20s} {'OK' if ok else 'MISMATCH'}")
        out[f"primary.{n}.{k}"] = bool(ok)
json.dump(out, open(S + "a2_result.json", "w"), indent=1)
