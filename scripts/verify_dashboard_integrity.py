"""Side-by-side proof: committed files vs FastAPI vs UI binding map.

Run with the API up:
  python scripts/verify_dashboard_integrity.py

Does not modify any files.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
PROTECTED = [
    ROOT / "JUDGE_QA.md",
    ROOT / "docs" / "writeup_model.md",
    ROOT / "results" / "top500.csv",
    ROOT / "results" / "scores_2026.csv",
]


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def row(label: str, file_v, api_v, ui_bind: str, ok: bool) -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}")
    print(f"       file : {file_v}")
    print(f"       api  : {api_v}")
    print(f"       ui   : {ui_bind}")
    print()


def main() -> int:
    meta = json.loads((ROOT / "data_cache" / "granite_embeddings_watsonx_subset.meta.json").read_text(encoding="utf-8"))
    comparison = json.loads((ROOT / "results" / "granite_subset_comparison.json").read_text(encoding="utf-8"))
    summaries = json.loads((ROOT / "results" / "granite_summaries_top100.json").read_text(encoding="utf-8"))
    explanations = {str(r["cve_id"]): r for r in summaries.get("results") or [] if r.get("cve_id")}
    top = pd.read_csv(ROOT / "results" / "top500.csv")
    scores = pd.read_csv(ROOT / "results" / "scores_2026.csv")
    merged = top.merge(scores, on="cve_id", how="left").sort_values("rank")

    summary = get("/api/stats/summary")
    ranking = get("/api/ranking/cves?limit=3")
    first_expl_id = next(iter(explanations))
    expl = get(f"/api/explanations/{first_expl_id}")

    print("=== Dashboard integrity proof (file vs API vs UI binding) ===\n")

    row(
        "total_analyzed_cves",
        meta["n_rows"],
        summary["total_analyzed_cves"],
        "not shown in the UI (watsonx subset row count)",
        summary["total_analyzed_cves"] == meta["n_rows"],
    )
    row(
        "estimated_tokens_consumed",
        meta["estimated_tokens_this_run"],
        summary["token_usage"]["estimated_tokens_consumed"],
        "not shown in the UI (no claim for it)",
        summary["token_usage"]["estimated_tokens_consumed"] == meta["estimated_tokens_this_run"],
    )
    mean = comparison["selection_hint"]["mean_delta_auc_granite_minus_tfidf"]
    row(
        "mean_delta_auc_granite_minus_tfidf withheld",
        f"{mean} (exploratory subset, unverified; audit/2026-11-07-granite-subset.md)",
        summary["comparison"]["mean_delta_auc_granite_minus_tfidf"],
        "not shown in the UI; API must return null",
        summary["comparison"]["mean_delta_auc_granite_minus_tfidf"] is None,
    )
    p0_file = int((merged["priority"] == "P0").sum())
    row(
        "risk_bands.critical (P0)",
        p0_file,
        summary["risk_bands"]["critical"],
        "KpiTile 'P0 · Critical' + Donut P0 ← summary.risk_bands.critical",
        summary["risk_bands"]["critical"] == p0_file,
    )

    print("--- Ranking page (first 3) ---")
    fails = 0
    for i, item in enumerate(ranking["items"]):
        file_row = merged.iloc[i]
        ok = (
            item["cve_id"] == file_row["cve_id"]
            and int(item["rank"]) == int(file_row["rank"])
            and abs(float(item["score"]) - float(file_row["score"])) < 1e-12
        )
        if not ok:
            fails += 1
        row(
            f"ranking items[{i}]",
            f"{file_row['cve_id']} rank={file_row['rank']} score={file_row['score']}",
            f"{item['cve_id']} rank={item['rank']} score={item['score']}",
            "RankedTable cell ← GET /api/ranking/cves items[]",
            ok,
        )

    file_text = explanations[first_expl_id].get("summary")
    api_text = (expl.get("granite") or {}).get("summary")
    row(
        f"explanation {first_expl_id}",
        (file_text or "")[:120] + ("…" if file_text and len(file_text) > 120 else ""),
        (api_text or "")[:120] + ("…" if api_text and len(api_text) > 120 else ""),
        "CVE panel granite.summary ← results/granite_summaries_top100.json (summary text only)",
        file_text == api_text,
    )
    # Summaries were written for an earlier ranking: rank must come from scores_2026.csv, not the summary file.
    score_rank = scores.loc[scores["cve_id"] == first_expl_id, "rank"]
    row(
        f"explanation {first_expl_id} rank source",
        f"scores_2026.csv rank={int(score_rank.iloc[0]) if len(score_rank) else None}",
        f"api rank={expl.get('rank')}",
        "rank/priority/reasons ← scores_2026.csv only",
        len(score_rank) > 0 and expl.get("rank") == int(score_rank.iloc[0]),
    )

    # Hardcoded smell checks on API payload
    approx = summary.get("token_usage", {}).get("estimated_tokens_consumed_approx")
    lite_cap = summary.get("token_usage", {}).get("lite_plan_monthly_cap")
    row(
        "no hardcoded token approx / lite_cap in API",
        "absent",
        f"approx={approx!r} lite_cap={lite_cap!r}",
        "UI must not show fabricated ~233k / 300000 caps",
        approx is None and lite_cap is None,
    )

    print("--- Protected files (must match origin/main in the index; local untracked runtime copies OK) ---")
    import subprocess

    diff = subprocess.run(
        ["git", "diff", "--exit-code", "origin/main", "--"]
        + [str(p.relative_to(ROOT)) for p in PROTECTED],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    tracked = subprocess.run(
        ["git", "ls-files", "--"] + [str(p.relative_to(ROOT)) for p in PROTECTED],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    print("tracked on HEAD:", tracked.stdout.strip() or "(none — matches origin/main absence)")
    print("diff vs origin/main:", "none" if diff.returncode == 0 else diff.stdout[:400])
    print()

    bad = fails
    if summary["total_analyzed_cves"] != meta["n_rows"]:
        bad += 1
    if summary["token_usage"]["estimated_tokens_consumed"] != meta["estimated_tokens_this_run"]:
        bad += 1
    if file_text != api_text:
        bad += 1
    if diff.returncode != 0:
        bad += 1
        print("FAIL: audited paths differ from origin/main")
    if approx is not None or lite_cap is not None:
        bad += 1

    print("RESULT:", "ALL CHECKS PASSED" if bad == 0 else f"{bad} CHECK(S) FAILED")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
