"""Auditor: independent solo AUCs on the 2025 test pool (my_pool2 from the harness audit). Plain numpy rank AUC."""
import json, re, numpy as np, pandas as pd
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; D = R + ".data/data/"; S = R + "audit/scratch/"
p = pd.read_parquet(S + "my_pool2.parquet")
te = p[p.month >= "2025-01"].reset_index(drop=True)
assert len(te) == 35280 and te.y.sum() == 52
ids = set(te.cve_id)
v = pd.read_csv(D + "vulnerabilities.csv", usecols=["cve_id", "nvd_status", "cvss3_score", "cwe_ids", "attack_vector",
                "n_references", "n_affected_cpes", "description"], dtype=str)
v = v[v.cve_id.isin(ids)].set_index("cve_id").reindex(te.cve_id)
ap = set()
for c in pd.read_csv(D + "affected_products.csv", usecols=["cve_id"], dtype=str, chunksize=1_000_000):
    ap |= set(c.cve_id[c.cve_id.isin(ids)])
NEWS = json.load(open(R + "results/leakage_table.meta.json"))["news_domains"]
refs = []
for c in pd.read_csv(D + "references.csv", usecols=["cve_id", "url", "domain", "tags"], dtype=str, chunksize=500_000):
    refs.append(c[c.cve_id.isin(ids)])
refs = pd.concat(refs); refs.to_parquet(S + "ld_refs_test.parquet")
dom = refs.domain.fillna("").str.lower()
dom = dom.where(~dom.str.startswith("www."), dom.str[4:])
tags = refs.tags.fillna("")
refs["news"] = tags.str.contains("Press/Media Coverage", regex=False) | dom.isin(NEWS)
refs["xf"] = dom.str.contains("exchange.xforce", regex=False) | refs.url.fillna("").str.contains("exchange.xforce", regex=False)
refs["ex"] = tags.str.split(";").apply(lambda t: "Exploit" in [x.strip() for x in t])
g = refs.groupby("cve_id")[["news", "xf", "ex"]].any().reindex(te.cve_id).fillna(False)

def auc(y, s):  # Mann-Whitney with average ranks, no scipy
    s = np.asarray(s, float); o = np.argsort(s, kind="mergesort"); ss = s[o]
    r = np.empty(len(s)); i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and ss[j + 1] == ss[i]: j += 1
        r[o[i:j + 1]] = (i + j) / 2 + 1; i = j + 1
    n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)

F = ["exploitdb", "metasploit", "nuclei", "poc_github"]
fl = te[F].fillna(0).astype(float)
W = r"exploited in the wild|actively exploited|known to be exploited|has been exploited|may have been exploited|is being exploited|CISA|KEV"
AV = {"NETWORK": 3, "ADJACENT_NETWORK": 2, "ADJACENT": 2, "LOCAL": 1, "PHYSICAL": 0}
cols = {
 "nvd_status_analysed": v.nvd_status.isin(["Analyzed", "Modified"]).to_numpy(),
 "n_affected_cpes": pd.to_numeric(v.n_affected_cpes).fillna(0).to_numpy(),
 "n_references": pd.to_numeric(v.n_references).fillna(0).to_numpy(),
 "cvss3_blank": v.cvss3_score.isna().to_numpy(),
 "cwe_blank": v.cwe_ids.isna().to_numpy(),
 "has_affected_product": te.cve_id.isin(ap).to_numpy(),
 "ref_news_threat_link": g.news.to_numpy(), "ref_xforce_link": g.xf.to_numpy(), "ref_exploit_tag": g.ex.to_numpy(),
 "desc_exploitation_wording": v.description.fillna("").str.contains(W, case=False, regex=True).to_numpy(),
 "epss": te.epss.fillna(-1).to_numpy(), "any_public_exploit": fl.max(axis=1).to_numpy(),
 "n_exploit_flags": fl.sum(axis=1).to_numpy(), "asg_rate": te.asg_rate.to_numpy(),
 "cvss3_score": pd.to_numeric(v.cvss3_score).fillna(-1).to_numpy(),
 "attack_vector": v.attack_vector.map(AV).fillna(-1).to_numpy(),
}
y = te.y.to_numpy(); claimed = pd.read_csv(R + "results/leakage_table.csv").set_index("column")
out = {}
for k, x in cols.items():
    x = np.asarray(x, float); a = auc(y, x); pos = x[y == 1]; neg = x[y == 0]
    binary = set(np.unique(x)) <= {0.0, 1.0}
    d = dict(raw_auc=round(a, 6), oriented=round(max(a, 1 - a), 4), claimed=float(claimed.solo_auc[k]),
             pos_mean=round(pos.mean(), 4), neg_mean=round(neg.mean(), 4))
    if binary: d.update(pos_ones=int(pos.sum()), neg_ones=int(neg.sum()))
    out[k] = d; print(k, d)
print("nvd_status of positives:", v.nvd_status[y == 1].value_counts().to_dict())
print("nvd_status all:", v.nvd_status.value_counts().to_dict())
print("missing vuln rows:", int(v.nvd_status.isna().sum()))
json.dump(out, open(S + "ld_1_result.json", "w"), indent=1)
