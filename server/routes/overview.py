"""High-level summary metrics and token stats — values come only from loaded files."""
from __future__ import annotations

import json

from fastapi import APIRouter

from server.services.data_service import RESULTS, store

router = APIRouter(tags=["overview"])

CLAIMS_GRANITE_SUBSET = RESULTS / "claims_model_granite_subset.json"


def _verified_claim(claim_id: str) -> dict | None:
    """Claim value read at request time; None unless its ledger status is verified."""
    try:
        claim = json.loads(CLAIMS_GRANITE_SUBSET.read_text(encoding="utf-8")).get(claim_id) or {}
    except (OSError, ValueError):
        return None
    if claim.get("status") != "verified":
        return None
    return {"id": claim_id, "value": claim.get("value"), "verified_by": claim.get("verified_by")}


@router.get("/api/stats/summary")
def stats_summary() -> dict:
    meta = store.embed_meta or {}
    comparison = store.comparison or {}
    ranking = store.ranking
    scores = store.scores
    has_live_gemini = bool(store.gemini_explanations or store.gemini_playbooks)
    folds = comparison.get("folds") or {}

    # Prefer embedding subset row count from meta; else comparison n_vectors; else ranking/scores lengths.
    analyzed = None
    if meta.get("n_rows") is not None:
        analyzed = int(meta["n_rows"])
    elif comparison.get("n_vectors") is not None:
        analyzed = int(comparison["n_vectors"])
    elif not ranking.empty:
        analyzed = len(ranking)
    elif not scores.empty:
        analyzed = len(scores)

    tokens = meta.get("estimated_tokens_this_run")
    tokens_i = int(tokens) if tokens is not None else None

    return {
        "total_analyzed_cves": analyzed,
        "ranking_rows": len(ranking),
        "scores_rows": len(scores),
        "risk_bands": store.risk_band_counts(),
        "token_usage": {
            "estimated_tokens_consumed": tokens_i,
            "truncate_tokens": meta.get("truncate_tokens"),
            "provider": meta.get("provider"),
            "model_id": meta.get("model_id"),
            "subset": meta.get("subset"),
            "n_embedded_this_run": meta.get("n_embedded_this_run"),
            "n_unique_texts": meta.get("n_unique_texts"),
            "dimension": meta.get("dimension"),
            "created_utc": meta.get("created_utc"),
        },
        "comparison": {
            "n_vectors": comparison.get("n_vectors"),
            "embeddings_files": comparison.get("embeddings_files"),
            "folds_present": sorted(folds.keys()),
            # Subset deltas withheld: label-selected subset, not comparable (audit/2026-11-07-granite-subset.md).
            "fold1_delta_auc_granite_minus_tfidf": None,
            "fold2_delta_auc_granite_minus_tfidf": None,
            "mean_delta_auc_granite_minus_tfidf": None,
            "note": "Exploratory subset, not comparable; see audit/2026-11-07-granite-subset.md. "
            "Granite text was adopted by a pre-registered rule with no measurable gain.",
        },
        # Back-compat alias used by older UI bindings
        "granite_subset": {
            "n_vectors": comparison.get("n_vectors"),
            "embeddings_files": comparison.get("embeddings_files"),
            "folds_present": sorted(folds.keys()),
        },
        "sources": {
            "embed_meta": "data_cache/granite_embeddings_watsonx_subset.meta.json",
            "comparison": "results/granite_subset_comparison.json",
            "ranking": "results/top500.csv + results/scores_2026.csv",
            "gemini_comparison": "results/gemini_subset_comparison.json",
            "gemini_eval": "results/agent_eval_report.json",
        },
        "multi_model": {
            # Plain file counts, unaudited; summaries were written for an earlier ranking version.
            "granite_explanations_unaudited": sum(1 for e in store.explanations.values() if e.get("source") == "granite"),
            "granite_template_fallbacks_unaudited": sum(
                1 for e in store.explanations.values() if e.get("source") == "template"
            ),
            "granite_summary_coverage": store.explanations_coverage,
            "gemini_explanations": len(store.gemini_explanations),
            "gemini_playbooks": len(store.gemini_playbooks),
            "gemini_eval_pass_rate": (store.gemini_eval or {}).get("overall_pass_rate") if has_live_gemini else None,
            "gemini_hallucination_rate": (store.gemini_eval or {}).get("patch_url_hallucination_rate") if has_live_gemini else None,
            "gemini_avg_latency_seconds": (store.gemini_eval or {}).get("avg_latency_seconds") if has_live_gemini else None,
            "granite_embedding_tokens": tokens_i,
        },
        "watsonx_subset": _verified_claim("p6.granite_subset.n_vectors"),
        "load_errors": list(store.load_errors),
    }
