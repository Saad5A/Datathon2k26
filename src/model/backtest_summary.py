"""Backtest summary for the UI (docs/INTERFACES.md section 1), one object per fold.

Run: .venv/bin/python src/model/backtest_summary.py
Reads results/model_candidates.json, results/first_pass_repro.json, results/claims_model.json; writes
results/backtest_summary.json. Copies values only (no recomputation). Every value sits beside the id of the claim it
comes from ("claim_ids", null when no claim exists); the script asserts each claim's value equals the copied value.
"""
import json
import math

from pool import ROOT

OUT = ROOT / "results" / "backtest_summary.json"
MC = json.loads((ROOT / "results" / "model_candidates.json").read_text())
FP = json.loads((ROOT / "results" / "first_pass_repro.json").read_text())
CLAIMS = json.loads((ROOT / "results" / "claims_model.json").read_text())


def check(cid, value):
    if cid is None:
        return None
    assert cid in CLAIMS, cid
    assert math.isclose(CLAIMS[cid]["value"], value, rel_tol=1e-9, abs_tol=1e-12), (cid, CLAIMS[cid]["value"], value)
    return cid


def entry(vals, ids):
    """vals/ids: flat dicts with the same keys; ci95 and ranges are [lo, hi] pairs with a pair of ids."""
    out, cids = {}, {}
    for k, v in vals.items():
        if isinstance(v, list):
            cids[k] = [check(i, x) for i, x in zip(ids[k], v)]
        else:
            cids[k] = check(ids[k], v)
        out[k] = v
    ci = out.pop("ci95_top500")
    out["ci95"] = {"top500": ci}
    cids["ci95"] = {"top500": cids.pop("ci95_top500")}
    out["claim_ids"] = cids
    return out


def from_p3(fold, name, group):
    e = MC[group][fold][name]
    m, ci = e["median"], e["ci95_seed0"]["top500_expected"]
    p = f"p3.{fold}.{name}"
    vals = {"top500": m["top500_cve_id"], "top250": m["top250_cve_id"], "auc": m["auc"], "avg_precision": m["avg_precision"],
            "median_rank": m["median_rank_cve_id"], "work_to_catch_50pct": m["work50_cve_id"], "ci95_top500": ci}
    ids = {"top500": f"{p}.top500_cve_id.median", "top250": f"{p}.top250_cve_id.median", "auc": f"{p}.auc.median",
           "avg_precision": f"{p}.avg_precision.median", "median_rank": f"{p}.median_rank_cve_id.median",
           "work_to_catch_50pct": f"{p}.work50_cve_id.median",
           "ci95_top500": [f"{p}.ci95_lo.top500_expected", f"{p}.ci95_hi.top500_expected"]}
    if m["top500_worst"] != m["top500_best"]:
        vals["top500_tie_range"] = [m["top500_worst"], m["top500_best"]]
        ids["top500_tie_range"] = [f"{p}.top500_worst.median", f"{p}.top500_best.median"]
    if group == "candidates":
        vals["top500_seed_range"] = [e["min"]["top500_cve_id"], e["max"]["top500_cve_id"]]
        ids["top500_seed_range"] = [f"{p}.top500_cve_id.min", f"{p}.top500_cve_id.max"]
    return entry(vals, ids)


def from_first_pass(r, prefix, full_claims):
    """first_pass_repro.json method result. Fold 2 (section E) has claims only for top500, AUC and AP."""
    d, t, ci = r["deterministic"], r["ties_top500"], r["ci95"]["top500_expected"]
    has = lambda key: f"{prefix}.{key}" if full_claims else None
    vals = {"top500": d["top500_cve_id"], "top250": d["top250_cve_id"], "auc": d["auc"], "avg_precision": d["avg_precision"],
            "median_rank": d["median_rank_cve_id"], "work_to_catch_50pct": d["work50_cve_id"], "ci95_top500": ci}
    ids = {"top500": f"{prefix}.top500_cve_id", "top250": has("top250_cve_id"), "auc": f"{prefix}.auc",
           "avg_precision": f"{prefix}.avg_precision", "median_rank": None, "work_to_catch_50pct": has("work50_cve_id"),
           "ci95_top500": [has("ci95_lo.top500_expected"), has("ci95_hi.top500_expected")]}
    if t["worst"] != t["best"]:
        vals["top500_tie_range"] = [t["worst"], t["best"]]
        ids["top500_tie_range"] = [has("top500_worst"), has("top500_best")]
    return entry(vals, ids)


def main():
    out = {"notes": [
        "Backtest only: 2025 CVEs scored with information available at their publication month, checked against later KEV "
        "additions. This is NOT an estimate of 2026 accuracy; there are no 2026 labels.",
        "Few positives: fold 1 has 52 exploited CVEs in its test pool and fold 2 has 32, so one hit is about 2% (fold 1) to "
        "3% (fold 2) of all positives. Read every number with its interval.",
        "The top-500 difference between 'ours' and 'exploit_then_epss' is not robust: it changes sign between folds and "
        "seed sets, and its paired bootstrap interval (seed set 0) includes 0. 'ours' ranks better on AUC in both folds, but that "
        "interval also includes 0 for seed set 0.",
        "'ours' = C1 (HGB on exploit signals + assigner KEV history + masked description text score), trained with "
        "time-safe labels (KEV additions only up to the train end). Values are medians over 5 seed sets; "
        "top500_seed_range is [lowest, highest] over the seed sets; ci95 for 'ours' is from seed set 0.",
        "'ours_first_pass_optimistic' (fold 1 only) is the first-pass model with train labels that overlap the test "
        "period (KEV additions to 2025-12-31). It is optimistic and is shown only for comparison; do not quote it as the result.",
        "top500 and top250 break tied scores by cve_id; top500_tie_range is [worst, best] over all orders of the tied rows "
        "and appears only where ties change the count. ci95.top500 is the 95% bootstrap interval of the tie-neutral "
        "expected top-500 hits (2000 resamples). median_rank and work_to_catch_50pct use ties by cve_id.",
        "work_to_catch_50pct = how many CVEs from the top of the ranking you must fix to catch half of the exploited ones.",
        "claim_ids name the ledger entry (results/claims_model.json) behind each value; null means no claim exists, so "
        "the value must not be published. Check each claim's status before display."]}
    for fold, fr in MC["folds"].items():
        o = {"pool_size": fr["test_rows"], "n_positives": fr["test_positives"],
             "split": (f"train snapshots {fr['train_months']} ({fr['train_rows']} rows, {fr['train_positives']} positives, "
                       f"labels = KEV additions up to {fr['train_label_cap']}); test snapshots {fr['test_months']} "
                       f"(labels = KEV additions within 365 days of the snapshot end, capped at 2025-12-31)"),
             "claim_ids": {"pool_size": check(f"p3.{fold}.test_rows", fr["test_rows"]),
                           "n_positives": check(f"p3.{fold}.test_positives", fr["test_positives"])}}
        for n in ("cvss3", "epss", "exploit_then_epss"):
            o[n] = from_p3(fold, n, "baselines")
        o["assigner_only"] = (from_first_pass(FP["primary"]["assigner_only"], "primary.assigner_only", True) if fold == "fold1"
                              else from_first_pass(FP["E_second_fold"]["methods"]["assigner_only"], "e.assigner_only", False))
        o["ours"] = from_p3(fold, "C1", "candidates")
        if fold == "fold1":
            o["ours_first_pass_optimistic"] = from_first_pass(FP["primary"]["hgb_signals_assigner_text"],
                                                              "primary.hgb_signals_assigner_text", True)
            o["ours_first_pass_optimistic"]["label"] = ("OPTIMISTIC: first-pass model, train labels overlap the test period; "
                                                        "comparison only")
        out[fold] = o
    # The assigner-only baseline does not depend on training labels: its test pool must match the fold's.
    assert FP["pool"]["test_rows"] == MC["folds"]["fold1"]["test_rows"]
    assert FP["E_second_fold"]["test_rows"] == MC["folds"]["fold2"]["test_rows"]
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
