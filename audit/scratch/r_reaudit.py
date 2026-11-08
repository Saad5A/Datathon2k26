"""Re-audit of the 7 re-registered rev.* claims against auditor values (r_result.json, raw-CSV recount); also checks the 75 verified claims are unchanged."""
import json, subprocess, pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
cl = json.load(open(R + "results/claims_model_reverse.json")); me = json.load(open(S + "r_result.json"))
v = pd.read_csv(R + ".data/data/vulnerabilities.csv", usecols=["cve_id", "assigner", "published"], dtype=str)
kev = pd.read_csv(R + ".data/data/known_exploited.csv", usecols=["cve_id", "date_added"], dtype=str)
kd = dict(zip(kev.cve_id, kev.date_added))
p = pd.read_parquet(S + "p3_pool.parquet")
pos = p[(p.month >= "2024-01") & (p.month <= "2024-12") & (p.y == 1)]
own = pos.cve_id.map(kd)                       # raw KEV date, not the pool column
kv = kev.merge(v[v.published.str[:10] >= "2021-01-01"], on="cve_id").dropna(subset=["assigner"])
a25 = set(kv[kv.date_added.str[:4] == "2025"].assigner)
mine = {"rev.exploit_then_epss.ci95_lo.top500_expected": me["ci"]["exploit_then_epss"]["top500_expected"][0],
        "rev.exploit_then_epss.ci95_hi.top500_expected": me["ci"]["exploit_then_epss"]["top500_expected"][1],
        "rev.cvss3.ci95_lo.top500_expected": me["ci"]["cvss3"]["top500_expected"][0],
        "rev.cvss3.ci95_hi.top500_expected": me["ci"]["cvss3"]["top500_expected"][1],
        "rev.indicator.positives_whose_assigner_has_kev_additions_dated_2025": int(pos.assigner.isin(a25).sum()),
        "rev.indicator.positives_own_kev_date_before_2025_09_01": int((own < "2025-09-01").sum()),
        "rev.indicator.positives_own_kev_date_before_2025_01_01": int((own < "2025-01-01").sum())}
ok = []
for k, m in mine.items():
    c = cl[k]; good = abs(c["value"] - m) <= 1e-6 and "reverse-time (not time-safe)" in c["text"]
    print(f"{k:72s} mine={m!r:20.18s} claimed={c['value']!r:20.18s} {'OK' if good else 'MISMATCH'}"); ok.append(good)
old = json.loads(subprocess.run(["git", "-C", R, "show", "588d5db:results/claims_model_reverse.json"], capture_output=True, text=True).stdout)
ver = [k for k, x in old.items() if x["status"] == "verified"]
chg = [k for k in ver if k not in cl or cl[k]["value"] != old[k]["value"] or cl[k]["text"] != old[k]["text"] or cl[k]["status"] != "verified"]
print("previously verified:", len(ver), "changed/missing:", chg, "| total claims now", len(cl), "| extra keys", sorted(set(cl) - set(old)))
print("all 7 OK:", all(ok))
