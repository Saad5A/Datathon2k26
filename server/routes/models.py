"""Multi-model comparison telemetry (Granite vs Gemini vs ranking baseline)."""
from __future__ import annotations

from fastapi import APIRouter

from server.services.data_service import store

router = APIRouter(tags=["models"])


@router.get("/api/models/comparison")
def models_comparison() -> dict:
    gcomp = store.gemini_comparison or {}
    geval = store.gemini_eval or {}
    granite = store.comparison or {}
    meta = store.embed_meta or {}
    hint = granite.get("selection_hint") or {}
    providers = gcomp.get("providers") or {}
    h2h = gcomp.get("head_to_head") or {}

    return {
        "baseline": gcomp.get("baseline")
        or "LightGBM/TF-IDF ranking (results/scores_2026.csv — audited, read-only)",
        "granite": {
            **(providers.get("granite") or {}),
            "n_explanations_loaded": len(store.explanations),
            "embedding_tokens": meta.get("estimated_tokens_this_run"),
            "n_rows_embedded": meta.get("n_rows"),
            "mean_delta_auc_vs_tfidf": hint.get("mean_delta_auc_granite_minus_tfidf"),
            "model_id": meta.get("model_id") or (providers.get("granite") or {}).get("model_id"),
        },
        "gemini": {
            **(providers.get("gemini") or {}),
            "n_explanations_loaded": len(store.gemini_explanations),
            "n_playbooks_loaded": len(store.gemini_playbooks),
            "eval": {
                "total_playbooks_evaluated": geval.get("total_playbooks_evaluated"),
                "schema_conformance_rate": geval.get("schema_conformance_rate"),
                "patch_url_hallucination_rate": geval.get("patch_url_hallucination_rate"),
                "vendor_grounding_pass_rate": geval.get("vendor_grounding_pass_rate"),
                "priority_preservation_rate": geval.get("priority_preservation_rate"),
                "overall_pass_rate": geval.get("overall_pass_rate"),
                "avg_latency_seconds": geval.get("avg_latency_seconds"),
            },
            "model_id": (providers.get("gemini") or {}).get("model_id") or "gemini-2.5-flash",
        },
        "head_to_head": h2h,
        "latency": h2h.get("latency"),
        "token_economics": h2h.get("token_economics"),
        "ranking_consistency": h2h.get("ranking_consistency"),
        "explanation_style": h2h.get("explanation_style"),
        "qualitative_depth": h2h.get("qualitative_depth"),
        "sources": gcomp.get("sources")
        or [
            "results/gemini_subset_comparison.json",
            "results/agent_eval_report.json",
            "results/granite_subset_comparison.json",
            "data_cache/granite_embeddings_watsonx_subset.meta.json",
        ],
        "load_errors": list(store.load_errors),
    }
