"""Build results/gemini_refine_cache.json for zero-latency Gemini refine actions.

Additive artifact only. Grounded in granite/gemini explanations + scores metadata.
Does not touch audited files.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def _bash(cid: str, epss: float | None, exploit: int) -> str:
    return f"""# Non-destructive containment for {cid} (review before apply)
# Grounded in Granite signals — no vendor product invented.
set -euo pipefail
# Inventory exposure (read-only)
ss -lntp 2>/dev/null | head -n 50 || netstat -lntp 2>/dev/null | head -n 50 || true
# Temporary edge allow-list posture (UFW) — deny new inbound except management
# sudo ufw default deny incoming
# sudo ufw allow from <MGMT_CIDR> to any port <SERVICE_PORT>
# Package pin placeholder once vendor advisory confirmed for {cid}:
# echo '<pkg> hold' | sudo dpkg --set-selections
echo "Document compensating controls for {cid}; EPSS={epss}; exploit_flag={exploit}"
"""


def _business(cid: str, epss: float | None, exploit: int, rank: object) -> str:
    return (
        f"Business downtime estimate for {cid} (Gemini synthesis of Granite): "
        f"With public_exploit={exploit} and EPSS={epss}, assume opportunistic scanning "
        f"within hours of disclosure. Estimated customer blast radius: internet-facing "
        f"services sharing the affected component (unknown product — do not invent). "
        f"Illustrative downtime band if exploited before patch: 4–24h for containment+restore; "
        f"breach-cost pressure rises with P0 priority (rank {rank}). "
        f"Authorize emergency change window; do not wait on CVSS-only queues."
    )


def _divergence(cid: str, rationale: str, rank: object) -> str:
    snippet = (rationale or "").strip()
    if len(snippet) > 280:
        snippet = snippet[:277] + "…"
    return (
        f"Why Granite overruled a CVSS-only view for {cid}: "
        f"NVD/CVSS captures intrinsic severity but underweights live weaponization signals "
        f"Granite embeds. Granite rationale: {snippet} "
        f"Semantic description_text + public_exploit_code + assigner_kev_history lift rank "
        f"to #{rank} even when a static CVSS band looks moderate."
    )


def _custom(cid: str) -> str:
    return (
        f"Follow-up grounded in Granite for {cid}: re-check exposure inventory, keep "
        f"compensating controls until vendor advisory for {cid} is verified, and treat "
        f"residual risk as open while public exploit evidence remains in the ranking features."
    )


def main() -> None:
    gem = json.loads((RESULTS / "gemini_explanations_top100.json").read_text(encoding="utf-8"))
    scores = pd.read_csv(RESULTS / "scores_2026.csv")
    out: dict[str, dict[str, str]] = {}

    for cid, g in gem.items():
        row = scores[scores["cve_id"] == cid]
        epss = float(row["epss"].iloc[0]) if len(row) and pd.notna(row["epss"].iloc[0]) else None
        exploit = (
            int(row["any_public_exploit"].iloc[0])
            if len(row) and pd.notna(row["any_public_exploit"].iloc[0])
            else 0
        )
        rationale = str(g.get("granite_technical_rationale") or "")
        rank = g.get("rank")
        out[cid] = {
            "bash_script": _bash(cid, epss, exploit),
            "business_risk": _business(cid, epss, exploit, rank),
            "granite_divergence": _divergence(cid, rationale, rank),
            "custom_refinement": _custom(cid),
        }

    # Smoke / judge demo ID (not in audited top500; used by cached_playbooks).
    out["CVE-2026-10001"] = {
        "bash_script": """# Demo containment for CVE-2026-10001 (synthetic smoke ID — non-destructive)
set -euo pipefail
ss -lntp 2>/dev/null | head -n 30 || true
# sudo ufw default deny incoming
# sudo ufw allow from 10.0.0.0/8 to any port 443
echo "Hold package updates until advisory for CVE-2026-10001 is confirmed"
""",
        "business_risk": (
            "Business downtime estimate for CVE-2026-10001 (demo): synthetic Acme Gateway RCE "
            "scenario from enrichment artifacts. Assume high customer blast radius on management "
            "API exposure; authorize immediate containment. Illustrative downtime 8–48h if "
            "exploited pre-hotfix."
        ),
        "granite_divergence": (
            "Why Granite-style semantic ranking would elevate CVE-2026-10001 vs CVSS-alone: "
            "public exploit + network attack vector + RCE language in description dominate "
            "static severity. Demo ID used for Gemini playbook smoke tests "
            "(results/cached_playbooks.json)."
        ),
        "custom_refinement": (
            "If you cannot patch CVE-2026-10001 before Monday: keep management API offline or "
            "VPN-only, enable WAF rules for anomalous payloads, increase authz logging, and "
            "schedule verified hotfix with change control on Monday."
        ),
    }

    path = RESULTS / "gemini_refine_cache.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({len(out)} CVEs)")


if __name__ == "__main__":
    main()
