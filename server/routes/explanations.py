"""Dual-provider explanations: IBM Granite + Gemini (additive)."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from server.services.data_service import store

router = APIRouter(tags=["explanations"])

ModelName = Literal["granite", "gemini", "both"]


def _lookup(mapping: dict, cve_id: str) -> dict | None:
    if cve_id in mapping:
        return mapping[cve_id]
    upper = cve_id.upper()
    for k, v in mapping.items():
        if str(k).upper() == upper:
            return v
    return None


def _remediation_steps(play: dict | None) -> list[dict[str, str]]:
    if not play:
        return []
    steps = []
    for key in ("immediate_mitigation", "patch_guidance", "executive_summary", "triage_explanation"):
        val = play.get(key)
        if val:
            steps.append({"step": key, "detail": str(val)})
    return steps


def _granite_block(expl: dict | None) -> dict[str, Any] | None:
    if not expl:
        return None
    return {
        "summary": expl.get("explanation"),
        "rationale": expl.get("explanation"),
        "provider": expl.get("provider"),
        "model_id": expl.get("model_id"),
        "is_ai_generated": expl.get("is_ai_generated"),
        "grounding_ok": expl.get("grounding_ok"),
    }


def _gemini_block(expl: dict | None, play: dict | None) -> dict[str, Any] | None:
    src = expl or play
    if not src:
        return None
    summary = (
        (expl or {}).get("explanation")
        or (play or {}).get("triage_explanation")
        or (play or {}).get("executive_summary")
    )
    return {
        "summary": summary,
        "rationale": summary,
        "executive_summary": (expl or {}).get("executive_summary") or (play or {}).get("executive_summary"),
        "provider": (expl or {}).get("provider") or "GEMINI",
        "model_id": (expl or {}).get("model_id") or "gemini-2.5-flash",
        "is_ai_generated": (expl or play or {}).get("is_ai_generated"),
        "grounding_ok": (expl or {}).get("grounding_ok"),
        "playbook": play,
        "remediation_steps": _remediation_steps(play or expl),
    }


@router.get("/api/explanations/{cve_id}")
def get_explanation(
    cve_id: str,
    model: ModelName = Query(
        "both",
        description="Provider filter: granite | gemini | both (default both, additive dual payload)",
    ),
) -> dict:
    granite_expl = _lookup(store.explanations, cve_id) if model in ("granite", "both") else None
    granite_play = _lookup(store.playbooks, cve_id) if model in ("granite", "both") else None
    gemini_expl = _lookup(store.gemini_explanations, cve_id) if model in ("gemini", "both") else None
    gemini_play = _lookup(store.gemini_playbooks, cve_id) if model in ("gemini", "both") else None

    # Legacy sample playbooks also surface under Gemini when model asks for gemini/both
    # and no dedicated gemini playbook exists.
    if model in ("gemini", "both") and gemini_play is None:
        gemini_play = _lookup(store.playbooks, cve_id)

    want_granite = model in ("granite", "both")
    want_gemini = model in ("gemini", "both")

    has_granite = granite_expl is not None or (want_granite and granite_play is not None and model == "granite")
    # For granite-only legacy behaviour, playbooks alone were enough for 200.
    if model == "granite":
        if granite_expl is None and granite_play is None:
            raise HTTPException(status_code=404, detail=f"No Granite explanation or playbook for {cve_id}")
    elif model == "gemini":
        if gemini_expl is None and gemini_play is None:
            raise HTTPException(status_code=404, detail=f"No Gemini explanation or playbook for {cve_id}")
    else:
        if granite_expl is None and granite_play is None and gemini_expl is None and gemini_play is None:
            raise HTTPException(status_code=404, detail=f"No explanation or playbook for {cve_id}")

    remediation = _remediation_steps(granite_play)
    if not remediation and gemini_play:
        remediation = _remediation_steps(gemini_play)

    return {
        "cve_id": cve_id,
        "priority": (granite_expl or {}).get("priority")
        or (gemini_expl or {}).get("priority")
        or (granite_play or {}).get("priority_tier")
        or (gemini_play or {}).get("priority_tier"),
        "rank": (granite_expl or {}).get("rank"),
        "model": model,
        "granite": _granite_block(granite_expl) if want_granite else None,
        "gemini": _gemini_block(gemini_expl, gemini_play) if want_gemini else None,
        "remediation": {
            "steps": remediation,
            "playbook": granite_play or gemini_play,
            "is_ai_generated": (granite_play or gemini_play or {}).get("is_ai_generated"),
        },
        "available": {
            "explanation": granite_expl is not None,
            "playbook": granite_play is not None or gemini_play is not None,
            "granite": granite_expl is not None or (model == "granite" and granite_play is not None),
            "gemini": gemini_expl is not None or gemini_play is not None,
        },
    }
