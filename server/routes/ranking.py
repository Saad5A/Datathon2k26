"""Ranked CVE list with pagination, search, sorting, and similarity."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from server.services.data_service import store

router = APIRouter(tags=["ranking"])


@router.get("/api/ranking/cves")
def list_cves(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    search: str | None = Query(None, description="Case-insensitive CVE ID substring filter"),
    min_score: float | None = Query(None, description="Minimum priority score"),
    sort: str = Query("rank", description="Sort field: rank|score|cve_id"),
    order: str = Query("asc", description="asc|desc"),
) -> dict:
    df = store.ranking
    if df.empty:
        df = store.scores
    if df.empty:
        return {"total": 0, "page": page, "limit": limit, "items": [], "warning": "no ranking data loaded"}

    view = df.copy()
    if search:
        needle = search.strip().upper()
        view = view[view["cve_id"].astype(str).str.upper().str.contains(needle, regex=False, na=False)]
    if min_score is not None and "score" in view.columns:
        view = view[view["score"].fillna(float("-inf")) >= float(min_score)]

    sort_col = sort if sort in view.columns else "rank" if "rank" in view.columns else view.columns[0]
    ascending = order.lower() != "desc"
    # Stable secondary key so pages are deterministic.
    by = [sort_col]
    if "cve_id" in view.columns and sort_col != "cve_id":
        by.append("cve_id")
    view = view.sort_values(by=by, ascending=ascending, kind="mergesort")

    total = len(view)
    start = (page - 1) * limit
    chunk = view.iloc[start : start + limit]
    items = [store.cve_record(row) for _, row in chunk.iterrows()]
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit else 0,
        "sort": sort_col,
        "order": "desc" if not ascending else "asc",
        "items": items,
    }


@router.get("/api/ranking/sample")
def sample_cves(
    priority: str = Query(..., pattern="^P[0-3]$"),
    n: int = Query(2, ge=1, le=20),
) -> dict:
    """Random sample of scored CVEs with one priority, read-only from scores_2026.csv.

    Used for the 3D stack's per-tier sample (P2 rows sit outside the 500-row ranking).
    Rank, priority, score and reasons are the scores file's own values.
    """
    df = store.scores
    if df.empty or "priority" not in df.columns:
        return {"priority": priority, "n": 0, "items": [], "warning": "no scores loaded"}
    pool = df[df["priority"].astype(str) == priority]
    chunk = pool.sample(n=min(n, len(pool))) if len(pool) else pool
    return {
        "priority": priority,
        "n": len(chunk),
        "pool_size": int(len(pool)),
        "source": "results/scores_2026.csv",
        "items": [store.cve_record(row) for _, row in chunk.iterrows()],
    }


@router.get("/api/ranking/similar/{cve_id}")
def similar_cves(cve_id: str, top_k: int = Query(5, ge=1, le=25)) -> dict:
    cid = cve_id.strip().upper()
    if not cid.startswith("CVE-"):
        # allow either form; normalise common casing
        cid = cve_id.strip()
    # Prefer exact match against stored ids (preserve original casing from file).
    result = store.similar_cves(cve_id.strip(), top_k=top_k)
    if result is None:
        # try uppercase variant
        result = store.similar_cves(cid, top_k=top_k)
    if result is None:
        if store.similar_matrix is None:
            raise HTTPException(status_code=503, detail="Similarity index not loaded")
        raise HTTPException(status_code=404, detail=f"CVE not in the retrieval index: {cve_id}")
    meta = store.similar_meta or {}
    return {
        "cve_id": cve_id,
        "top_k": top_k,
        "similar": result,
        "index": {
            "model_id": meta.get("model_id"),
            "dimension": meta.get("dimension"),
            "rows": int(len(store.similar_ids)),
            "purpose": meta.get("purpose") or "retrieval only; not used for scoring",
        },
        "note": "Description-similarity neighbours. Retrieval evidence only, not a probability of exploitation.",
    }
