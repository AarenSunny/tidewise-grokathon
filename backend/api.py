"""FastAPI app: /query, /recommend, /health, /spots, debug fail/reset."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.adapters.registry import AdapterRegistry
from backend.cache.memory import MemoryTTLCache
from backend.config import load_region
from backend.geo.nearby import nearest_spots
from backend.health import HealthMonitor
from backend.models.api import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    RecommendResponse,
    SpotsResponse,
)
from backend.models.common import Activity
from backend.models.scoring import SpotRecommendation

app = FastAPI(title="TideWise", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

health_monitor = HealthMonitor()
_cache = MemoryTTLCache()
registry = AdapterRegistry(cache=_cache, health=health_monitor)
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
    lat: float | None = None,
    lon: float | None = None,
    limit: int = Query(6, ge=1, le=15),
) -> RecommendResponse:
    """Resolve nearby/filtered spots. Scoring pipeline lands in Phase 5–6.

    When lat/lon provided, returns nearest spots (activity-filtered) with
    empty recommendations and a note — so nearby selection is demoable now.
    """
    if start is not None and start.tzinfo is None:
        raise HTTPException(status_code=422, detail="start must be timezone-aware")
    if end is not None and end.tzinfo is None:
        raise HTTPException(status_code=422, detail="end must be timezone-aware")

    distances: dict[str, float] = {}
    selected_ids: list[str] = []

    if spot:
        match = next((s for s in region.spots if s.id == spot), None)
        if match is None:
            raise HTTPException(status_code=404, detail=f"Unknown spot: {spot}")
        if activity not in match.activities:
            raise HTTPException(
                status_code=400,
                detail=f"Spot {spot} does not support activity {activity.value}",
            )
        selected_ids = [match.id]
    elif lat is not None and lon is not None:
        ranked = nearest_spots(
            region.spots, lat=lat, lon=lon, activity=activity, limit=limit
        )
        selected_ids = [s.id for s, _ in ranked]
        distances = {s.id: round(d, 2) for s, d in ranked}
    else:
        selected_ids = [s.id for s in region.spots if activity in s.activities][:limit]

    stubs = [
        SpotRecommendation(
            spot_id=sid,
            spot_name=next(s.name for s in region.spots if s.id == sid),
            windows=[],
            best_score=None,
            distance_km=distances.get(sid),
        )
        for sid in selected_ids
    ]

    return RecommendResponse(
        activity=activity,
        spot_ids=selected_ids,
        start=start,
        end=end,
        recommendations=stubs,
        health=health_monitor.snapshot(),
        distances_km=distances,
        note=(
            "Nearby/spot resolution only — scoring pipeline lands in Phase 5–6. "
            "recommendations windows are empty by design."
        ),
    )


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
