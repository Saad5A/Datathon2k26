"""Auditor: independent drift numbers. 2025 side = my_pool2 test rows; 2026 side = scoreboard_2026.csv raw."""
import json, numpy as np, pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; D = R + ".data/data/"; S = R + "audit/scratch/"
p = pd.read_parquet(S + "my_pool2.parquet"); te = p[p.month >= "2025-01"].reset_index(drop=True)
sb = pd.read_csv(D + "scoreboard_2026.csv", dtype={"cve_id": str, "published": str, "snapshot_month": str})
vm = pd.read_parquet(S + "vuln_min.parquet")  # cve_id, published, assigner, month (harness audit)
v3 = pd.read_csv(D + "vulnerabilities.csv", usecols=["cve_id", "cvss3_score"], dtype=str)
out = {}
print("scoreboard rows", len(sb), "dup ids", sb.cve_id.duplicated().sum())
out["sb_rows_by_month"] = sb.snapshot_month.value_counts().sort_index().to_dict()
pm = sb.published.str[:7]
print("published-month vs snapshot mismatches:", pd.crosstab(pm, sb.snapshot_month).where(lambda d: d > 0).stack().to_dict())
out["pool_rows_by_month"] = te.month.value_counts().sort_index().to_dict()
out["vuln_published_per_month"] = vm.month[(vm.month >= "2024-01") & (vm.month <= "2026-09")].value_counts().sort_index().to_dict()
amap = dict(zip(vm.cve_id, vm.assigner))
sb["assigner"] = sb.cve_id.map(amap)
print("scoreboard ids not in vulnerabilities:", int(~sb.cve_id.isin(set(vm.cve_id)).sum()), "null assigner", int(sb.assigner.isna().sum()), "pool null assigner", int(te.assigner.isna().sum()))
out["distinct"] = {"2025": int(te.assigner.nunique()), "2026": int(sb.assigner.nunique())}
s25 = te.assigner.value_counts(normalize=True); s26 = sb.assigner.value_counts(normalize=True)
for a in ["security-advisories@github.com", "disclosure@vulncheck.com", "audit@patchstack.com", "cna@vuldb.com", "cve@mitre.org",
          "secalert_us@oracle.com", "chrome-cve-admin@google.com", "416baaa9-dc9f-4396-8d5f-8c081fb06d67"]:
    out.setdefault("share", {})[a] = [float(s25.get(a, 0)), float(s26.get(a, 0))]
out["top15_25"] = s25.index[:15].tolist(); out["top15_26"] = s26.index[:15].tolist()
# missing-data
ap = set()
allids = set(te.cve_id) | set(sb.cve_id)
for c in pd.read_csv(D + "affected_products.csv", usecols=["cve_id"], dtype=str, chunksize=1_000_000):
    ap |= set(c.cve_id[c.cve_id.isin(allids)])
blank3 = set(v3.cve_id[v3.cvss3_score.isna()])
F = ["exploitdb", "metasploit", "nuclei", "poc_github"]
def miss(df, epss, flags):
    return {"no_affected_product": float((~df.cve_id.isin(ap)).mean()), "cvss3_blank": float(df.cve_id.isin(blank3).mean()),
            "epss_blank": float(epss.isna().mean()), "any_public_exploit": float((flags.fillna(0).astype(float).max(axis=1) > 0).mean()),
            "epss_gt_0_1": float((epss > 0.1).mean())}
out["miss25_all"] = miss(te, te.epss, te[F]); out["miss26_all"] = miss(sb, sb.epss, sb[F])
out["miss26_by_month"] = {m: miss(g, g.epss, g[F]) for m, g in sb.groupby("snapshot_month")}
out["miss25_by_month"] = {m: miss(g, g.epss, g[F]) for m, g in te.groupby("month")}
# no-prior-KEV share: KEV row -> assigner via vulnerabilities.csv; prior iff earliest KEV date_added < first day of snapshot month
kev = pd.read_csv(D + "known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str)
kev["assigner"] = kev.cve_id.map(amap); kev["pub"] = kev.cve_id.map(dict(zip(vm.cve_id, vm.published)))
print("KEV rows", len(kev), "no vuln row/assigner", int(kev.assigner.isna().sum()), "published <2021:", int((kev.pub < "2021").sum()))
def noprior(rows_assigner, rows_month, k):
    first = k.dropna(subset=["assigner"]).groupby("assigner").date_added.min()
    f = rows_assigner.map(first)
    return (f.isna() | (f >= rows_month + "-01"))
res = {}
for name, k in [("all_kev", kev), ("kev_pub_2021plus", kev[kev.pub >= "2021"])]:
    n25 = noprior(te.assigner, te.month, k); n26 = noprior(sb.assigner, sb.snapshot_month, k)
    res[name] = {"2025_all": float(n25.mean()), "2026_all": float(n26.mean()),
                 "2025_by_month": n25.groupby(te.month).mean().round(6).to_dict(), "2026_by_month": n26.groupby(sb.snapshot_month).mean().round(6).to_dict()}
    print(name, res[name]["2025_all"], res[name]["2026_all"])
out["noprior"] = res
# which assigners flip between the two definitions (2026 rows)
first_all = kev.groupby("assigner").date_added.min(); first_21 = kev[kev.pub >= "2021"].groupby("assigner").date_added.min()
flip = sb.assigner[sb.assigner.map(first_all).notna() & sb.assigner.map(first_21).isna()].value_counts().head(10)
print("2026 rows counted no-prior only because of the 2021+ restriction:", flip.to_dict())
json.dump(out, open(S + "ld_4_result.json", "w"), indent=1, default=str)
