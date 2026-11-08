"""Unified Granite technical + Gemini executive synthesis explanations."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from server.services.data_service import is_live_gemini_record, store

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


def _playbook_steps(gemini: dict | None) -> list[dict[str, str]]:
    if not gemini:
        return []
    triage = gemini.get("gemini_triage_playbook") or {}
    steps: list[dict[str, str]] = []
    mapping = [
        ("containment", triage.get("containment") or gemini.get("immediate_mitigation")),
        ("remediation", triage.get("remediation") or gemini.get("patch_guidance")),
        ("verification", triage.get("verification")),
    ]
    for step, detail in mapping:
        if detail:
            steps.append({"step": step, "detail": str(detail)})
    return steps


def _unified_record(cve_id: str, granite: dict | None, gemini: dict | None) -> dict[str, Any]:
    tech = None
    if granite:
        tech = granite.get("explanation")
    if gemini and gemini.get("granite_technical_rationale"):
        tech = gemini.get("granite_technical_rationale") or tech

    executive = None
    triage = None
    if gemini:
        executive = gemini.get("gemini_executive_summary") or gemini.get("executive_summary") or gemini.get("explanation")
        triage = gemini.get("gemini_triage_playbook")
        if not triage and (gemini.get("immediate_mitigation") or gemini.get("patch_guidance")):
            triage = {
                "containment": gemini.get("immediate_mitigation"),
                "remediation": gemini.get("patch_guidance"),
                "verification": None,
            }

    return {
        "cve_id": cve_id,
        "granite_technical_rationale": tech,
        "gemini_executive_summary": executive,
        "gemini_triage_playbook": triage,
        "priority": (granite or {}).get("priority") or (gemini or {}).get("priority"),
        "rank": (granite or {}).get("rank") or (gemini or {}).get("rank"),
        "granite": {
            "summary": tech,
            "rationale": tech,
            "provider": (granite or {}).get("provider"),
            "model_id": (granite or {}).get("model_id"),
            "is_ai_generated": (granite or {}).get("is_ai_generated"),
        }
        if tech
        else None,
        "gemini": {
            "summary": executive,
            "rationale": executive,
            "executive_summary": executive,
            "provider": (gemini or {}).get("provider"),
            "model_id": (gemini or {}).get("model_id"),
            "is_ai_generated": (gemini or {}).get("is_ai_generated"),
            "playbook": triage,
            "remediation_steps": _playbook_steps(gemini)
            or [
                {"step": k, "detail": v}
                for k, v in (
                    ("containment", (triage or {}).get("containment")),
                    ("remediation", (triage or {}).get("remediation")),
                    ("verification", (triage or {}).get("verification")),
                )
                if v
            ],
        }
        if executive or triage
        else None,
        "remediation": {
            "steps": _playbook_steps(gemini)
            or [
                {"step": k, "detail": str(v)}
                for k, v in (
                    ("containment", (triage or {}).get("containment")),
                    ("remediation", (triage or {}).get("remediation")),
                    ("verification", (triage or {}).get("verification")),
                )
                if v
            ],
            "playbook": triage,
            "is_ai_generated": bool(gemini and gemini.get("is_ai_generated") is True),
        },
        "available": {
            "explanation": bool(tech),
            "playbook": bool(triage),
            "granite": bool(tech),
            "gemini": bool(executive or triage),
        },
    }


@router.get("/api/explanations/{cve_id}")
def get_explanation(
    cve_id: str,
    model: ModelName = Query(
        "both",
        description="granite | gemini | both — unified payload always includes linked fields when both= true",
    ),
) -> dict:
    granite = _lookup(store.explanations, cve_id)
    gemini = _lookup(store.gemini_explanations, cve_id)
    if not is_live_gemini_record(gemini):
        gemini = None

    # Only serve explicit Gemini explanation records. Legacy sample/playbook
    # caches lack reliable provider provenance and must not be presented as Gemini.
    payload = _unified_record(cve_id, granite, gemini)
    payload["model"] = model

    if model == "granite":
        if not payload["available"]["granite"]:
            raise HTTPException(status_code=404, detail=f"No Granite technical rationale for {cve_id}")
        payload["gemini"] = None
        payload["gemini_executive_summary"] = None
        payload["gemini_triage_playbook"] = None
        payload["remediation"] = {"steps": [], "playbook": None, "is_ai_generated": False}
    elif model == "gemini":
        if not payload["available"]["gemini"]:
            raise HTTPException(status_code=404, detail=f"No Gemini executive synthesis for {cve_id}")
        payload["granite"] = None
        payload["granite_technical_rationale"] = None
    else:
        if not payload["available"]["granite"] and not payload["available"]["gemini"]:
            raise HTTPException(status_code=404, detail=f"No explanation or playbook for {cve_id}")

    return payload
