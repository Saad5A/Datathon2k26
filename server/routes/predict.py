"""Score an uploaded CVE list (CSV/JSON rows parsed by the dashboard).

Known scoreboard CVEs reuse the audited G2 score and reasons. Unknown CVEs use
a transparent, explicitly labelled API fallback; the endpoint never writes to
the repository artifacts.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.services.data_service import store

router = APIRouter(tags=["predict"])

MAX_ROWS = 50_000


class PredictRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(..., min_length=1, max_length=MAX_ROWS)


@router.post("/api/predict")
def predict(request: PredictRequest) -> dict[str, Any]:
    if len(request.rows) > MAX_ROWS:
        raise HTTPException(status_code=413, detail=f"At most {MAX_ROWS} rows are accepted per request.")
    result = store.score_upload(request.rows)
    if not result["rows"]:
        raise HTTPException(status_code=422, detail="No usable rows: every record was missing cve_id.")
    return result
