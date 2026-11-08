"""FastAPI dashboard backend — read-only bridge over results/ and data_cache/.

Run from the repo root:

  uvicorn server.app:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.routes import explanations, overview, ranking
from server.services.data_service import store


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="Datathon CVE Ranking API",
    description="Lightweight read-only API over ranking outputs and Granite artifacts.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(overview.router)
app.include_router(ranking.router)
app.include_router(explanations.router)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "provider": "watsonx.ai",
        "model": "ibm-granite",
        "artifacts_loaded": {
            "ranking_rows": len(store.ranking),
            "scores_rows": len(store.scores),
            "explanations": len(store.explanations),
            "playbooks": len(store.playbooks),
            "embeddings": 0 if store.embed_matrix is None else int(store.embed_matrix.shape[0]),
        },
        "load_errors": list(store.load_errors),
    }
