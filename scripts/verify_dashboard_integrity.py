"""Side-by-side proof: committed files vs FastAPI vs UI binding map.

Run with the API up:
  python scripts/verify_dashboard_integrity.py

Does not modify any files.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
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
    explanations = json.loads((ROOT / "results" / "granite_explanations_top100.json").read_text(encoding="utf-8"))
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
        "KpiTile 'CVEs analyzed' ← summary.total_analyzed_cves",
        summary["total_analyzed_cves"] == meta["n_rows"],
    )
    row(
        "estimated_tokens_consumed",
        meta["estimated_tokens_this_run"],
        summary["token_usage"]["estimated_tokens_consumed"],
        "KpiTile 'Watsonx tokens used' ← summary.token_usage.estimated_tokens_consumed (exact int)",
        summary["token_usage"]["estimated_tokens_consumed"] == meta["estimated_tokens_this_run"],
    )
    mean = comparison["selection_hint"]["mean_delta_auc_granite_minus_tfidf"]
    row(
        "mean_delta_auc_granite_minus_tfidf",
        mean,
        summary["comparison"]["mean_delta_auc_granite_minus_tfidf"],
        "KpiTile 'Granite ΔAUC vs TF-IDF' ← summary.comparison.mean_delta_auc…",
        abs(float(summary["comparison"]["mean_delta_auc_granite_minus_tfidf"]) - float(mean)) < 1e-12,
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

    file_text = explanations[first_expl_id].get("explanation")
    api_text = (expl.get("granite") or {}).get("summary")
    row(
        f"explanation {first_expl_id}",
        (file_text or "")[:120] + ("…" if file_text and len(file_text) > 120 else ""),
        (api_text or "")[:120] + ("…" if api_text and len(api_text) > 120 else ""),
        "ExplanationModal granite.summary ← results/granite_explanations_top100.json",
        file_text == api_text,
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

    print("--- Protected files (must be unmodified in git) ---")
    import subprocess

    proc = subprocess.run(
        ["git", "status", "--short", "--"] + [str(p.relative_to(ROOT)) for p in PROTECTED],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    dirty = proc.stdout.strip()
    print("git status protected:", dirty or "(clean)")
    print()

    bad = fails
    if summary["total_analyzed_cves"] != meta["n_rows"]:
        bad += 1
    if summary["token_usage"]["estimated_tokens_consumed"] != meta["estimated_tokens_this_run"]:
        bad += 1
    if file_text != api_text:
        bad += 1
    if dirty:
        bad += 1
        print("FAIL: protected files have local modifications")
    if approx is not None or lite_cap is not None:
        bad += 1

    print("RESULT:", "ALL CHECKS PASSED" if bad == 0 else f"{bad} CHECK(S) FAILED")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
