"""FastAPI app skeleton: /query, /recommend, /health, /spots, debug fail/reset."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.health import HealthMonitor
from backend.models.api import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    RecommendResponse,
    SpotsResponse,
)
from backend.models.common import Activity
from backend.config import load_region

app = FastAPI(title="TideWise", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

health_monitor = HealthMonitor()
region = load_region()


def _debug_enabled() -> bool:
    import os

    return os.getenv("DEBUG", "false").lower() in {"1", "true", "yes"}


@app.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    return HealthResponse(
        status=health_monitor.overall_status(),
        adapters=health_monitor.snapshot(),
        checked_at=datetime.now(timezone.utc),
    )


@app.get("/spots", response_model=SpotsResponse)
async def get_spots() -> SpotsResponse:
    return SpotsResponse(region_id=region.id, spots=region.spots)


@app.post("/query", response_model=QueryResponse)
async def post_query(body: QueryRequest) -> QueryResponse:
    raise HTTPException(status_code=501, detail="Query pipeline lands in Phase 6")


@app.get("/recommend", response_model=RecommendResponse)
async def get_recommend(
    activity: Activity = Query(...),
    spot: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> RecommendResponse:
    raise HTTPException(status_code=501, detail="Recommend pipeline lands in Phase 5–6")


@app.post("/debug/fail/{source}")
async def debug_fail(source: str) -> dict:
    if not _debug_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    health_monitor.set_forced_down(source, True)
    return {"source": source, "forced_down": True}


@app.post("/debug/reset")
async def debug_reset() -> dict:
    if not _debug_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    for h in health_monitor.snapshot():
        health_monitor.set_forced_down(h.source_name, False)
    return {"reset": True}
