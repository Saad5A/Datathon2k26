"""Granite explanations and remediation playbooks for ranked CVEs."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.services.data_service import store

router = APIRouter(tags=["explanations"])


def _lookup(mapping: dict, cve_id: str) -> dict | None:
    if cve_id in mapping:
        return mapping[cve_id]
    upper = cve_id.upper()
    for k, v in mapping.items():
        if str(k).upper() == upper:
            return v
    return None


@router.get("/api/explanations/{cve_id}")
def get_explanation(cve_id: str) -> dict:
    expl = _lookup(store.explanations, cve_id)
    play = _lookup(store.playbooks, cve_id)

    if expl is None and play is None:
        raise HTTPException(status_code=404, detail=f"No explanation or playbook for {cve_id}")

    remediation = []
    if play:
        for key in ("immediate_mitigation", "patch_guidance", "executive_summary", "triage_explanation"):
            val = play.get(key)
            if val:
                remediation.append({"step": key, "detail": val})

    return {
        "cve_id": (expl or play or {}).get("cve_id", cve_id),
        "priority": (expl or {}).get("priority") or (play or {}).get("priority_tier"),
        "rank": (expl or {}).get("rank"),
        "granite": {
            "summary": (expl or {}).get("explanation"),
            "rationale": (expl or {}).get("explanation"),
            "provider": (expl or {}).get("provider"),
            "model_id": (expl or {}).get("model_id"),
            "is_ai_generated": (expl or {}).get("is_ai_generated"),
            "grounding_ok": (expl or {}).get("grounding_ok"),
        }
        if expl
        else None,
        "remediation": {
            "steps": remediation,
            "playbook": play,
            "is_ai_generated": (play or {}).get("is_ai_generated"),
        },
        "available": {
            "explanation": expl is not None,
            "playbook": play is not None,
        },
    }
