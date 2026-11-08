"""CVE explanations: Granite instruct summaries (AI-generated, unaudited) plus any
provenance-qualified live Gemini brief. Template text is labelled as template."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from server.services.data_service import is_live_gemini_record, store

router = APIRouter(tags=["explanations"])

ModelName = Literal["granite", "gemini", "both"]
ActionType = Literal["bash_script", "business_risk", "granite_divergence", "custom_refinement"]


class RefineActionRequest(BaseModel):
    cve_id: str = Field(..., min_length=3)
    action_type: ActionType
    granite_rationale: str = ""  # accepted for old clients; ignored (server-side data only)
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
    user_context: str | None,
    meta: dict[str, Any],
) -> str:
    """Deterministic template (no model is called). Grounded in ranking metadata; no invented patch URLs."""
    epss = meta.get("epss")
    exploit = meta.get("any_public_exploit") or 0
    rank = meta.get("rank")

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
            f"Authorize containment now."
        )
    if action_type == "granite_divergence":
        return (
            f"Why the ranking model placed {cve_id} above a CVSS-only queue: its cited reasons "
            f"were {', '.join(str(r.get('signal')) for r in (meta.get('reasons') or []) if isinstance(r, dict)) or 'unavailable'} "
            f"(rank={rank}, EPSS={epss}, public_exploit={exploit})."
        )
    # custom_refinement
    follow = (user_context or "").strip() or "Provide residual-risk guidance until a verified patch exists."
    return (
        f"Template answer for {cve_id} (no model was called): Q: {follow} "
        f"A: Keep compensating controls active, verify inventory for {cve_id}, and do not invent "
        f"patch URLs."
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


def _unified_record(cve_id: str, granite: dict | None, gemini: dict | None) -> dict[str, Any]:
    tech = (granite or {}).get("explanation")

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
        "gemini_executive_summary": executive,
        "gemini_triage_playbook": triage,
        # rank / priority / reasons are filled from scores_2026.csv by _ranking_meta().
        "granite": {
            "summary": tech,
            "note": "Written for an earlier version of the ranking; rank and reasons shown come from the current model.",
            "suggested_action": (granite or {}).get("suggested_action"),
            "source": (granite or {}).get("source"),
            "provider": (granite or {}).get("provider"),
            "model_id": (granite or {}).get("model_id"),
            "is_ai_generated": (granite or {}).get("is_ai_generated"),
            "audited": False,
            "label": (granite or {}).get("label"),
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
    payload.update(_ranking_meta(cve_id))

    if model == "granite":
        if not payload["available"]["granite"]:
            raise HTTPException(status_code=404, detail=f"No Granite summary for {cve_id}")
        payload["gemini"] = None
        payload["gemini_executive_summary"] = None
        payload["gemini_triage_playbook"] = None
        payload["remediation"] = {"steps": [], "playbook": None, "is_ai_generated": False}
    elif model == "gemini":
        if not payload["available"]["gemini"]:
            raise HTTPException(status_code=404, detail=f"No Gemini executive brief for {cve_id}")
        payload["granite"] = None
    else:
        if not payload["available"]["granite"] and not payload["available"]["gemini"]:
            raise HTTPException(status_code=404, detail=f"No explanation or playbook for {cve_id}")

    return payload


@router.post("/api/gemini/refine-action")
def refine_action(body: RefineActionRequest) -> dict[str, Any]:
    """Deterministic triage templates (no LLM call), grounded in ranking metadata.

    The old results/gemini_refine_cache.json was also template output
    (scripts/build_gemini_refine_cache.py) mislabelled as Gemini, so it is not served.
    """
    cve_id = body.cve_id.strip()
    action = body.action_type
    content = _synthesize_refine(cve_id, action, body.user_context, _ranking_meta(cve_id))

    return {
        "cve_id": cve_id,
        "action_type": action,
        "content": content,
        "format": "bash" if action == "bash_script" else "prose",
        "cached": False,
        "source": "template",
        "provider": "template",
        "is_ai_generated": False,
        "label": "Template (no AI)",
        "role": "contextual_triage_orchestrator",
        "grounding": "ranking_metadata",
    }
