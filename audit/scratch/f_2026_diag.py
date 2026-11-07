"""Diagnose the 2026 preview mismatch: compare producer feature rows (their loaders, no fitting) with the auditor's."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/Users/aahmad/Working/datathon/code/Datathon2k26/src/model")
import candidates as C, reproduce_first_pass as R
from pool import FLAGS, assigner_history, data_dir, kev_with_assigner, load_kev, load_vulns
D = "/Users/aahmad/Working/datathon/code/Datathon2k26/.data/data/"
sb = pd.read_csv(data_dir() / "scoreboard_2026.csv", dtype={"cve_id": str})
v = load_vulns(cols=["cve_id", "published", "assigner", "description"])
sb = sb.merge(v[["cve_id", "assigner", "description"]], on="cve_id", how="left", validate="one_to_one")
kv = kev_with_assigner(load_kev(), v)
hist = {}
for m in sorted(sb.snapshot_month.unique()):
    start = pd.Timestamp(m + "-01")
    hist[m] = assigner_history(kv[kv.date_added < start], v[v.published < start], m)
sb["asg_rate"] = [hist[m][0].get(a, 0) for m, a in zip(sb.snapshot_month, sb.assigner)]
sb["asg_kev"] = [hist[m][1].get(a, 0) for m, a in zip(sb.snapshot_month, sb.assigner)]
# auditor's
va = pd.read_csv(D + "vulnerabilities.csv", usecols=["cve_id", "published", "assigner"], dtype=str)
ka = pd.read_csv(D + "known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str).merge(va[["cve_id", "assigner"]], on="cve_id", how="left").dropna(subset=["assigner"])
va["d"] = va.published.str[:10]
r2, c2 = np.zeros(len(sb)), np.zeros(len(sb))
for m in sorted(sb.snapshot_month.unique()):
    st = m + "-01"; kc = ka[ka.date_added < st].assigner.value_counts(); pc = va[va.d < st].assigner.value_counts()
    idx = np.where(sb.snapshot_month == m)[0]; a = sb.assigner.iloc[idx]
    k = a.map(kc).fillna(0); c2[idx] = k; r2[idx] = (k / (a.map(pc) + 20)).fillna(0)
print("asg_kev equal", (sb.asg_kev.to_numpy() == c2).all(), "asg_rate maxdiff", np.abs(sb.asg_rate.to_numpy() - r2).max())
d = sb[np.abs(sb.asg_rate.to_numpy() - r2) > 1e-12]
print(len(d), d[["snapshot_month", "assigner"]].drop_duplicates().head(10).to_string())
print("published dtype", v.published.dtype, v.published.head(2).tolist(), "kv date dtype", kv.date_added.dtype)
print("vulns rows producer", len(v), "auditor", len(va))
