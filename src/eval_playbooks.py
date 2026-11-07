"""Automated validation suite for Gemini triage playbooks.

Evaluates results/cached_playbooks.json against results/top500_enriched.csv
and writes results/agent_eval_report.json for judges / submission evidence.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.remediation_agent import (  # noqa: E402
    CACHED_PLAYBOOKS_PATH,
    NO_PATCH_MSG,
    PRODUCTISH,
    URL_PATTERN,
    _parse_reference_urls,
)

ENRICHED_PATH = ROOT / "results" / "top500_enriched.csv"
REPORT_PATH = ROOT / "results" / "agent_eval_report.json"

REQUIRED_FIELDS = (
    "executive_summary",
    "immediate_mitigation",
    "triage_explanation",
    "patch_guidance",
    "priority_tier",
    "cve_id",
    "is_ai_generated",
)

FALLBACK_WARNING_NEEDLE = "no verified vendor patch url identified"


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    text = str(value).strip()
    return bool(text) and text.lower() not in {"nan", "none", "null"}


def load_inputs(
    cache_path: Path = CACHED_PLAYBOOKS_PATH,
    enriched_path: Path = ENRICHED_PATH,
) -> tuple[dict[str, dict[str, Any]], pd.DataFrame]:
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Missing playbook cache: {cache_path}\n"
            "Run: python -m src.generate_playbooks"
        )
    if not enriched_path.exists():
        raise FileNotFoundError(
            f"Missing enriched table: {enriched_path}\n"
            "Run: python -m src.enrich_top500"
        )

    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    if not isinstance(cache, dict) or not cache:
        raise ValueError(f"Playbook cache is empty or invalid: {cache_path}")

    enriched = pd.read_csv(enriched_path)
    if "cve_id" not in enriched.columns:
        raise ValueError("Enriched CSV missing required column: cve_id")
    return cache, enriched


def _grounded_corpus(row: pd.Series) -> str:
    parts = [
        row.get("vendor"),
        row.get("affected_products"),
        row.get("assigner"),
        row.get("description"),
        row.get("weakness"),
        row.get("cwe_name"),
        row.get("cve_id"),
        row.get("reference_urls"),
    ]
    return " ".join(_nonempty(p) and str(p) or "" for p in parts).lower()


def _allowed_vendor_tokens(row: pd.Series) -> set[str]:
    tokens: set[str] = set()
    for col in ("vendor", "affected_products", "assigner"):
        raw = row.get(col)
        if not _nonempty(raw):
            continue
        text = str(raw)
        tokens.add(text.lower())
        for piece in re.split(r"[;|,/]", text):
            piece = piece.strip().lower()
            if piece:
                tokens.add(piece)
                tokens.update(piece.split())
    return {t for t in tokens if len(t) >= 2}


def check_schema(playbook: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in playbook or not _nonempty(playbook.get(field)):
            # is_ai_generated can be bool False/True — handle separately
            if field == "is_ai_generated":
                continue
            failures.append(f"missing_or_null:{field}")
    if playbook.get("is_ai_generated") is not True:
        failures.append("is_ai_generated_not_true")
    return len(failures) == 0, failures


def check_priority(playbook: dict[str, Any], row: pd.Series) -> tuple[bool, list[str]]:
    expected = str(row.get("priority", "")).strip().upper()
    actual = str(playbook.get("priority_tier", "")).strip().upper()
    if expected not in {"P0", "P1", "P2"}:
        return False, [f"input_priority_invalid:{expected}"]
    if actual != expected:
        return False, [f"priority_mismatch:expected={expected}:got={actual}"]
    return True, []


def check_patch_urls(playbook: dict[str, Any], row: pd.Series) -> tuple[bool, list[str]]:
    """Return (pass, failures). Pass means no hallucinated URLs / correct empty-ref fallback."""
    failures: list[str] = []
    allowed = set(_parse_reference_urls(row.get("reference_urls")))
    guidance = str(playbook.get("patch_guidance", "") or "")
    cited = [u.rstrip(").,];") for u in URL_PATTERN.findall(guidance)]

    if not allowed:
        if FALLBACK_WARNING_NEEDLE not in guidance.lower():
            failures.append("missing_empty_ref_fallback_warning")
        if cited:
            failures.append(f"unexpected_urls_with_empty_refs:{cited}")
        return len(failures) == 0, failures

    for url in cited:
        if url not in allowed:
            failures.append(f"hallucinated_url:{url}")
    return len(failures) == 0, failures


def check_vendor_grounding(playbook: dict[str, Any], row: pd.Series) -> tuple[bool, list[str]]:
    """Every vendor/product Proper Name in the playbook must appear in input metadata."""
    failures: list[str] = []
    grounded = _grounded_corpus(row)
    allowed_tokens = _allowed_vendor_tokens(row)

    combined = " ".join(
        str(playbook.get(k, "") or "")
        for k in (
            "executive_summary",
            "triage_explanation",
            "immediate_mitigation",
            "patch_guidance",
        )
    )

    # Soft allowlist for SOC language / weakness labels that are not vendors.
    allowlist = {
        "Priority Score",
        "Code Injection",
        "Untrusted Data",
        "Improper Authentication",
        "Improper Access",
        "Improper Access Control",
        "Improper Control",
        "Cross Site",
        "Cross-site Scripting",
        "Web Page",
        "Generation Of",
        "Remote Code",
        "Known Exploited",
        "Interim Mitigations",
        "Advisory References",
        "Vendor Patch",
        "Verified References",
        "Message Broker",
        "Identity Proxy",
        "Stopgap Mitigation",
    }
    allowlist_l = {a.lower() for a in allowlist}

    for match in PRODUCTISH.finditer(combined):
        name = match.group(1).strip()
        name_l = name.lower()
        if name.upper().startswith("CVE-") or name_l in allowlist_l:
            continue
        if name_l in grounded:
            continue
        # Token overlap with vendor/product metadata
        name_tokens = set(re.findall(r"[a-z0-9]+", name_l))
        if name_tokens and name_tokens.issubset(allowed_tokens):
            continue
        if any(tok and tok in grounded for tok in name_tokens if len(tok) > 3):
            # partial grounded mention (e.g. vendor token inside longer phrase)
            if any(tok in allowed_tokens for tok in name_tokens):
                continue
        failures.append(f"ungrounded_vendor_or_product:{name}")

    # If input has an explicit vendor, require at least one grounded vendor/product token
    # appears somewhere in the executive summary when vendor is not Unknown.
    vendor = str(row.get("vendor", "") or "").strip()
    if vendor and vendor.lower() not in {"unknown", "unassigned", "pending review"}:
        summary = str(playbook.get("executive_summary", "") or "").lower()
        vendor_l = vendor.lower()
        products = str(row.get("affected_products", "") or "").lower()
        if vendor_l not in summary and vendor_l not in grounded:
            failures.append(f"input_vendor_absent_from_grounding_context:{vendor}")
        elif vendor_l not in summary and not any(
            p.strip() and p.strip() in summary for p in re.split(r"[;|,]", products) if p.strip()
        ):
            # Prefer seeing vendor/product referenced in the impact summary.
            # Do not hard-fail if description-grounded generic wording is used;
            # only fail when neither vendor nor product token appears in summary.
            tokens = _allowed_vendor_tokens(row)
            if not any(tok in summary for tok in tokens if len(tok) > 3):
                failures.append(f"vendor_not_mentioned_in_summary:{vendor}")

    return len(failures) == 0, failures


def evaluate_playbook(
    cve_id: str,
    playbook: dict[str, Any],
    row: pd.Series,
) -> dict[str, Any]:
    schema_ok, schema_fail = check_schema(playbook)
    priority_ok, priority_fail = check_priority(playbook, row)
    patch_ok, patch_fail = check_patch_urls(playbook, row)
    vendor_ok, vendor_fail = check_vendor_grounding(playbook, row)

    latency = playbook.get("latency_seconds")
    if latency is None:
        latency = playbook.get("_latency_seconds")
    try:
        latency_f = float(latency) if latency is not None else None
    except (TypeError, ValueError):
        latency_f = None

    failures = schema_fail + priority_fail + patch_fail + vendor_fail
    return {
        "cve_id": cve_id,
        "schema_ok": schema_ok,
        "priority_ok": priority_ok,
        "patch_url_ok": patch_ok,
        "vendor_grounding_ok": vendor_ok,
        "passed": all((schema_ok, priority_ok, patch_ok, vendor_ok)),
        "failures": failures,
        "latency_seconds": latency_f,
    }


def evaluate_all(
    cache: dict[str, dict[str, Any]],
    enriched: pd.DataFrame,
) -> dict[str, Any]:
    by_cve = enriched.drop_duplicates("cve_id").set_index("cve_id", drop=False)

    per_cve: list[dict[str, Any]] = []
    missing_rows = 0
    for cve_id, playbook in cache.items():
        if cve_id not in by_cve.index:
            missing_rows += 1
            per_cve.append(
                {
                    "cve_id": cve_id,
                    "schema_ok": False,
                    "priority_ok": False,
                    "patch_url_ok": False,
                    "vendor_grounding_ok": False,
                    "passed": False,
                    "failures": ["missing_enriched_row"],
                    "latency_seconds": None,
                }
            )
            continue
        row = by_cve.loc[cve_id]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        per_cve.append(evaluate_playbook(cve_id, playbook, row))

    n = len(per_cve) or 1
    schema_pass = sum(1 for r in per_cve if r["schema_ok"])
    patch_fail = sum(1 for r in per_cve if not r["patch_url_ok"])
    vendor_pass = sum(1 for r in per_cve if r["vendor_grounding_ok"])
    priority_pass = sum(1 for r in per_cve if r["priority_ok"])
    overall_pass = sum(1 for r in per_cve if r["passed"])

    latencies = [r["latency_seconds"] for r in per_cve if r["latency_seconds"] is not None]
    avg_latency = sum(latencies) / len(latencies) if latencies else None

    summary = {
        "total_playbooks_evaluated": len(per_cve),
        "schema_conformance_rate": round(100.0 * schema_pass / n, 2),
        "patch_url_hallucination_rate": round(100.0 * patch_fail / n, 2),
        "vendor_grounding_pass_rate": round(100.0 * vendor_pass / n, 2),
        "priority_preservation_rate": round(100.0 * priority_pass / n, 2),
        "overall_pass_rate": round(100.0 * overall_pass / n, 2),
        "avg_latency_seconds": None if avg_latency is None else round(avg_latency, 4),
        "missing_enriched_rows": missing_rows,
        "per_cve": per_cve,
    }
    return summary


def save_report(summary: dict[str, Any], path: Path = REPORT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def print_summary_table(summary: dict[str, Any]) -> None:
    rows = [
        ("total_playbooks_evaluated", str(summary["total_playbooks_evaluated"])),
        ("schema_conformance_rate", f"{summary['schema_conformance_rate']:.1f}%"),
        ("patch_url_hallucination_rate", f"{summary['patch_url_hallucination_rate']:.1f}%"),
        ("vendor_grounding_pass_rate", f"{summary['vendor_grounding_pass_rate']:.1f}%"),
        ("priority_preservation_rate", f"{summary['priority_preservation_rate']:.1f}%"),
        ("overall_pass_rate", f"{summary['overall_pass_rate']:.1f}%"),
        (
            "avg_latency_seconds",
            "n/a" if summary["avg_latency_seconds"] is None else str(summary["avg_latency_seconds"]),
        ),
    ]

    metric_w = max(len(k) for k, _ in rows)
    value_w = max(len(v) for _, v in rows)
    bar = f"+-{'-' * metric_w}-+-{'-' * value_w}-+"

    print(bar)
    print(f"| {'metric'.ljust(metric_w)} | {'value'.ljust(value_w)} |")
    print(bar)
    for key, val in rows:
        print(f"| {key.ljust(metric_w)} | {val.ljust(value_w)} |")
    print(bar)

    failed = [r for r in summary.get("per_cve", []) if not r["passed"]]
    if failed:
        print("\nFailed CVE checks:")
        for item in failed:
            print(f"  - {item['cve_id']}: {', '.join(item['failures'])}")
    else:
        print("\nAll playbooks passed grounding, patch-URL, priority, and schema checks.")


def main() -> None:
    cache, enriched = load_inputs()
    summary = evaluate_all(cache, enriched)
    out = save_report(summary)
    print_summary_table(summary)
    print(f"\nWrote {out}")

    # Hard expectation called out in the brief: hallucination rate must be 0.0%
    if summary["patch_url_hallucination_rate"] != 0.0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
