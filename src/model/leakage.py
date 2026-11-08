"""Leakage table: solo AUC of every excluded and used column on the 2025 test pool.

Run: .venv/bin/python src/model/leakage.py
Writes results/leakage_table.csv (column, used_in_model, solo_auc, reason), its .meta.json (with
bootstrap 95% CIs and exact bounds on positive counts) and merges results/claims_model_drift.json.

A solo AUC here measures the leak size in the BACKTEST (2025 rows read from today's NVD files). The README
warns these fields leak for 2026 rows; the 2026 leak size cannot be measured (no 2026 labels).
"""
import json

import numpy as np
import pandas as pd
from scipy.stats import beta

import candidates as C
import metrics as M
from pool import ROOT, data_dir, load_kev, load_pool
from reproduce_first_pass import text_test_score, text_vectors
from reproduce_first_pass import EXPLOIT_WORDING
from sidecar import claim, merge_claims, write_meta

SCRIPT = "src/model/leakage.py"
OUT = "results/leakage_table.csv"
N_BOOT, SEED = 1000, 0

# News outlets and threat-intel / attack-research blogs (www. stripped). Hand-picked and incomplete on purpose: a
# transparent rule, not a classifier, so its AUC is a lower bound on the news/threat-link leak. Excluded after a look
# at the URLs: sophos.com (Sophos's own product advisories), tenable.com (own research disclosures, product
# advisories, Nessus plugins), rapid7.com outside /blog/ (Metasploit module pages = exploit links, not news).
NEWS_DOMAINS = {
    "bleepingcomputer.com", "theregister.com", "thehackernews.com", "securityweek.com", "darkreading.com",
    "therecord.media", "arstechnica.com", "wired.com", "krebsonsecurity.com", "techcrunch.com",
    "securityaffairs.com", "helpnetsecurity.com", "unit42.paloaltonetworks.com", "securelist.com",
    "welivesecurity.com", "greynoise.io", "labs.greynoise.io", "huntress.com", "volexity.com", "mandiant.com",
    "research.checkpoint.com", "blog.talosintelligence.com", "crowdstrike.com", "labs.watchtowr.com",
    "horizon3.ai", "isc.sans.edu",
}
NEWS_URL_PARTS = ("rapid7.com/blog/",)
README_QUOTE = ("README 'Keep it fair': \"For 2026 vulnerabilities, `nvd_status`, `n_affected_cpes`, `n_references`, "
                "blank severity scores, and links to news or threat reports in `references.csv` can give part of the "
                "answer away, because NIST reviews attacked vulnerabilities first.\" DATA_DICTIONARY.md: \"can give "
                "much of the answer away\". The 2026 leak size cannot be measured (no 2026 labels).")
FACT_TEXT = {"nvd_status_Analyzed": "have NVD status Analyzed", "has_affected_product": "have an affected_products.csv row",
             "cvss3_present": "have a non-blank CVSS3 score", "cwe_present": "have non-blank cwe_ids"}
AV_ORDER = {"NETWORK": 3, "ADJACENT_NETWORK": 2, "LOCAL": 1, "PHYSICAL": 0}


def cp_lower(k, n):
    """Lower end of the exact (Clopper-Pearson) two-sided 95% interval for k successes in n."""
    return 0.0 if k == 0 else round(float(beta.ppf(0.025, k, n - k + 1)), 6)


def reference_flags(ids):
    """Per CVE in `ids`: any news/threat link, any X-Force link, any link tagged Exploit (0 if no reference)."""
    parts = []
    for c in pd.read_csv(data_dir() / "references.csv", usecols=["cve_id", "url", "domain", "tags"], chunksize=500_000):
        c = c[c.cve_id.isin(ids)]
        dom = c.domain.fillna("").str.lower().str.removeprefix("www.")
        tags = c.tags.fillna("")
        parts.append(pd.DataFrame({
            "cve_id": c.cve_id,
            "news": (tags.str.contains("Press/Media Coverage", regex=False) | dom.isin(NEWS_DOMAINS)
                     | c.url.fillna("").str.lower().str.contains("|".join(NEWS_URL_PARTS), regex=True)).astype(int),
            "xforce": dom.str.contains("exchange.xforce", regex=False).astype(int),
            "exploit_tag": tags.str.split(";").apply(lambda t: "Exploit" in [x.strip() for x in t]).astype(int),
        }))
    return pd.concat(parts).groupby("cve_id").max().reindex(ids, fill_value=0)


def product_ids(ids):
    found = set()
    for c in pd.read_csv(data_dir() / "affected_products.csv", usecols=["cve_id"], chunksize=1_000_000):
        found.update(c.cve_id[c.cve_id.isin(ids)])
    return found


def text_score(pool, t):
    """Selected model C1's text input on fold 1: masked-description TF-IDF + LR fit on 2024 rows with labels capped at
    2024-12-31, scored on the 2025 test rows. Same functions as candidates.py."""
    tr, te, y_tr = C.fold_data(pool, load_kev(), C.FOLDS["fold1"])
    assert (te.cve_id.to_numpy() == t.cve_id.to_numpy()).all(), "fold-1 test rows differ from the 2025 pool"
    Xtr, Xte = text_vectors(C.masked(tr), C.masked(te))
    return text_test_score(Xtr, y_tr, Xte)


def rows(t, txt):
    ids = pd.Index(t.cve_id)
    ref = reference_flags(ids)
    prods = product_ids(ids)
    v = lambda s: np.asarray(s, dtype=float)
    # Share of positives carrying each NIST-analysis value: the bootstrap CI of a value all positives share only
    # reflects the negatives, so these counts get an exact binomial bound instead (see main).
    facts = {"nvd_status_Analyzed": t.nvd_status.eq("Analyzed"), "has_affected_product": t.cve_id.isin(prods),
             "cvss3_present": t.cvss3_score.notna(), "cwe_present": t.cwe_ids.notna()}
    return facts, [
        ("nvd_status_analysed", "no", v(t.nvd_status.isin(["Analyzed", "Modified"])),
         "1 if NVD status Analyzed/Modified (today's status). NIST analyses attacked CVEs first. README: leaks"),
        ("n_affected_cpes", "no", v(t.n_affected_cpes.fillna(0)),
         "Product (CPE) count from today's NVD file; filled in by NIST analysis, which reaches attacked CVEs first. README: leaks"),
        ("n_references", "no", v(t.n_references.fillna(0)),
         "Reference count from today's file; links are often added after attacks. README: leaks"),
        ("cvss3_blank", "no", v(t.cvss3_score.isna()),
         "1 if cvss3_score blank. Blank-score pattern reflects NIST review order. README: leaks"),
        ("cwe_blank", "no", v(t.cwe_ids.isna()),
         "1 if cwe_ids blank. Blank pattern reflects NIST review order"),
        ("has_affected_product", "no", v(t.cve_id.isin(prods)),
         "1 if any affected_products.csv row (today's file); product lists come from NIST analysis"),
        ("ref_news_threat_link", "no", v(ref.news),
         f"Press/Media tag or one of {len(NEWS_DOMAINS)} news/threat domains + rapid7 blog (leakage.py). Hand-picked, "
         "incomplete list: AUC is a lower bound"),
        ("ref_xforce_link", "no", v(ref.xforce),
         "1 if a reference domain contains exchange.xforce (IBM X-Force Exchange). Treated as leak-prone (data guide)"),
        ("ref_exploit_tag", "no", v(ref.exploit_tag),
         "1 if a reference is tagged Exploit. Tags and links are today's, often added after attacks"),
        ("desc_exploitation_wording", "no", v(t.description.fillna("").str.contains(EXPLOIT_WORDING, case=False, regex=True)),
         "1 if today's description matches EXPLOIT_WORDING (exploited in the wild, CISA, KEV). Phase-3 plan masks it out "
         "before any text model"),
        ("epss", "yes", v(t.epss_f),
         "EPSS at snapshot month end, blank as -1. As-of value from the signals file"),
        ("any_public_exploit", "yes", v(t.anyx),
         "1 if any of Exploit-DB/Metasploit/Nuclei/GitHub PoC flags at snapshot month end. As-of value"),
        ("n_exploit_flags", "yes", v(t.nx),
         "Number of the 4 exploit flags set at snapshot month end. As-of value"),
        ("asg_rate", "yes", v(t.asg_rate),
         "Assigner KEV rate from KEV rows dated before the snapshot month (CVEs published 2021+). Assigner is today's value"),
        ("asg_kev", "yes", v(t.asg_kev),
         "Assigner KEV count from KEV rows dated before the snapshot month (CVEs published 2021+). Assigner is today's value"),
        ("txt_masked_tfidf", "yes", v(txt),
         "Today's description text, exploitation wording masked; TF-IDF+LR on 2024 rows. Residual risk: descriptions edited after attacks"),
        ("asg_rate_24m", "no", v(t.asg24_rate),
         "Assigner KEV rate over the 24 months before the snapshot month (C2 input, not selected). Assigner is today's value"),
        ("cvss3_score", "no", v(t.cvss3),
         "Today's NVD CVSS3 score, blank as -1 (also carries the blank pattern). Ablation only, not in the model"),
        ("attack_vector", "no", v(t.attack_vector.map(AV_ORDER).fillna(-1)),
         "Today's NVD value: NETWORK 3, ADJACENT 2, LOCAL 1, PHYSICAL 0, blank -1. Ablation only, not in the model"),
    ]


def main():
    pool = C.add_window_features(load_pool())
    t = pool[pool.ym >= "2025-01"].reset_index(drop=True)
    txt = text_score(pool, t)
    y = t.y.to_numpy()
    rng = np.random.default_rng(SEED)
    boots = []
    while len(boots) < N_BOOT:  # paired resamples, shared by every column
        i = rng.integers(0, len(y), len(y))
        if y[i].sum():
            boots.append(i)

    out, ci = [], {}
    facts, table = rows(t, txt)
    for name, used, s, reason in table:
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

    pos = y == 1
    n_pos = int(pos.sum())
    positive_facts = {}
    for name, f in facts.items():
        k = int(f.to_numpy()[pos].sum())
        positive_facts[name] = {"positives_with_value": k, "positives": n_pos,
                                "cp95_lower_share": cp_lower(k, n_pos),
                                "negatives_share_with_value": round(float(f.to_numpy()[~pos].mean()), 6)}
    write_meta(OUT, SCRIPT, {
        "pool": "2025 test pool, snapshots 2025-01..2025-09, label y", "rows": len(t), "positives": n_pos,
        "solo_auc_ci95": ci, "ci_method": f"{N_BOOT} paired row bootstrap resamples, seed {SEED}, percentile 95%",
        "ci_caveat": ("For a value carried by every positive (or none), AUC = 1 - 0.5 x share of negatives with it, so "
                      "the bootstrap CI only reflects the negatives and is near zero width. Quote positive_facts instead."),
        "positive_facts": positive_facts,
        "positive_facts_method": "Clopper-Pearson exact two-sided 95% interval, lower end (Beta(0.025; k, n-k+1)).",
        "news_rule": {"tag": "Press/Media Coverage", "domains": sorted(NEWS_DOMAINS), "url_parts": list(NEWS_URL_PARTS)},
        "note": "Measures leak size in the 2025 backtest only. " + README_QUOTE})
    claims = {f"leakage.solo_auc.{r['column']}": claim(
        f"Solo AUC of {r['column']} (used_in_model={r['used_in_model']}) on the 2025 test pool", r["solo_auc"],
        "fraction", SCRIPT, OUT) for r in out}
    for name, f in positive_facts.items():
        claims[f"leakage.positives.{name}.count"] = claim(
            f"2025 test positives with {name} (of {n_pos})", f["positives_with_value"], "count", SCRIPT, OUT)
        claims[f"leakage.positives.{name}.cp95_lower"] = claim(
            f"Clopper-Pearson 95% lower bound on the share of 2025 test positives with {name}",
            f["cp95_lower_share"], "fraction", SCRIPT, OUT)
        claims[f"leakage.negatives.{name}.share"] = claim(
            f"Share of the {int((~pos).sum()):,} non-exploited 2025 test CVEs that {FACT_TEXT[name]}",
            f["negatives_share_with_value"], "fraction", SCRIPT, OUT)
    n = merge_claims(claims)
    print(json.dumps(positive_facts, indent=1))
    print(df.drop(columns="reason").to_string(index=False))
    print(f"rows {len(t)} positives {int(y.sum())}; wrote {OUT}, meta, {n} claims")


if __name__ == "__main__":
    assert cp_lower(0, 52) == 0.0 and abs(cp_lower(52, 52) - 0.025 ** (1 / 52)) < 1e-6  # k = n: (alpha/2)^(1/n)
    main()
