"""Orchestrator: concurrent adapter fan-out via registry; scorers stubbed.

Does not import concrete adapters — only AdapterRegistry — so A/B cloud-agent
adapters plug in when merged. Scorers/features are off-limits; missing scorers
⇒ empty windows + note (no mock data on the live path).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.adapters.registry import AdapterRegistry
from backend.config import load_region
from backend.geo.nearby import nearest_spots
from backend.health import HealthMonitor
from backend.models.api import QueryResponse, RecommendResponse
from backend.models.common import Activity
from backend.models.intent import QueryIntent
from backend.models.scoring import SpotRecommendation
from backend.models.sources import SourceResult
from backend.models.spots import RegionConfig, Spot
from backend.redact import redact

logger = logging.getLogger(__name__)

# Default sources for a recommend/query fan-out (registry names; absent → skipped)
DEFAULT_SOURCES = (
    "coops_tides",
    "coops_currents",
    "ndbc_buoy",
    "erddap_chl",
    "erddap_sst",
    "erddap_charm",
    "cdph_shellfish",
    "beachwatch_bacteria",
    "epa_uv",
    "nws_forecast",  # A may add
    "daylight_sunrise_api",
)


@dataclass
class SpotFetchBundle:
    spot: Spot
    results: dict[str, SourceResult] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class Orchestrator:
    """Fans out to registered adapters with deadline, concurrency, isolation."""

    def __init__(
        self,
        registry: AdapterRegistry,
        *,
        region: Optional[RegionConfig] = None,
        overall_deadline_s: float = 20.0,
        max_concurrency: int = 8,
        sources: Optional[tuple[str, ...]] = None,
    ) -> None:
        self.registry = registry
        self.region = region or load_region()
        self.overall_deadline_s = overall_deadline_s
        self.max_concurrency = max_concurrency
        self.sources = sources or DEFAULT_SOURCES

    @property
    def health(self) -> HealthMonitor:
        return self.registry.health

    def select_spots(
        self,
        activity: Activity,
        *,
        spot_id: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        limit: int = 6,
    ) -> tuple[list[Spot], dict[str, float]]:
        """Resolve spots (uses geo.nearby when lat/lon given)."""
        distances: dict[str, float] = {}
        if spot_id:
            match = next((s for s in self.region.spots if s.id == spot_id), None)
            if match is None:
                raise KeyError(spot_id)
            if activity not in match.activities:
                raise ValueError(f"spot {spot_id} does not support {activity.value}")
            return [match], distances
        if lat is not None and lon is not None:
            ranked = nearest_spots(
                self.region.spots, lat=lat, lon=lon, activity=activity, limit=limit
            )
            distances = {s.id: round(d, 2) for s, d in ranked}
            return [s for s, _ in ranked], distances
        selected = [s for s in self.region.spots if activity in s.activities][:limit]
        return selected, distances

    async def fetch_spot_sources(
        self,
        spot: Spot,
        start: datetime,
        end: datetime,
        *,
        sources: Optional[list[str]] = None,
    ) -> SpotFetchBundle:
        """Fetch all requested sources for one spot; isolate failures."""
        names = [n for n in (sources or list(self.sources)) if self.registry.get(n)]
        sem = asyncio.Semaphore(self.max_concurrency)
        bundle = SpotFetchBundle(spot=spot)

        async def _one(name: str) -> None:
            adapter = self.registry.get(name)
            if adapter is None:
                return
            async with sem:
                try:
                    result = await adapter.fetch(spot, start, end)
                    bundle.results[name] = result
                except Exception as exc:  # noqa: BLE001 — never fail the request
                    msg = redact(f"{type(exc).__name__}: {exc}")
                    bundle.errors[name] = msg
                    logger.warning(
                        "orchestrator source isolated fail source=%s spot=%s err=%s",
                        name,
                        spot.id,
                        msg,
                    )

        try:
            await asyncio.wait_for(
                asyncio.gather(*[_one(n) for n in names]),
                timeout=self.overall_deadline_s,
            )
        except asyncio.TimeoutError:
            for n in names:
                if n not in bundle.results and n not in bundle.errors:
                    bundle.errors[n] = "orchestrator_deadline_exceeded"
        return bundle

    async def recommend(
        self,
        activity: Activity,
        *,
        spot_id: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 6,
    ) -> RecommendResponse:
        now = datetime.now(timezone.utc)
        start = start or now
        end = end or (now + timedelta(hours=24))
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start/end must be timezone-aware UTC")

        spots, distances = self.select_spots(
            activity, spot_id=spot_id, lat=lat, lon=lon, limit=limit
        )

        # Fan-out per spot concurrently (bounded inside fetch_spot_sources)
        bundles = await asyncio.gather(
            *[self.fetch_spot_sources(s, start, end) for s in spots]
        )

        # Scorer boundary: no FeatureEngine/ActivityScorers on this track.
        # Live path returns empty windows + honest note (no mock scores).
        recs = [
            SpotRecommendation(
                spot_id=b.spot.id,
                spot_name=b.spot.name,
                windows=[],
                best_score=None,
                distance_km=distances.get(b.spot.id),
            )
            for b in bundles
        ]
        degraded = any(
            b.errors or any(r.status.value != "ok" for r in b.results.values())
            for b in bundles
        )
        note = (
            "Adapter fan-out complete via registry; scoring pipeline not wired "
            "(backend/scorers + features owned elsewhere). windows empty by design."
        )
        if degraded:
            note += " One or more sources degraded/down — see health."

        return RecommendResponse(
            activity=activity,
            spot_ids=[s.id for s in spots],
            start=start,
            end=end,
            recommendations=recs,
            health=self.health.snapshot(),
            distances_km=distances,
            note=note,
        )

    async def query(self, text: str) -> QueryResponse:
        """IntentBot not wired yet — return clarifying stub without crashing."""
        intent = QueryIntent(raw_text=text[:2000])
        return QueryResponse(
            intent=intent,
            clarifying=None,
            recommendations=[],
            explanation=(
                "IntentBot/ExplainerBot land in Phase 6. "
                "Use GET /recommend?activity=… for structured (unscored) results."
            ),
            health=self.health.snapshot(),
        )
