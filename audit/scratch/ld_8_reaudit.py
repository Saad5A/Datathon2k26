"""Auditor re-audit of f64fccf: 14 changed claims + sanity of previously verified ones. Own code."""
import json, numpy as np, pandas as pd, subprocess
from scipy.stats import rankdata, beta
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"; D = R + ".data/data/"
def auc(y, s):
    r = rankdata(s); n1 = y.sum(); n0 = len(y) - n1; return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
p = pd.read_parquet(S + "my_pool2.parquet"); te = p[p.month >= "2025-01"].reset_index(drop=True); y = te.y.to_numpy()
assert len(te) == 35280 and y.sum() == 52
# asg_kev (harness auditor's independently-checked column)
print("asg_kev auc", round(auc(y, te.asg_kev.to_numpy()), 6))
# news rule, rebuilt from my own refs extract
r = pd.read_parquet(S + "ld_refs_test.parquet"); r["dom"] = r.domain.fillna("").str.lower().str.removeprefix("www.")
url = r.url.fillna("").str.lower()
press = r.tags.fillna("").str.contains("Press/Media Coverage", regex=False)
NEWS = {"arstechnica.com","bleepingcomputer.com","blog.talosintelligence.com","crowdstrike.com","darkreading.com","greynoise.io",
 "helpnetsecurity.com","horizon3.ai","huntress.com","isc.sans.edu","krebsonsecurity.com","labs.greynoise.io","labs.watchtowr.com",
 "mandiant.com","research.checkpoint.com","securelist.com","securityaffairs.com","securityweek.com","techcrunch.com",
 "thehackernews.com","therecord.media","theregister.com","unit42.paloaltonetworks.com","volexity.com","welivesecurity.com","wired.com"}
assert NEWS == set(json.load(open(R + "results/leakage_table.meta.json"))["news_rule"]["domains"])
def news_auc(extra_dom=set(), r7_all=False):
    m = press | r.dom.isin(NEWS | extra_dom) | url.str.contains("rapid7.com/blog/", regex=False)
    if r7_all: m |= r.dom.str.endswith("rapid7.com")
    x = te.cve_id.isin(set(r.cve_id[m])).to_numpy().astype(float)
    return round(auc(y, x), 6), int(x[y == 1].sum()), int(x[y == 0].sum())
print("news as committed", news_auc())
print("news + sophos/tenable/all rapid7", news_auc({"sophos.com", "news.sophos.com", "tenable.com"}, True))
for d in ["sophos.com", "news.sophos.com", "tenable.com", "rapid7.com"]:
    sub = r[r.dom == d]; print(d, sub.cve_id.nunique(), "CVEs, pos", int(sub.cve_id.isin(set(te.cve_id[y == 1])).sum()), sub.url.str.replace(r"https?://(www\.)?", "", regex=True).str[:60].head(6).tolist())
# positive facts from raw vulnerabilities
v = pd.read_csv(D + "vulnerabilities.csv", usecols=["cve_id", "nvd_status", "cvss3_score", "cwe_ids"], dtype=str).set_index("cve_id").reindex(te.cve_id)
ap = set()
for c in pd.read_csv(D + "affected_products.csv", usecols=["cve_id"], dtype=str, chunksize=1_000_000): ap |= set(c.cve_id[c.cve_id.isin(set(te.cve_id))])
facts = {"nvd_status_Analyzed": (v.nvd_status == "Analyzed").to_numpy(), "has_affected_product": te.cve_id.isin(ap).to_numpy(),
         "cvss3_present": v.cvss3_score.notna().to_numpy(), "cwe_present": v.cwe_ids.notna().to_numpy()}
cp = lambda k, n: (0.025 ** (1 / n)) if k == n else beta.ppf(0.025, k, n - k + 1)  # closed form when k = n
for k, x in facts.items(): print(k, int(x[y == 1].sum()), "/ 52  cp95_lower", round(cp(int(x[y == 1].sum()), 52), 6), "neg share", round(x[y == 0].mean(), 6))
