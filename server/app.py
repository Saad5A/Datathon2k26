"""FastAPI dashboard backend — read-only bridge over results/ and data_cache/.

Run from the repo root:

  uvicorn server.app:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.routes import explanations, models, overview, predict, ranking
from server.services.data_service import store


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="Datathon CVE Ranking API",
    description="Ranking, Granite/Gemini explanations, and transparent upload scoring over the published artifacts.",
    version="0.1.0",
    lifespan=lifespan,
)

# Wildcard origin + credentials is rejected by browsers; local Vite needs * without credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(overview.router)
app.include_router(ranking.router)
app.include_router(predict.router)
app.include_router(explanations.router)
app.include_router(models.router)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "artifacts_loaded": {
            "ranking_rows": len(store.ranking),
            "scores_rows": len(store.scores),
            "explanations": len(store.explanations),
            "playbooks": len(store.playbooks),
            "embeddings": 0 if store.embed_matrix is None else int(store.embed_matrix.shape[0]),
        },
        "capabilities": {
            "ranking": bool(len(store.ranking) or len(store.scores)),
            "gemini_explanations": bool(len(store.gemini_explanations)),
            "upload_scoring": True,
        },
        "load_errors": list(store.load_errors),
    }


@app.get("/health", include_in_schema=False)
def health_alias() -> dict:
    """Compatibility alias for uptime checks that do not use the /api prefix."""
    return health()


@app.post("/api/reload")
def reload_artifacts() -> dict:
    """Re-read results/ and data_cache/ from disk (dev/demo hot reload). Never writes files."""
    store.load()
    return {
        "status": "reloaded",
        "artifacts_loaded": {
            "ranking_rows": len(store.ranking),
            "scores_rows": len(store.scores),
            "explanations": len(store.explanations),
            "playbooks": len(store.playbooks),
            "embeddings": 0 if store.embed_matrix is None else int(store.embed_matrix.shape[0]),
        },
        "load_errors": list(store.load_errors),
    }
