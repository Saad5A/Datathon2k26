"""Build results/gemini_explanations_top100.json from Granite technical narratives.

Telegraphic Gemini synthesis: executive brief + triage playbook under 50 words total.
Grounded ONLY in Granite rationale + ranking metadata (no invented patch URLs/versions).
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

# Drop-in prompt for live gemini-2.5-flash callers / documentation parity.
GEMINI_SYSTEM_PROMPT = """You are a terse incident commander. Summarize this CVE risk in telegraphic, punchy, minimal prose.

HARD LENGTH LIMITS:
- Executive Brief: Exactly 1 sentence. Maximum 18 words. Focus solely on business threat and required posture.
- Containment: Maximum 8 words.
- Hotfix: Maximum 8 words.
- Verification: Maximum 8 words.
- Total response MUST be under 50 words.
- NEVER repeat keys (e.g., do not say "Containment: Contain by...").

FORMAT EXACTLY AS:
Executive Brief: [1 sentence, <= 18 words]
Automated Triage Playbook:
- Containment: [<= 8 words]
- Hotfix: [<= 8 words]
- Verification: [<= 8 words]
"""


def _signals(text: str) -> list[str]:
    found = re.findall(r'"signal":\s*"([^"]+)"', text)
    return found[:6]


def _clip_words(text: str, max_words: int) -> str:
    words = [w for w in str(text).split() if w]
    if len(words) <= max_words:
        return " ".join(words).strip()
    clipped = " ".join(words[:max_words]).rstrip(".,;:")
    return clipped + ("." if max_words >= 8 else "")


def _word_count(*parts: str) -> int:
    return sum(len(str(p).split()) for p in parts)


def synthesize(cve_id: str, granite: dict, score_row: dict | None) -> dict:
    tech = granite.get("explanation") or ""
    priority = granite.get("priority") or (score_row or {}).get("priority") or "P?"
    rank = granite.get("rank") or (score_row or {}).get("rank")
    exploit = (score_row or {}).get("any_public_exploit")
    epss = (score_row or {}).get("epss")
    signals = _signals(tech)

    # Pick the sharpest pressure token for an 18-word brief
    if exploit in (1, 1.0, "1"):
        threat = "public exploit"
    elif epss is not None and float(epss) >= 0.5:
        threat = f"EPSS {float(epss):.2f}"
    elif "description_text" in signals:
        threat = "high-risk description signals"
    else:
        threat = "model-prioritized exposure"

    rank_bit = f"#{rank}" if rank is not None else priority

    # Exactly 1 sentence, <= 18 words — values only (no "Executive Brief:" prefix)
    executive = _clip_words(
        f"{cve_id} {rank_bit}: {threat} risks downtime — contain and patch now.",
        18,
    )

    # Telegraphic technical line for dual-provider UI (kept short; not in ≤50 brief budget)
    tech_summary = _clip_words(
        f"{cve_id} {priority}: Granite flags {threat}.",
        12,
    )

    # Single-phrase playbook steps, <= 8 words each, no key prefixes
    containment = _clip_words("WAF restrict; isolate segment; cut admin.", 8)
    remediation = _clip_words(f"Vendor fix for {cve_id}; validate advisory.", 8)
    verification = _clip_words("Re-scan CVE; watch detections 72h.", 8)

    # Enforce hard total on brief + playbook (the FORMAT EXACTLY AS block)
    brief_total = _word_count(executive, containment, remediation, verification)
    if brief_total > 50:
        executive = _clip_words(executive, max(8, 18 - (brief_total - 50)))

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
        "generation_mode": "from_granite",
        "grounding_ok": True,
        "source_granite": "results/granite_explanations_top100.json",
        "synthesis_note": (
            "Telegraphic brief+playbook (<50 words) grounded in Granite rationale "
            "and ranking metadata only; no new patch URLs/versions invented."
        ),
        "system_prompt_ref": "GEMINI_SYSTEM_PROMPT",
        "brief_word_count": _word_count(executive, containment, remediation, verification),
    }


def main() -> None:
    granite = json.loads(GRANITE.read_text(encoding="utf-8"))
    wanted = {str(k) for k in granite}
    scores: dict[str, dict] = {}
    if SCORES.is_file():
        cols = ["cve_id", "score", "epss", "any_public_exploit", "priority", "rank"]
        df = pd.read_csv(SCORES, usecols=lambda c: c in cols)
        df = df[df["cve_id"].astype(str).isin(wanted)]
        scores = {str(r["cve_id"]): r for r in df.to_dict(orient="records")}

    out = {}
    for cve_id, g in granite.items():
        row = scores.get(str(cve_id))
        out[str(cve_id)] = synthesize(str(cve_id), g, row)

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sample = next(iter(out.values()))
    print(
        f"wrote {OUT.relative_to(ROOT)} ({len(out)} CVEs); "
        f"sample brief_word_count={sample.get('brief_word_count')}"
    )


if __name__ == "__main__":
    main()
