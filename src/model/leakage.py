"""Leakage table: solo AUC of every excluded and used column on the 2025 test pool.

Run: .venv/bin/python src/model/leakage.py
Writes results/leakage_table.csv (column, used_in_model, solo_auc, reason), its .meta.json (with
bootstrap 95% CIs) and merges results/claims_model_drift.json.

A solo AUC here measures the leak size in the BACKTEST (2025 rows read from today's NVD files). The README
says the leak is stronger for 2026 rows; that cannot be measured without 2026 labels.
"""
import numpy as np
import pandas as pd

import metrics as M
from pool import ROOT, data_dir, load_pool
from reproduce_first_pass import EXPLOIT_WORDING
from sidecar import claim, merge_claims, write_meta

SCRIPT = "src/model/leakage.py"
OUT = "results/leakage_table.csv"
N_BOOT, SEED = 1000, 0

# News outlets and threat-intel research blogs (www. stripped). Short on purpose: a transparent rule, not a classifier.
NEWS_DOMAINS = {
    "bleepingcomputer.com", "theregister.com", "thehackernews.com", "securityweek.com", "darkreading.com",
    "therecord.media", "arstechnica.com", "wired.com", "krebsonsecurity.com", "techcrunch.com",
    "securityaffairs.com", "helpnetsecurity.com", "unit42.paloaltonetworks.com", "securelist.com",
    "welivesecurity.com", "greynoise.io", "labs.greynoise.io", "huntress.com", "volexity.com", "mandiant.com",
    "research.checkpoint.com", "blog.talosintelligence.com", "crowdstrike.com", "labs.watchtowr.com",
}
AV_ORDER = {"NETWORK": 3, "ADJACENT_NETWORK": 2, "LOCAL": 1, "PHYSICAL": 0}


def reference_flags(ids):
    """Per CVE in `ids`: any news/threat link, any X-Force link, any link tagged Exploit (0 if no reference)."""
    parts = []
    for c in pd.read_csv(data_dir() / "references.csv", usecols=["cve_id", "domain", "tags"], chunksize=500_000):
        c = c[c.cve_id.isin(ids)]
        dom = c.domain.fillna("").str.lower().str.removeprefix("www.")
        tags = c.tags.fillna("")
        parts.append(pd.DataFrame({
            "cve_id": c.cve_id,
            "news": (tags.str.contains("Press/Media Coverage", regex=False) | dom.isin(NEWS_DOMAINS)).astype(int),
            "xforce": dom.str.contains("exchange.xforce", regex=False).astype(int),
            "exploit_tag": tags.str.split(";").apply(lambda t: "Exploit" in [x.strip() for x in t]).astype(int),
        }))
    return pd.concat(parts).groupby("cve_id").max().reindex(ids, fill_value=0)


def product_ids(ids):
    found = set()
    for c in pd.read_csv(data_dir() / "affected_products.csv", usecols=["cve_id"], chunksize=1_000_000):
        found.update(c.cve_id[c.cve_id.isin(ids)])
    return found


def rows(t):
    ids = pd.Index(t.cve_id)
    ref = reference_flags(ids)
    prods = product_ids(ids)
    v = lambda s: np.asarray(s, dtype=float)
    return [
        ("nvd_status_analysed", "no", v(t.nvd_status.isin(["Analyzed", "Modified"])),
         "1 if NVD status Analyzed/Modified (today's status). NIST analyses attacked CVEs first. README: leaks"),
        ("n_affected_cpes", "no", v(t.n_affected_cpes.fillna(0)),
         "Product (CPE) count from today's NVD file; filled in by NIST analysis, which reaches attacked CVEs first. README: leaks"),
        ("n_references", "no", v(t.n_references.fillna(0)),
         "Reference count from today's file; links are added after attacks. README: leaks"),
        ("cvss3_blank", "no", v(t.cvss3_score.isna()),
         "1 if cvss3_score blank. Blank-score pattern reflects NIST review order. README: leaks"),
        ("cwe_blank", "no", v(t.cwe_ids.isna()),
         "1 if cwe_ids blank. Blank pattern reflects NIST review order"),
        ("has_affected_product", "no", v(t.cve_id.isin(prods)),
         "1 if any affected_products.csv row (today's file); product lists come from NIST analysis"),
        ("ref_news_threat_link", "no", v(ref.news),
         "1 if a reference is tagged Press/Media Coverage or its domain is in NEWS_DOMAINS (24 news/threat sites, leakage.py)"),
        ("ref_xforce_link", "no", v(ref.xforce),
         "1 if a reference domain contains exchange.xforce (IBM X-Force Exchange). Treated as leak-prone (data guide)"),
        ("ref_exploit_tag", "no", v(ref.exploit_tag),
         "1 if a reference is tagged Exploit. Tags and links are today's, often added after attacks"),
        ("desc_exploitation_wording", "no", v(t.description.fillna("").str.contains(EXPLOIT_WORDING, case=False, regex=True)),
         "1 if today's description matches EXPLOIT_WORDING (exploited in the wild, CISA, KEV...); text may be edited later"),
        ("epss", "yes", v(t.epss_f),
         "EPSS at snapshot month end, blank as -1. As-of value from the signals file"),
        ("any_public_exploit", "yes", v(t.anyx),
         "1 if any of Exploit-DB/Metasploit/Nuclei/GitHub PoC flags at snapshot month end. As-of value"),
        ("n_exploit_flags", "yes", v(t.nx),
         "Number of the 4 exploit flags set at snapshot month end. As-of value"),
        ("asg_rate", "yes", v(t.asg_rate),
         "Assigner KEV rate from KEV rows dated before the snapshot month (CVEs published 2021+). Assigner is today's value"),
        ("cvss3_score", "ablation only", v(t.cvss3),
         "Today's NVD CVSS3 score, blank as -1 (so it also carries the blank pattern). Ablation only"),
        ("attack_vector", "ablation only", v(t.attack_vector.map(AV_ORDER).fillna(-1)),
         "Today's NVD value: NETWORK 3, ADJACENT 2, LOCAL 1, PHYSICAL 0, blank -1. Ablation only"),
    ]


def main():
    pool = load_pool()
    t = pool[pool.ym >= "2025-01"].reset_index(drop=True)
    y = t.y.to_numpy()
    rng = np.random.default_rng(SEED)
    boots = []
    while len(boots) < N_BOOT:  # paired resamples, shared by every column
        i = rng.integers(0, len(y), len(y))
        if y[i].sum():
            boots.append(i)

    out, ci = [], {}
    for name, used, s, reason in rows(t):
        a = M.auc(y, s)
        if s.min() == s.max():
            reason = "CONSTANT in this pool (AUC 0.5 by definition). " + reason
        if a < 0.5:  # natural direction is inverse: flip so higher = more likely exploited
            s, a = -s, M.auc(y, -s)
            reason = "FLIPPED (lower = more exploited). " + reason
        assert len(reason) < 160, (name, len(reason))
        out.append({"column": name, "used_in_model": used, "solo_auc": round(a, 4), "reason": reason})
        q = [M.auc(y[i], s[i]) for i in boots]
        ci[name] = [float(np.percentile(q, 2.5)), float(np.percentile(q, 97.5))]
    df = pd.DataFrame(out, columns=["column", "used_in_model", "solo_auc", "reason"])
    df.to_csv(ROOT / OUT, index=False)

    write_meta(OUT, SCRIPT, {
        "pool": "2025 test pool, snapshots 2025-01..2025-09, label y", "rows": len(t), "positives": int(y.sum()),
        "solo_auc_ci95": ci, "ci_method": f"{N_BOOT} paired row bootstrap resamples, seed {SEED}, percentile 95%",
        "news_domains": sorted(NEWS_DOMAINS),
        "note": "Measures leak size in the 2025 backtest only; README says the leak is stronger for 2026 rows (no 2026 labels)."})
    n = merge_claims({f"leakage.solo_auc.{r['column']}": claim(
        f"Solo AUC of {r['column']} (used_in_model={r['used_in_model']}) on the 2025 test pool", r["solo_auc"],
        "fraction", SCRIPT, OUT) for r in out})
    print(df.drop(columns="reason").to_string(index=False))
    print(f"rows {len(t)} positives {int(y.sum())}; wrote {OUT}, meta, {n} claims")


if __name__ == "__main__":
    main()
