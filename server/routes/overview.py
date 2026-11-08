"""High-level summary metrics and token stats — values come only from loaded files."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.services.data_service import store

router = APIRouter(tags=["overview"])


def _fold_delta(folds: dict[str, Any], fold: str) -> float | None:
    models = ((folds.get(fold) or {}).get("models") or {})
    delta = models.get("delta_auc_granite_minus_tfidf")
    return float(delta) if isinstance(delta, (int, float)) else None


@router.get("/api/stats/summary")
def stats_summary() -> dict:
    meta = store.embed_meta or {}
    comparison = store.comparison or {}
    ranking = store.ranking
    scores = store.scores
    has_live_gemini = bool(store.gemini_explanations or store.gemini_playbooks)
    folds = comparison.get("folds") or {}
    hint = comparison.get("selection_hint") or {}

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

    fold1_delta = _fold_delta(folds, "fold1")
    fold2_delta = _fold_delta(folds, "fold2")
    mean_delta = hint.get("mean_delta_auc_granite_minus_tfidf")
    if mean_delta is None and fold1_delta is not None and fold2_delta is not None:
        mean_delta = (fold1_delta + fold2_delta) / 2.0
    elif mean_delta is not None:
        mean_delta = float(mean_delta)

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
            "fold1_delta_auc_granite_minus_tfidf": fold1_delta,
            "fold2_delta_auc_granite_minus_tfidf": fold2_delta,
            "mean_delta_auc_granite_minus_tfidf": mean_delta,
            "prefer": hint.get("prefer"),
            "rule": hint.get("rule"),
            "note": comparison.get("note"),
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
            "granite_explanations": len(store.explanations),
            "gemini_explanations": len(store.gemini_explanations),
            "gemini_playbooks": len(store.gemini_playbooks),
            "gemini_eval_pass_rate": (store.gemini_eval or {}).get("overall_pass_rate") if has_live_gemini else None,
            "gemini_hallucination_rate": (store.gemini_eval or {}).get("patch_url_hallucination_rate") if has_live_gemini else None,
            "gemini_avg_latency_seconds": (store.gemini_eval or {}).get("avg_latency_seconds") if has_live_gemini else None,
            "granite_embedding_tokens": tokens_i,
        },
        "load_errors": list(store.load_errors),
    }
