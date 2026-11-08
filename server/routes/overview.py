"""High-level summary metrics and token stats."""
from __future__ import annotations

from fastapi import APIRouter

from server.services.data_service import store

router = APIRouter(tags=["overview"])


@router.get("/api/stats/summary")
def stats_summary() -> dict:
    meta = store.embed_meta or {}
    comparison = store.comparison or {}
    ranking = store.ranking
    scores = store.scores

    analyzed = int(meta.get("n_rows") or 0)
    if not analyzed and comparison.get("n_vectors"):
        analyzed = int(comparison["n_vectors"])
    if not analyzed and not ranking.empty:
        analyzed = len(ranking)
    elif not analyzed and not scores.empty:
        analyzed = len(scores)

    tokens = meta.get("estimated_tokens_this_run")
    lite_cap = 300_000
    return {
        "total_analyzed_cves": analyzed,
        "ranking_rows": len(ranking),
        "scores_rows": len(scores),
        "risk_bands": store.risk_band_counts(),
        "token_usage": {
            "estimated_tokens_consumed": tokens,
            "estimated_tokens_consumed_approx": "~233k" if tokens and 200_000 <= int(tokens) <= 260_000 else None,
            "truncate_tokens": meta.get("truncate_tokens", 512),
            "lite_plan_monthly_cap": lite_cap,
            "provider": meta.get("provider", "WATSONX"),
            "model_id": meta.get("model_id", "ibm/granite-embedding-278m-multilingual"),
            "subset": bool(meta.get("subset", True)),
            "n_embedded_this_run": meta.get("n_embedded_this_run"),
        },
        "granite_subset": {
            "n_vectors": comparison.get("n_vectors"),
            "embeddings_files": comparison.get("embeddings_files"),
            "folds_present": sorted((comparison.get("folds") or {}).keys()),
        },
        "load_errors": list(store.load_errors),
    }
