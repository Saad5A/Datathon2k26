"""Indicator re-derivation with the CVE-published-2021+ restriction (same population as the asg features)."""
import pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"
v = pd.read_csv(R + ".data/data/vulnerabilities.csv", usecols=["cve_id", "assigner", "published"], dtype=str)
kev = pd.read_csv(R + ".data/data/known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str)
p = pd.read_parquet(R + "audit/scratch/p3_pool.parquet")
pos = p[(p.month >= "2024-01") & (p.month <= "2024-12") & (p.y == 1)]
for lab, vv in (("all", v), ("pub2021+", v[v.published.str[:10] >= "2021-01-01"])):
    kv = kev.merge(vv, on="cve_id").dropna(subset=["assigner"])
    a = set(kv[kv.date_added.str[:4] == "2025"].assigner)
    print(lab, "assigners", len(a), "test positives with such assigner", int(pos.assigner.isin(a).sum()), "of", len(pos))
