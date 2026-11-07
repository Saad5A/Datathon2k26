"""Auditor: domain-level positive rate among test-pool CVEs; effect of adding obvious missed research/news domains."""
import json, numpy as np, pandas as pd, sys
R = "/Users/aahmad/Working/datathon/code/Datathon2k26/"; S = R + "audit/scratch/"
sys.path.insert(0, S); 
p = pd.read_parquet(S + "my_pool2.parquet"); te = p[p.month >= "2025-01"].reset_index(drop=True)
pos = set(te.cve_id[te.y == 1])
r = pd.read_parquet(S + "ld_refs_test.parquet"); r["dom"] = r.domain.fillna("").str.lower().str.removeprefix("www.")
t = r.groupby("dom").cve_id.agg(lambda s: (s.nunique(), len(set(s) & pos)))
t = pd.DataFrame(t.tolist(), index=t.index, columns=["cves", "pos"]); t = t[t.pos > 0].assign(rate=lambda d: d.pos / d.cves)
print(t.sort_values("rate", ascending=False).head(30).to_string())
NEWS = set(json.load(open(R + "results/leakage_table.meta.json"))["news_domains"])

from scipy.stats import rankdata
def auc(y, s):
    rk = rankdata(s); n1 = y.sum(); n0 = len(y) - n1; return (rk[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
y = te.y.to_numpy()
press = r.tags.fillna("").str.contains("Press/Media Coverage", regex=False)
for name, extra in [("as claimed", set()), ("+horizon3.ai", {"horizon3.ai"}),
                    ("+horizon3,vicarius,intezer,akamai,rapid7,tenable,sophos,doublepulsar", {"horizon3.ai","vicarius.io","intezer.com","akamai.com","rapid7.com","tenable.com","sophos.com","news.sophos.com","doublepulsar.com"})]:
    f = set(r.cve_id[press | r.dom.isin(NEWS | extra)])
    x = te.cve_id.isin(f).to_numpy().astype(float)
    print(f"{name}: auc {auc(y, x):.4f} pos {int(x[y==1].sum())} neg {int(x[y==0].sum())}")
print("press-tag only:", int(te.cve_id.isin(set(r.cve_id[press]))[te.y==1].sum()), "pos CVEs")
