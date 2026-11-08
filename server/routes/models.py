"""Multi-model comparison telemetry (Granite vs Gemini vs ranking baseline)."""
from __future__ import annotations

from fastapi import APIRouter

from server.services.data_service import store

router = APIRouter(tags=["models"])

# Documented in docs/ibm.md; used when the untracked data_cache meta file is absent (fresh clone/deploy).
DOCUMENTED_EMBEDDING_MODEL_ID = "ibm-granite/granite-embedding-278m-multilingual"


@router.get("/api/models/comparison")
def models_comparison() -> dict:
    # Comparison artifacts alone do not prove the provider actually generated
    # the summaries surfaced by this backend. Only expose Gemini details when
    # a provenance-qualified live output is loaded.
    has_live_gemini = bool(store.gemini_explanations or store.gemini_playbooks)
    gcomp = (store.gemini_comparison or {}) if has_live_gemini else {}
    geval = (store.gemini_eval or {}) if has_live_gemini else {}
    rmeta = store.ranking_embed_meta or {}
    emeta = store.explanations_meta or {}
    expl = list(store.explanations.values())
    h2h = gcomp.get("head_to_head") or {}
    live_records = list(store.gemini_explanations.values()) + list(store.gemini_playbooks.values())
    live_model_ids = {str(row.get("model_id")) for row in live_records if row.get("model_id")}
    live_model_id = next(iter(live_model_ids)) if len(live_model_ids) == 1 else None
    live_provider = live_records[0].get("provider") if live_records and len({row.get("provider") for row in live_records}) == 1 else None

    return {
        "baseline": gcomp.get("baseline")
        or "LightGBM/TF-IDF ranking (results/scores_2026.csv — audited, read-only)",
        "granite": {
            "embedding_model_id": rmeta.get("model_id") or DOCUMENTED_EMBEDDING_MODEL_ID,
            "embedding_model_id_source": "data_cache/granite_embeddings.meta.json"
            if rmeta.get("model_id")
            else "docs/ibm.md (embedding meta file not present on this server)",
            "embedding_role": "Description embeddings feed the ranking model's text score (submitted model G2).",
            "adoption_note": "Granite text was adopted by a pre-registered rule; no measurable gain over TF-IDF.",
            "instruct_model_id": emeta.get("model_id"),
            "instruct_role": "Granite instruct, run locally, wrote plain-language summaries for an earlier "
            "version of the ranking. AI-generated, unaudited.",
            "summary_coverage": store.explanations_coverage,
            "unaudited_file_counts": {
                "granite_summaries": sum(1 for e in expl if e.get("source") == "granite"),
                "template_fallbacks": sum(1 for e in expl if e.get("source") == "template"),
            },
            "model_id": rmeta.get("model_id") or DOCUMENTED_EMBEDDING_MODEL_ID,
            "mean_delta_auc_vs_tfidf": None,
            "subset_comparison_note": "Exploratory subset, not comparable; see audit/2026-11-07-granite-subset.md.",
        },
        "gemini": {
            "provider": live_provider,
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
            "model_id": live_model_id,
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
            "results/granite_summaries_top100.json",
            "data_cache/granite_embeddings.meta.json",
        ],
        "load_errors": list(store.load_errors),
    }
