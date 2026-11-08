"""Read-only normalization of the audited result artifacts for the /results page.

The numbers on the proof page are never typed into the UI. They are read from
the same JSON files the claim ledger points at, together with the ledger status
of each metric, so the page and the audit trail cannot drift apart.

Never writes to results/.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"

MODEL_ORDER = ("cvss3", "epss", "exploit_then_epss", "C1", "G2")
MODEL_LABELS = {
    "cvss3": "CVSS v3 score",
    "epss": "EPSS",
    "exploit_then_epss": "Exploit code, then EPSS",
    "C1": "C1 · gradient boosting",
    "G2": "G2 · submitted",
}
MODEL_SHORT = {
    "cvss3": "CVSS3",
    "epss": "EPSS",
    "exploit_then_epss": "Exploit → EPSS",
    "C1": "C1",
    "G2": "G2",
}

ABLATION_ORDER = ("drop_signals", "drop_text", "drop_assigner", "unmasked_text")
ABLATION_LABELS = {
    "drop_signals": "Without exploit signals",
    "drop_text": "Without description text",
    "drop_assigner": "Without assigner history",
    "unmasked_text": "Unmasked description text",
}
ABLATION_NOTES = {
    "drop_signals": "EPSS, Exploit-DB, Metasploit, Nuclei and GitHub PoC removed.",
    "drop_text": "Masked TF-IDF description text removed.",
    "drop_assigner": "Assigner KEV rate and assigner volume removed.",
    "unmasked_text": "Exploitation wording left in the description (leakage check, not a candidate).",
}

METRICS = ("top500", "top250", "auc", "avg_precision", "median_rank")
METRIC_LABELS = {
    "top500": "Top-500 hits",
    "top250": "Top-250 hits",
    "auc": "ROC AUC",
    "avg_precision": "Average precision",
    "median_rank": "Median rank of exploited",
}
METRIC_CLAIM_KEYS = {
    "top500": "top500_cve_id",
    "top250": "top250_cve_id",
    "auc": "auc",
    "avg_precision": "avg_precision",
    "median_rank": "median_rank_cve_id",
}

SOURCE_FILES = {
    "backtest_summary": RESULTS / "backtest_summary.json",
    "granite_comparison": RESULTS / "granite_comparison.json",
    "model_candidates": RESULTS / "model_candidates.json",
    "drift_summary": RESULTS / "drift_summary.json",
}
CLAIM_FILES = (
    RESULTS / "claims_model.json",
    RESULTS / "claims_model_granite.json",
)


def _load(name: str) -> dict[str, Any]:
    path = SOURCE_FILES[name]
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def _claim_status(stamp: str) -> dict[str, str]:
    """claim id -> ledger status, cached on the corpus mtime signature."""
    del stamp  # cache key only
    out: dict[str, str] = {}
    for path in CLAIM_FILES:
        if not path.exists():
            continue
        try:
            for key, value in json.loads(path.read_text(encoding="utf-8")).items():
                out[key] = str(value.get("status", "unverified"))
        except (OSError, ValueError):
            continue
    return out


def _claim_index() -> tuple[dict[str, str], str]:
    stamp = "|".join(f"{p.name}:{p.stat().st_mtime_ns}" for p in CLAIM_FILES if p.exists())
    return _claim_status(stamp), stamp


def _pick(block: dict[str, Any], key: str) -> float | None:
    """Read a metric from either artifact shape (top500 or top500_cve_id)."""
    for candidate in (key, METRIC_CLAIM_KEYS.get(key, key)):
        value = block.get(candidate)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _metrics(block: dict[str, Any], claim_prefix: str, claims: dict[str, str]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key in METRICS:
        value = _pick(block, key)
        claim_id = f"{claim_prefix}.{METRIC_CLAIM_KEYS[key]}.median"
        values[key] = {
            "value": value,
            "claim": claim_id,
            "verified": claims.get(claim_id) == "verified",
        }
    return values


def _fold_models(
    fold_key: str,
    granite_fold: dict[str, Any],
    backtest_fold: dict[str, Any],
    claims: dict[str, str],
) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    granite_models = granite_fold.get("models", {})
    for key in MODEL_ORDER:
        if key == "C1":
            # Phase 3's C1 is the same refit the Granite comparison asserts.
            block = backtest_fold.get("ours") or {}
            metrics = _metrics(block, f"p3.{fold_key}.C1", claims)
        elif key == "G2":
            block = (granite_models.get(key) or {}).get("median") or {}
            metrics = _metrics(block, f"p6.granite.{fold_key}.{key}", claims)
        else:
            block = backtest_fold.get(key) or {}
            metrics = _metrics(block, f"p3.{fold_key}.{key}", claims)
        models.append(
            {
                "key": key,
                "label": MODEL_LABELS[key],
                "short": MODEL_SHORT[key],
                "submitted": key == "G2",
                "metrics": metrics,
            }
        )
    return models


def build_results() -> dict[str, Any]:
    backtest = _load("backtest_summary")
    granite = _load("granite_comparison")
    candidates = _load("model_candidates")
    drift = _load("drift_summary")
    claims, _stamp = _claim_index()

    folds: list[dict[str, Any]] = []
    for index, fold_key in enumerate(("fold1", "fold2"), start=1):
        granite_fold = (granite.get("folds") or {}).get(fold_key) or {}
        backtest_fold = backtest.get(fold_key) or {}
        folds.append(
            {
                "key": fold_key,
                "label": f"Fold {index}",
                "test_months": granite_fold.get("test_months"),
                "test_rows": granite_fold.get("test_rows"),
                "positives": granite_fold.get("test_positives"),
                "models": _fold_models(fold_key, granite_fold, backtest_fold, claims),
            }
        )

    ablations: list[dict[str, Any]] = []
    for key in ABLATION_ORDER:
        rows: list[dict[str, Any]] = []
        for fold_key in ("fold1", "fold2"):
            block = ((candidates.get("ablations") or {}).get(fold_key) or {}).get(key) or {}
            median = block.get("median") or {}
            rows.append(
                {
                    "key": fold_key,
                    "auc": _pick(median, "auc"),
                    "top500": _pick(median, "top500_cve_id"),
                    "top250": _pick(median, "top250_cve_id"),
                    "avg_precision": _pick(median, "avg_precision"),
                    "median_rank": _pick(median, "median_rank_cve_id"),
                    "verified": claims.get(f"p3.{fold_key}.{key}.auc.median") == "verified",
                }
            )
        ablations.append(
            {
                "key": key,
                "label": ABLATION_LABELS[key],
                "note": ABLATION_NOTES[key],
                "folds": rows,
            }
        )

    selection = granite.get("selection") or {}
    paired = ((candidates.get("paired_bootstrap_vs_exploit_then_epss") or {}).get("fold1") or {}).get(
        "seed_median"
    ) or {}
    permutation = (candidates.get("permutation") or {}).get("fold1") or {}
    unseen = ((candidates.get("unseen_assigner") or {}).get("fold1") or {}).get("seed_median") or {}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "submitted": {
            "model": selection.get("adopted") or "G2",
            "base": "C1",
            "best_granite": selection.get("best_granite"),
            "rule": selection.get("rule"),
            "flag": selection.get("final_py_flag"),
            "mean_auc": selection.get("mean_auc_over_folds") or {},
        },
        "folds": folds,
        "ablations": ablations,
        "significance": {
            "paired_bootstrap_vs_exploit_then_epss": {
                "fold": "fold1",
                **paired,
            },
            "permutation": {
                "fold": "fold1",
                "mean": permutation.get("mean"),
                "sd": permutation.get("sd"),
                "max": permutation.get("max"),
                "n_shuffles": permutation.get("n_shuffles"),
            },
        },
        "unseen_assigner": {
            "fold": "fold1",
            "definition": unseen.get("definition"),
            "rows": unseen.get("rows"),
            "positives": unseen.get("positives"),
            "auc": unseen.get("auc_within_subset"),
            "top500_rows_from_subset": unseen.get("top500_rows_from_subset"),
            "top500_hits_from_subset": unseen.get("top500_hits_from_subset"),
        },
        "drift": {
            "rows_2025_pool": (drift.get("rows") or {}).get("2025_pool"),
            "rows_2026_scoreboard": (drift.get("rows") or {}).get("2026_scoreboard"),
            "assigners_2025": ((drift.get("assigner_mix") or {}).get("distinct_assigners") or {}).get(
                "2025_pool"
            ),
            "assigners_2026": ((drift.get("assigner_mix") or {}).get("distinct_assigners") or {}).get(
                "2026_scoreboard"
            ),
        },
        "sources": [
            {"path": "results/backtest_summary.json", "role": "baselines and C1, per fold"},
            {"path": "results/granite_comparison.json", "role": "C1 vs G1 vs G2 and the selection rule"},
            {"path": "results/model_candidates.json", "role": "ablations, bootstrap, permutation, unseen assigners"},
            {"path": "results/drift_summary.json", "role": "2025 pool vs 2026 scoreboard composition"},
            {"path": "results/claims_model.json", "role": "verified claim ids for every metric"},
            {"path": "results/claims_model_granite.json", "role": "verified claim ids for G2 metrics"},
            {"path": "audit/2026-11-07-phase3.md", "role": "independent Phase 3 audit"},
            {"path": "audit/2026-11-08-granite-final.md", "role": "independent Granite audit"},
        ],
        "metric_labels": METRIC_LABELS,
    }


def write_snapshot(path: Path | None = None) -> Path:
    """Write the exact payload the page bundles when the API is unavailable."""
    target = path or (ROOT / "dashboard" / "src" / "data" / "results_snapshot.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_results(), indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    print(write_snapshot())
