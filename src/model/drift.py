"""Drift: 2025 backtest test pool vs the 2026 scoreboard.

Run: .venv/bin/python src/model/drift.py
Writes results/drift_summary.json, its .meta.json and merges results/claims_model_drift.json.
Describes distributions only: there are no 2026 labels, so nothing here is a 2026 accuracy.
"""
import json

import pandas as pd

from pool import (FLAGS, ROOT, assigner_history, data_dir, kev_with_assigner, load_kev, load_pool,
                  load_vulns)
from sidecar import claim, merge_claims, write_meta

SCRIPT = "src/model/drift.py"
OUT = "results/drift_summary.json"
SCOREBOARD_ROWS = 72_670  # README / DATA_DICTIONARY
GITHUB, VULNCHECK = "security-advisories@github.com", "disclosure@vulncheck.com"


def product_ids(ids):
    found = set()
    for c in pd.read_csv(data_dir() / "affected_products.csv", usecols=["cve_id"], chunksize=1_000_000):
        found.update(c.cve_id[c.cve_id.isin(ids)])
    return found


def missing(df, month_col):
    """Per-month and overall shares. df has no_product, cvss3_blank, epss (raw, NaN = blank), anyx."""
    cols = {"no_affected_product": df.no_product, "cvss3_blank": df.cvss3_blank,
            "epss_blank": df.epss.isna(), "any_public_exploit": df.anyx == 1, "epss_gt_0_1": df.epss > 0.1}
    f = pd.DataFrame(cols).astype(float).assign(m=df[month_col].to_numpy())
    by = f.groupby("m").mean()
    out = {m: {"rows": int(n), **{k: round(v, 6) for k, v in by.loc[m].items()}}
           for m, n in f.groupby("m").size().items()}
    out["all"] = {"rows": len(f), **{k: round(v, 6) for k, v in f.drop(columns="m").mean().items()}}
    return out


def assigner_shares(a):
    return a.fillna("(no assigner)").value_counts(normalize=True)


def main():
    v = load_vulns(cols=["cve_id", "published", "assigner", "cvss3_score"])  # CVEs published 2021+
    k = load_kev()
    pool = load_pool()
    t = pool[pool.ym >= "2025-01"].copy()
    sb = pd.read_csv(data_dir() / "scoreboard_2026.csv", dtype={"snapshot_month": str})
    assert len(sb) == SCOREBOARD_ROWS, len(sb)
    sb = sb.merge(v[["cve_id", "assigner", "cvss3_score"]], on="cve_id", how="left", validate="one_to_one")
    sb["anyx"] = sb[FLAGS].fillna(0).max(axis=1)

    prods = product_ids(set(t.cve_id) | set(sb.cve_id))
    for d in (t, sb):
        d["no_product"] = ~d.cve_id.isin(prods)
        d["cvss3_blank"] = d.cvss3_score.isna()

    # Assigner KEV count before the snapshot month, same function and inputs as the pool's asg_kev feature.
    kv = kev_with_assigner(k, v)
    hist = {m: assigner_history(kv, v, m)[1] for m in sorted(set(sb.snapshot_month) | set(t.ym))}
    t_kev = pd.Series([hist[m].get(a, 0) for m, a in zip(t.ym, t.assigner)], index=t.index)
    assert (t_kev == t.asg_kev).all(), "recomputed asg_kev differs from the cached pool"
    sb_kev = pd.Series([hist[m].get(a, 0) for m, a in zip(sb.snapshot_month, sb.assigner)], index=sb.index)

    vm = v[(v.ym >= "2024-01") & (v.ym <= "2026-09")].groupby("ym").size()
    s25, s26 = assigner_shares(t.assigner), assigner_shares(sb.assigner)
    top = lambda s: [{"assigner": a, "share_2025_pool": round(float(s25.get(a, 0)), 6),
                      "share_2026_scoreboard": round(float(s26.get(a, 0)), 6)} for a in s.head(15).index]
    no_kev = lambda flag, months: {**{m: round(float(x), 6) for m, x in flag.groupby(months.to_numpy()).mean().items()},
                                   "all": round(float(flag.mean()), 6)}

    out = {
        "periods": {"2025_pool": "backtest test pool: CVEs published 2025-01..2025-09, not on KEV at snapshot "
                                 "(src/model/pool.py), snapshot = publish month",
                    "2026_scoreboard": "scoreboard_2026.csv, joined to vulnerabilities.csv on cve_id"},
        "rows": {"2025_pool": len(t), "2026_scoreboard": len(sb),
                 "2026_scoreboard_without_vulnerabilities_row": int(sb.assigner.isna().sum())},
        "monthly_volume": {
            "cves_published_per_month_vulnerabilities_csv": {m: int(n) for m, n in vm.items()},
            "pool_rows_per_snapshot_month_2025": {m: int(n) for m, n in t.groupby("ym").size().items()},
            "scoreboard_rows_per_snapshot_month_2026": {m: int(n) for m, n in sb.groupby("snapshot_month").size().items()},
        },
        "assigner_mix": {
            "distinct_assigners": {"2025_pool": int(t.assigner.nunique()), "2026_scoreboard": int(sb.assigner.nunique())},
            "top15_2025_pool": top(s25), "top15_2026_scoreboard": top(s26),
        },
        "missing_data_by_snapshot_month": {"2025_pool": missing(t, "ym"), "2026_scoreboard": missing(sb, "snapshot_month")},
        "assigner_no_prior_kev_share": {"2025_pool": no_kev(t_kev == 0, t.ym),
                                        "2026_scoreboard": no_kev(sb_kev == 0, sb.snapshot_month)},
        "notes": [
            "June 2026 signals are missing, so June 2026 CVEs use snapshot_month 2026-07: the 2026-07 scoreboard "
            "group holds June and July publications. 2026 per-month rates are grouped by snapshot_month.",
            "The 2026 scoreboard excludes CVEs already on KEV at their snapshot (built by the organisers with KEV data "
            "after 2025-12-31 that we do not have). The 2025 pool applies the same exclusion with our KEV file.",
            "assigner_no_prior_kev_share: assigner had 0 KEV rows with date_added before the first day of the snapshot "
            "month; assigner attached via vulnerabilities.csv for CVEs published 2021+ (same code as the asg_kev "
            "feature). Our KEV file ends 2025-12-31, so 2026 KEV additions are invisible: the 2026 share is an upper bound.",
            "cvss3 and product presence are today's NVD values: 2026 CVEs have had less time for NIST analysis "
            "(51,046 of 92,205 2026 CVEs unreviewed per README), so blank rates mix real drift with review backlog.",
            "epss_blank and any_public_exploit come from snapshot-month signals; Feb 2025 signals miss about 14,500 "
            "CVEs and EPSS changed model in March 2025, so 2025-02 and 2025-01 EPSS rates are not comparable to later months.",
            "monthly_volume.cves_published_per_month counts today's vulnerabilities.csv (rejected CVEs removed).",
            f"GitHub advisories = assigner {GITHUB} only (product-cna@github.com is separate); VulnCheck = {VULNCHECK}.",
            "No 2026 accuracy is claimed anywhere here: there are no 2026 labels.",
        ],
    }
    (ROOT / OUT).write_text(json.dumps(out, indent=2) + "\n")
    write_meta(OUT, SCRIPT)

    sbm = out["monthly_volume"]["scoreboard_rows_per_snapshot_month_2026"]
    miss = out["missing_data_by_snapshot_month"]
    nk = out["assigner_no_prior_kev_share"]
    c = lambda text, value, unit="fraction": claim(text, value, unit, SCRIPT, OUT)
    claims = {f"drift.scoreboard_rows.{m}": c(f"2026 scoreboard rows with snapshot_month {m}", n, "count")
              for m, n in sbm.items()}
    claims["drift.scoreboard_rows.total"] = c("2026 scoreboard rows", len(sb), "count")
    claims["drift.pool_rows_2025"] = c("2025 test pool rows (published 2025-01..09)", len(t), "count")
    for name, a in (("github_advisories", GITHUB), ("vulncheck", VULNCHECK)):
        claims[f"drift.assigner_share.{name}.2025_pool"] = c(f"Share of 2025 pool rows assigned by {a}", s25.get(a, 0))
        claims[f"drift.assigner_share.{name}.2026_scoreboard"] = c(f"Share of 2026 scoreboard rows assigned by {a}", s26.get(a, 0))
    for p in ("2025_pool", "2026_scoreboard"):
        claims[f"drift.distinct_assigners.{p}"] = c(f"Distinct assigners, {p}", out["assigner_mix"]["distinct_assigners"][p], "count")
        claims[f"drift.no_prior_kev_share.{p}"] = c(
            f"Share of {p} rows whose assigner had 0 KEV rows before the snapshot month", nk[p]["all"])
        for k_ in ("no_affected_product", "cvss3_blank", "epss_blank", "any_public_exploit", "epss_gt_0_1"):
            claims[f"drift.{k_}.{p}.all"] = c(f"Share of {p} rows: {k_}", miss[p]["all"][k_])
    for m in ("2026-08", "2026-09"):
        claims[f"drift.no_affected_product.2026_scoreboard.{m}"] = c(
            f"Share of 2026 scoreboard rows with snapshot_month {m} with no affected_products row",
            miss["2026_scoreboard"][m]["no_affected_product"])
    n = merge_claims(claims)
    print(json.dumps({"scoreboard_rows": sbm, "distinct": out["assigner_mix"]["distinct_assigners"],
                      "no_prior_kev": {p: nk[p]["all"] for p in nk},
                      "missing_all": {p: miss[p]["all"] for p in miss},
                      "no_product_2026": {m: miss["2026_scoreboard"][m]["no_affected_product"] for m in sbm}}, indent=1))
    for p, s in (("2025", s25), ("2026", s26)):
        print(p, {a: round(float(s.get(a, 0)), 4) for a in (GITHUB, VULNCHECK)})
    print(f"wrote {OUT}, meta, {n} claims")


if __name__ == "__main__":
    main()
