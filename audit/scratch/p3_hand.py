"""Hand check of the 24-month assigner window for two assigner-months with plain csv loops, then a full
comparison against the producer's add_window_features (producer code used only as the object under test)."""
import csv, sys, numpy as np, pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
csv.field_size_limit(10**9)
CASES = [("secure@microsoft.com", "2024-06"), ("security@apache.org", "2025-02")]
pub, asg = {}, {}
with open(R + ".data/data/vulnerabilities.csv", newline="") as fh:
    for r in csv.DictReader(fh):
        pub[r["cve_id"]] = r["published"][:10]; asg[r["cve_id"]] = r["assigner"]
kev = list(csv.DictReader(open(R + ".data/data/known_exploited.csv", newline="")))
p = pd.read_parquet(S + "p3_pool.parquet")
for a, m in CASES:
    start = m + "-01"; lo = f"{int(m[:4]) - 2}{m[4:]}-01"
    rows = [k for k in kev if asg.get(k["cve_id"]) == a]
    inw = [k for k in rows if lo <= k["date_added"] < start and pub[k["cve_id"]] >= "2021-01-01"]
    inw_all = [k for k in rows if lo <= k["date_added"] < start]
    after = [k for k in rows if k["date_added"] >= start]
    before_lo = [k for k in rows if k["date_added"] < lo]
    n = sum(1 for c, d in pub.items() if asg[c] == a and lo <= d < start)
    got = p[(p.month == m) & (p.assigner == a)][["asg24_rate", "asg24_kev", "asg24_kev_all"]].iloc[0].to_dict()
    print(f"{a} {m}: window [{lo},{start}) KEV in window (CVE 2021+)={len(inw)} (any year={len(inw_all)}), "
          f"excluded on/after start={len(after)}, before window={len(before_lo)}, published in window={n}, "
          f"rate={len(inw)/(n+20):.6f}; latest date in window={max(k['date_added'] for k in inw)}; pool={got}")

sys.path.insert(0, R + "src/model")
from candidates import add_window_features
from pool import load_pool
q = add_window_features(load_pool()).set_index("cve_id").loc[p.cve_id]
print("asg24_rate max abs diff vs producer", float(np.abs(q.asg24_rate.to_numpy() - p.asg24_rate.to_numpy()).max()),
      "asg24_kev equal", bool((q.asg24_kev.to_numpy() == p.asg24_kev.to_numpy()).all()))
print("rows where all-year count differs", int((p.asg24_kev != p.asg24_kev_all).sum()), "of", len(p))
