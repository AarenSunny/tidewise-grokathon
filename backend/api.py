"""FastAPI app: /query, /recommend, /health, /spots, debug fail/reset."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.adapters.registry import AdapterRegistry
from backend.cache.memory import MemoryTTLCache
from backend.config import load_region
from backend.health import HealthMonitor
from backend.models.api import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    RecommendResponse,
    SpotsResponse,
)
from backend.models.common import Activity
from backend.orchestrator import Orchestrator
from backend.redact import redact
from backend.settings import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

health_monitor = HealthMonitor()
_cache = MemoryTTLCache()
registry = AdapterRegistry(cache=_cache, health=health_monitor)
region = load_region()
orchestrator = Orchestrator(
    registry,
    region=region,
    overall_deadline_s=settings.orchestrator_deadline_s,
    max_concurrency=settings.orchestrator_max_concurrency,
)


def _debug_enabled() -> bool:
    return bool(settings.debug)


@app.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    snap = health_monitor.snapshot()
    # Belt-and-suspenders: ensure last_error is redacted (review1-#13)
    for h in snap:
        if h.last_error:
            h.last_error = redact(h.last_error)
    return HealthResponse(
        status=health_monitor.overall_status(),
        adapters=snap,
        checked_at=datetime.now(timezone.utc),
    )


@app.get("/spots", response_model=SpotsResponse)
async def get_spots() -> SpotsResponse:
    return SpotsResponse(region_id=region.id, spots=region.spots)


@app.post("/query", response_model=QueryResponse)
async def post_query(body: QueryRequest) -> QueryResponse:
    return await orchestrator.query(body.text)


@app.get("/recommend", response_model=RecommendResponse)
async def get_recommend(
    activity: Activity = Query(...),
    spot: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    lat: float | None = None,
    lon: float | None = None,
    limit: int = Query(6, ge=1, le=15),
) -> RecommendResponse:
    if start is not None and start.tzinfo is None:
        raise HTTPException(status_code=422, detail="start must be timezone-aware")
    if end is not None and end.tzinfo is None:
        raise HTTPException(status_code=422, detail="end must be timezone-aware")
    try:
        return await orchestrator.recommend(
            activity,
            spot_id=spot,
            lat=lat,
            lon=lon,
            start=start,
            end=end,
            limit=limit,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown spot: {spot}") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.post("/debug/fail/{source}")
async def debug_fail(source: str) -> dict:
    if not _debug_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    if source not in registry.names():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source; known={registry.names()}",
        )
    registry.set_forced_down(source, True)
    return {"source": source, "forced_down": True}


@app.post("/debug/reset")
async def debug_reset() -> dict:
    if not _debug_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    registry.reset_forced_down()
    return {"reset": True, "sources": registry.names()}
