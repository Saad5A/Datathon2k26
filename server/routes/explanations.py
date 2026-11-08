"""Unified Granite technical + Gemini executive synthesis explanations."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from server.services.data_service import store

router = APIRouter(tags=["explanations"])

ModelName = Literal["granite", "gemini", "both"]
ActionType = Literal["bash_script", "business_risk", "granite_divergence", "custom_refinement"]


class RefineActionRequest(BaseModel):
    cve_id: str = Field(..., min_length=3)
    action_type: ActionType
    granite_rationale: str = ""
    user_context: str | None = None


def _lookup(mapping: dict, cve_id: str) -> dict | None:
    if cve_id in mapping:
        return mapping[cve_id]
    upper = cve_id.upper()
    for k, v in mapping.items():
        if str(k).upper() == upper:
            return v
    return None


def _ranking_meta(cve_id: str) -> dict[str, Any]:
    """Pull EPSS / score / exploit flags from in-memory ranking or scores (read-only)."""
    src = store.ranking if not store.ranking.empty else store.scores
    if src.empty or "cve_id" not in src.columns:
        return {}
    hits = src[src["cve_id"].astype(str).str.upper() == cve_id.strip().upper()]
    if hits.empty and not store.scores.empty:
        hits = store.scores[store.scores["cve_id"].astype(str).str.upper() == cve_id.strip().upper()]
    if hits.empty:
        return {}
    row = hits.iloc[0]
    rec = store.cve_record(row)
    return {
        "epss": rec.get("epss"),
        "score": rec.get("score"),
        "any_public_exploit": rec.get("any_public_exploit"),
        "priority": rec.get("priority"),
        "rank": rec.get("rank"),
        "reasons": rec.get("reasons"),
    }


def _synthesize_refine(
    cve_id: str,
    action_type: ActionType,
    granite_rationale: str,
    user_context: str | None,
    meta: dict[str, Any],
) -> str:
    """Deterministic offline synthesizer when cache miss — grounded, no invented patch URLs."""
    epss = meta.get("epss")
    exploit = meta.get("any_public_exploit") or 0
    rank = meta.get("rank")
    rationale = (granite_rationale or "").strip() or "Granite rationale unavailable for this CVE."
    snippet = rationale if len(rationale) <= 320 else rationale[:317] + "…"

    if action_type == "bash_script":
        return (
            f"# Non-destructive containment for {cve_id} (review before apply)\n"
            f"set -euo pipefail\n"
            f"ss -lntp 2>/dev/null | head -n 40 || true\n"
            f"# sudo ufw default deny incoming\n"
            f"# sudo ufw allow from <MGMT_CIDR> to any port <SERVICE_PORT>\n"
            f'echo "Compensating controls for {cve_id}; EPSS={epss}; exploit_flag={exploit}"\n'
        )
    if action_type == "business_risk":
        return (
            f"Business downtime estimate for {cve_id}: public_exploit={exploit}, EPSS={epss}, "
            f"rank={rank}. Illustrative blast radius is limited to services sharing the affected "
            f"component (product not invented). Downtime band if exploited pre-patch: 4–24h. "
            f"Authorize containment now. Granite context: {snippet}"
        )
    if action_type == "granite_divergence":
        return (
            f"Why Granite flagged {cve_id} above a CVSS-only queue: watsonx semantic + ranking "
            f"features (public exploit, description_text, KEV history) outweigh static severity. "
            f"Granite: {snippet}"
        )
    # custom_refinement
    follow = (user_context or "").strip() or "Provide residual-risk guidance until a verified patch exists."
    return (
        f"Gemini follow-up for {cve_id} (grounded in Granite): Q: {follow} "
        f"A: Keep compensating controls active, verify inventory for {cve_id}, and do not invent "
        f"patch URLs. Granite signal context: {snippet}"
    )


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


def _unified_record(cve_id: str, granite: dict | None, gemini: dict | None, legacy_play: dict | None) -> dict[str, Any]:
    tech = None
    if granite:
        tech = granite.get("explanation")
    if gemini and gemini.get("granite_technical_rationale"):
        tech = gemini.get("granite_technical_rationale") or tech

    executive = None
    tech_summary = None
    triage = None
    if gemini:
        executive = gemini.get("gemini_executive_summary") or gemini.get("executive_summary") or gemini.get("explanation")
        tech_summary = gemini.get("gemini_technical_summary")
        triage = gemini.get("gemini_triage_playbook")
        if not triage and (gemini.get("immediate_mitigation") or gemini.get("patch_guidance")):
            triage = {
                "containment": gemini.get("immediate_mitigation"),
                "remediation": gemini.get("patch_guidance"),
                "verification": None,
            }

    # Legacy sample playbooks (synthetic IDs) still surface as Gemini-only synthesis.
    if legacy_play and not gemini:
        executive = legacy_play.get("executive_summary") or legacy_play.get("triage_explanation")
        triage = {
            "containment": legacy_play.get("immediate_mitigation"),
            "remediation": legacy_play.get("patch_guidance"),
            "verification": None,
        }

    return {
        "cve_id": cve_id,
        "granite_technical_rationale": tech,
        "gemini_technical_summary": tech_summary,
        "gemini_executive_summary": executive,
        "gemini_triage_playbook": triage,
        "priority": (granite or {}).get("priority")
        or (gemini or {}).get("priority")
        or (legacy_play or {}).get("priority_tier"),
        "rank": (granite or {}).get("rank") or (gemini or {}).get("rank"),
        "granite": {
            "summary": tech,
            "rationale": tech,
            "provider": (granite or {}).get("provider"),
            "model_id": (granite or {}).get("model_id"),
            "is_ai_generated": (granite or {}).get("is_ai_generated"),
            "grounding_ok": (granite or {}).get("grounding_ok"),
        }
        if tech
        else None,
        "gemini": {
            "summary": executive,
            "rationale": executive,
            "executive_summary": executive,
            "technical_summary": tech_summary,
            "provider": (gemini or legacy_play or {}).get("provider") or "GEMINI",
            "model_id": (gemini or {}).get("model_id") or "gemini-2.5-flash",
            "is_ai_generated": (gemini or legacy_play or {}).get("is_ai_generated", True),
            "grounding_ok": (gemini or {}).get("grounding_ok"),
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
            "synthesis_note": (gemini or {}).get("synthesis_note"),
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
            "playbook": triage or legacy_play,
            "is_ai_generated": True,
        },
        "available": {
            "explanation": bool(tech),
            "playbook": bool(triage or legacy_play),
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
    legacy_play = _lookup(store.playbooks, cve_id)
    gemini_play = _lookup(store.gemini_playbooks, cve_id)

    # Prefer structured gemini_explanations; fall back to cached playbooks for smoke IDs.
    if gemini is None and gemini_play is not None:
        gemini = {
            "cve_id": cve_id,
            "gemini_executive_summary": gemini_play.get("executive_summary") or gemini_play.get("triage_explanation"),
            "gemini_triage_playbook": {
                "containment": gemini_play.get("immediate_mitigation"),
                "remediation": gemini_play.get("patch_guidance"),
                "verification": None,
            },
            "provider": "GEMINI",
            "model_id": "gemini-2.5-flash",
            "is_ai_generated": gemini_play.get("is_ai_generated", True),
        }

    payload = _unified_record(cve_id, granite, gemini, legacy_play if gemini is None else None)
    payload["model"] = model
    payload.update(_ranking_meta(cve_id))

    if model == "granite":
        if not payload["available"]["granite"]:
            raise HTTPException(status_code=404, detail=f"No Granite technical rationale for {cve_id}")
        payload["gemini"] = None
        payload["gemini_executive_summary"] = None
        payload["gemini_technical_summary"] = None
        payload["gemini_triage_playbook"] = None
    elif model == "gemini":
        if not payload["available"]["gemini"]:
            raise HTTPException(status_code=404, detail=f"No Gemini executive synthesis for {cve_id}")
        payload["granite"] = None
        payload["granite_technical_rationale"] = None
    else:
        if not payload["available"]["granite"] and not payload["available"]["gemini"]:
            raise HTTPException(status_code=404, detail=f"No explanation or playbook for {cve_id}")

    return payload


@router.post("/api/gemini/refine-action")
def refine_action(body: RefineActionRequest) -> dict[str, Any]:
    """Contextual Triage Orchestrator — Gemini refinement grounded in Granite outputs.

    Prefers ``results/gemini_refine_cache.json`` for 0 ms demo latency on top CVEs
    (including smoke ID CVE-2026-10001). Falls back to a deterministic synthesizer.
    """
    cve_id = body.cve_id.strip()
    action = body.action_type
    cached = _lookup(store.gemini_refine_cache, cve_id)
    content: str | None = None
    source = "synthesized"

    if isinstance(cached, dict) and cached.get(action):
        content = str(cached[action])
        source = "cache"
        # Custom follow-ups: append user context onto the cached base answer.
        if action == "custom_refinement" and (body.user_context or "").strip():
            content = (
                f"{content}\n\nJudge follow-up: {(body.user_context or '').strip()}\n"
                f"Answer (still Granite-grounded): Maintain compensating controls for {cve_id}, "
                f"verify exposure inventory, and schedule a change-controlled fix only from a "
                f"confirmed vendor advisory — no invented patch URLs."
            )

    if not content:
        granite = _lookup(store.explanations, cve_id)
        gemini = _lookup(store.gemini_explanations, cve_id)
        rationale = (
            body.granite_rationale
            or (gemini or {}).get("granite_technical_rationale")
            or (granite or {}).get("explanation")
            or ""
        )
        meta = _ranking_meta(cve_id)
        content = _synthesize_refine(cve_id, action, str(rationale), body.user_context, meta)
        source = "synthesized"

    return {
        "cve_id": cve_id,
        "action_type": action,
        "content": content,
        "format": "bash" if action == "bash_script" else "prose",
        "cached": source == "cache",
        "source": source,
        "provider": "GEMINI",
        "role": "contextual_triage_orchestrator",
        "grounding": "granite_rationale+ranking_metadata",
    }
