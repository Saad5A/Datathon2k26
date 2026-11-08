"""Proof-page telemetry: the audited metrics behind the submitted ranking."""
from __future__ import annotations

from fastapi import APIRouter

from server.services.results_service import build_results

router = APIRouter(tags=["results"])


@router.get("/api/results")
def results() -> dict:
    """Every figure the /results page can quote, with its claim id and audit status."""
    return build_results()
