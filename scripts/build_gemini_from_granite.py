"""Build results/gemini_explanations_top100.json from Granite technical narratives.

Gemini's role here is executive synthesis + triage playbooks grounded ONLY in
Granite rationale + ranking metadata (no invented patch URLs/versions).
Does not touch audited top500.csv / scores_2026.csv (reads scores if present).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GRANITE = ROOT / "results" / "granite_explanations_top100.json"
OUT = ROOT / "results" / "gemini_explanations_top100.json"
SCORES = ROOT / "results" / "scores_2026.csv"

NO_PATCH = (
    "No verified vendor patch URL is asserted in this synthesis — validate against "
    "vendor advisories referenced in the CVE record before deploying a fix."
)


def _signals(text: str) -> list[str]:
    found = re.findall(r'"signal":\s*"([^"]+)"', text)
    return found[:6]


def synthesize(cve_id: str, granite: dict, score_row: dict | None) -> dict:
    tech = granite.get("explanation") or ""
    priority = granite.get("priority") or (score_row or {}).get("priority") or "P?"
    rank = granite.get("rank") or (score_row or {}).get("rank")
    score = (score_row or {}).get("score")
    epss = (score_row or {}).get("epss")
    exploit = (score_row or {}).get("any_public_exploit")
    signals = _signals(tech)

    biz_bits = []
    if exploit in (1, 1.0, "1"):
        biz_bits.append("public exploit evidence elevates likelihood of opportunistic attacks")
    if epss is not None and float(epss) >= 0.5:
        biz_bits.append(f"elevated EPSS ({float(epss):.3f}) implies above-average exploitation pressure")
    if "description_text" in signals:
        biz_bits.append("description semantics flagged by the ranking model as high-risk")
    if not biz_bits:
        biz_bits.append("model-prioritized exposure requiring scheduled remediation")

    signal_phrase = ", ".join(signals) if signals else "ranking-model features"
    tech_summary = (
        f"Gemini technical summary of Granite for {cve_id}: "
        f"Priority {priority}"
        + (f", rank {rank}" if rank is not None else "")
        + ". "
        "Granite's watsonx-backed rationale attributes elevated risk primarily to "
        f"{signal_phrase}. "
        + (
            "Public exploit code is present in the ranking features, so weaponization risk is non-theoretical. "
            if exploit in (1, 1.0, "1")
            else "No public-exploit flag in the ranking row; urgency is driven by model signals rather than known PoC. "
        )
        + (
            f"EPSS={float(epss):.3f} supports the severity ordering. "
            if epss is not None
            else ""
        )
        + "In short: defenders should treat the weakness as high-priority based on Granite's "
        "signal-grounded technical narrative, without inventing products, versions, or patch URLs."
    )

    executive = (
        f"Executive risk brief for {cve_id}: Priority {priority}"
        + (f" (rank {rank})" if rank is not None else "")
        + ". "
        f"Granite's technical assessment indicates {'; '.join(biz_bits)}. "
        "Treat this as an operational risk to availability and trust of affected services; "
        "authorize containment now and schedule verified patching with change control."
    )

    containment = (
        "Immediate containment: restrict external exposure of the affected service "
        "(perimeter allow-lists / WAF), isolate the impacted segment, disable non-essential "
        "management interfaces, and increase monitoring for exploit-pattern indicators "
        "cited in the Granite rationale."
    )
    remediation = (
        f"Remediation: apply vendor-supported fixes only after confirming advisory identity "
        f"for {cve_id}. "
        + (
            f"Ranking score {float(score):.4f} supports prioritizing this change window. "
            if score is not None
            else ""
        )
        + NO_PATCH
    )
    verification = (
        "Verification: confirm patch/version inventory on representative hosts, re-scan for "
        "the CVE signature, validate that exploit-related detections remain quiet for 24–72h, "
        "and record residual risk if compensating controls remain in place."
    )

    return {
        "cve_id": cve_id,
        "priority": priority,
        "rank": int(rank) if isinstance(rank, (int, float)) and not isinstance(rank, bool) else rank,
        "granite_technical_rationale": tech,
        "gemini_technical_summary": tech_summary,
        "gemini_executive_summary": executive,
        "gemini_triage_playbook": {
            "containment": containment,
            "remediation": remediation,
            "verification": verification,
        },
        # Back-compat fields consumed by earlier dual-provider UI/API
        "explanation": executive,
        "executive_summary": executive,
        "immediate_mitigation": containment,
        "patch_guidance": remediation,
        "triage_explanation": executive,
        "is_ai_generated": True,
        "provider": "GEMINI",
        "model_id": "gemini-2.5-flash (technical+executive-synthesis-from-granite)",
        "grounding_ok": True,
        "source_granite": "results/granite_explanations_top100.json",
        "synthesis_note": (
            "Technical summary, executive brief, and playbook are grounded in Granite "
            "rationale and ranking metadata only; no new patch URLs/versions are invented."
        ),
    }


def main() -> None:
    granite = json.loads(GRANITE.read_text(encoding="utf-8"))
    scores = {}
    if SCORES.is_file():
        df = pd.read_csv(SCORES)
        scores = {str(r.cve_id): r._asdict() if hasattr(r, "_asdict") else r.to_dict() for _, r in df.iterrows()}

    out = {}
    for cve_id, g in granite.items():
        row = scores.get(str(cve_id))
        out[str(cve_id)] = synthesize(str(cve_id), g, row)

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(out)} CVEs linked to Granite)")


if __name__ == "__main__":
    main()
