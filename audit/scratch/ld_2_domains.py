"""Auditor: which reference domains/tags appear for test positives, and are major news/threat sites missing from NEWS_DOMAINS."""
import json, pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"; D = R + ".data/data/"
p = pd.read_parquet(S + "my_pool2.parquet"); te = p[p.month >= "2025-01"]
pos = set(te.cve_id[te.y == 1])
r = pd.read_parquet(S + "ld_refs_test.parquet")
r["dom"] = r.domain.fillna("").str.lower().str.removeprefix("www.")
NEWS = set(json.load(open(R + "results/leakage_table.meta.json"))["news_domains"])
rp = r[r.cve_id.isin(pos)]
print("positive-ref domains (n CVEs):"); print(rp.groupby("dom").cve_id.nunique().sort_values(ascending=False).head(60).to_string())
print("tags vocabulary:", sorted({t.strip() for x in r.tags.dropna() for t in x.split(";")}))
cand = ["securityonline.info","cybersecuritynews.com","gbhackers.com","rapid7.com","tenable.com","horizon3.ai","attackerkb.com",
        "sekoia.io","sophos.com","news.sophos.com","fortiguard.com","blog.qualys.com","zerodayinitiative.com","cisa.gov","bleepingcomputer.com",
        "securityonline.info","censys.com","vulncheck.com","googleprojectzero.blogspot.com","cloud.google.com","microsoft.com",
        "thecyberexpress.com","cyble.com","socradar.io","darkreading.com","infosecurity-magazine.com","zdnet.com","forbes.com","bitsight.com",
        "arcticwolf.com","trendmicro.com","eclecticiq.com","shadowserver.org","github.com","x.com","twitter.com","reddit.com"]
for d in sorted(set(cand)):
    sub = r[r.dom.str.endswith(d)]
    print(f"{d:32s} inlist={d in NEWS} cves={sub.cve_id.nunique():5d} pos_cves={sub.cve_id[sub.cve_id.isin(pos)].nunique()}")
# xforce in whole refs file
n = 0; yrs = {}
for c in pd.read_csv(D + "references.csv", usecols=["cve_id", "domain"], dtype=str, chunksize=500_000):
    m = c.domain.fillna("").str.contains("xforce", regex=False); n += m.sum()
    for k, val in c.cve_id[m].str[4:8].value_counts().items(): yrs[k] = yrs.get(k, 0) + val
print("xforce refs whole file", n, "by cve-id year (top)", sorted(yrs.items(), key=lambda t: -t[1])[:8], "2025:", yrs.get("2025"), "2026:", yrs.get("2026"))
