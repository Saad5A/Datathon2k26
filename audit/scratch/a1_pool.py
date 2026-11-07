"""Auditor's independent pool build. String months, dict KEV lookup, numpy datetime64 labels."""
import numpy as np, pandas as pd, sys
D = "/Users/aahmad/Working/datathon/code/Datathon2k26/.data/data/"
OUT = "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch/"

v = pd.read_csv(D + "vulnerabilities.csv", usecols=["cve_id", "published", "assigner", "description"], dtype=str)
print("vuln rows", len(v), "dup ids", v.cve_id.duplicated().sum())
v["month"] = v.published.str[:7]
v[["cve_id", "published", "assigner", "month"]].to_parquet(OUT + "vuln_min.parquet")
p = v[(v.month >= "2024-01") & (v.month <= "2025-09")].copy()
print("published 2024-01..2025-09:", len(p))

keys = set(zip(p.cve_id, p.month))
sig = []
for f in ("exploit_signals_2024.csv", "exploit_signals_2025.csv"):
    s = pd.read_csv(D + f, dtype={"cve_id": str, "month": str})
    m = [(c, mo) in keys for c, mo in zip(s.cve_id, s.month)]
    sig.append(s[m])
sig = pd.concat(sig)
print("signal rows matched", len(sig), "dup keys", sig.duplicated(["cve_id", "month"]).sum())
p = p.merge(sig, on=["cve_id", "month"], how="left")

kev = pd.read_csv(D + "known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str)
print("kev rows", len(kev), "dup", kev.cve_id.duplicated().sum())
kd = dict(zip(kev.cve_id, kev.date_added))
p["kev_date"] = p.cve_id.map(kd)

# month end as numpy date
start = np.array([np.datetime64(m + "-01") for m in p.month])
mend = (start.astype("datetime64[M]") + 1).astype("datetime64[D]") - 1
added = np.array([np.datetime64(d) if isinstance(d, str) else np.datetime64("NaT") for d in p.kev_date], dtype="datetime64[D]")
on_kev = (p.in_kev.fillna(0).astype(float) == 1).to_numpy() | (~np.isnat(added) & (added <= mend))
print("dropped in_kev flag", int((p.in_kev.fillna(0).astype(float) == 1).sum()), "dropped total", int(on_kev.sum()))
lim = np.minimum(mend + 365, np.datetime64("2025-12-31"))
y = (~np.isnat(added)) & (added > mend) & (added <= lim)
p["y"] = y.astype(int)
p["mend"] = mend
p = p[~on_kev].reset_index(drop=True)
tr, te = p[p.month < "2025-01"], p[p.month >= "2025-01"]
print("pool", len(p), p.y.sum(), "train", len(tr), tr.y.sum(), "test", len(te), te.y.sum())
print("id overlap train/test", len(set(tr.cve_id) & set(te.cve_id)), "pool unique", p.cve_id.is_unique)
print("KEV rows in pool counted negative (outside window)", int((p.kev_date.notna() & (p.y == 0)).sum()))
print("test positives by month", te.groupby("month").y.sum().to_dict())
print("test pos with no signal row", int(te[te.y == 1].epss.isna().sum()))
p.to_parquet(OUT + "my_pool.parquet")
