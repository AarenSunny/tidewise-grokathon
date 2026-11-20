"""Orchestrator: concurrent adapter fan-out, then live activity scoring.

Does not import concrete adapters — only AdapterRegistry — so A/B cloud-agent
adapters plug in when merged. Features are built from the fetched bundle and
scored with the existing activity scorers. A down source does not drop the
request: whatever can be scored is returned, and a cannot_confirm gate is
never presented as safe.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.adapters.registry import AdapterRegistry
from backend.config import load_region
from backend.config.safety import load_region_rules
from backend.geo.nearby import select_spots as geo_select_spots
from backend.health import HealthMonitor
from backend.models.api import QueryResponse, RecommendResponse
from backend.models.common import Activity, SourceStatus
from backend.models.features import (
    ChlorophyllObservation,
    CurrentSample,
    HourlyFeatures,
    SpotFeatureGrid,
    TideSample,
)
from backend.models.intent import QueryIntent
from backend.models.scoring import ScoredWindow, SpotRecommendation
from backend.models.sources import SourceResult
from backend.models.spots import RegionConfig, Spot
from backend.redact import redact
from backend.scorers.windows import ranked_windows

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
    "nws_alerts",
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
    ) -> tuple[list[Spot], dict[str, float], list[str]]:
        """Resolve spots via geo.nearby (activity, no-take, distance)."""
        return geo_select_spots(
            list(self.region.spots),
            activity,
            spot_id=spot_id,
            lat=lat,
            lon=lon,
            limit=limit,
            bbox=self.region.bbox,
        )

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

        spots, distances, selection_notes = self.select_spots(
            activity, spot_id=spot_id, lat=lat, lon=lon, limit=limit
        )

        # Fan-out per spot concurrently (bounded inside fetch_spot_sources)
        bundles = await asyncio.gather(
            *[self.fetch_spot_sources(s, start, end) for s in spots]
        )

        recs: list[SpotRecommendation] = []
        for bundle in bundles:
            try:
                windows, best_score = score_bundle(bundle, activity, start, end)
            except Exception as exc:  # noqa: BLE001 — one spot must not fail the request
                msg = redact(f"{type(exc).__name__}: {exc}")
                bundle.errors["scoring"] = msg
                logger.warning(
                    "orchestrator scoring isolated fail spot=%s err=%s",
                    bundle.spot.id,
                    msg,
                )
                windows, best_score = [], None
            recs.append(
                SpotRecommendation(
                    spot_id=bundle.spot.id,
                    spot_name=bundle.spot.name,
                    windows=windows,
                    best_score=best_score,
                    distance_km=distances.get(bundle.spot.id),
                )
            )
        degraded = any(
            b.errors or any(r.status.value != "ok" for r in b.results.values())
            for b in bundles
        )
        scored_any = any(rec.windows for rec in recs)
        note = (
            "Live scoring: ranked windows from fetched adapter features and the activity scorers."
        )
        if not scored_any:
            note += " No scoreable windows in this range."
        if degraded:
            note += (
                " One or more sources degraded or down — scored what is available; "
                "unconfirmed gates are not treated as safe."
            )
        if selection_notes:
            note += " " + " ".join(selection_notes)

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
                "IntentBot/ExplainerBot are not wired. "
                "Use GET /recommend?activity=… for live scored windows."
            ),
            health=self.health.snapshot(),
        )


def score_bundle(
    bundle: SpotFetchBundle,
    activity: Activity,
    start: datetime,
    end: datetime,
) -> tuple[list[ScoredWindow], Optional[float]]:
    """Build a feature grid from one spot's adapter bundle and rank windows."""
    grid, tides, currents = features_from_bundle(bundle, start, end)
    windows = ranked_windows(
        grid,
        activity.value,
        start,
        end,
        latitude=bundle.spot.lat,
        longitude=bundle.spot.lon,
        tides=tides or None,
        currents=currents or None,
        as_of=start,
    )
    windows = _present_honestly(windows)
    best = windows[0].score if windows else None
    return windows, best


def _present_honestly(windows: list[ScoredWindow]) -> list[ScoredWindow]:
    """A cannot_confirm or failed gate must never stay eligible."""
    honest: list[ScoredWindow] = []
    for window in windows:
        blocked = (not window.gates) or any(
            (not gate.passed) or gate.cannot_confirm for gate in window.gates
        )
        if window.eligible and blocked:
            window = window.model_copy(update={"eligible": False})
        honest.append(window)
    return honest


def features_from_bundle(
    bundle: SpotFetchBundle,
    start: datetime,
    end: datetime,
) -> tuple[SpotFeatureGrid, list[TideSample], list[CurrentSample]]:
    """Map adapter payloads onto the hourly grid and tide/current series the scorers read."""
    tides = _tide_samples(bundle)
    currents = _current_samples(bundle)
    statuses = _source_statuses(bundle)
    alerts = _alerts(bundle)
    wind, waves, buoy_sst = _buoy(bundle)
    sst = buoy_sst if buoy_sst is not None else _sst(bundle)
    chlorophyll = _chlorophyll(bundle, statuses.get("satellite_chl", SourceStatus.unknown))
    region = load_region_rules().get("spot_regions", {}).get(bundle.spot.id)
    hours = [
        HourlyFeatures(
            hour=moment,
            tide_height_ft_mllw=_nearest_tide(tides, moment),
            is_slack_water=_slack(currents, moment),
            current_velocity_kt=_nearest_current(currents, moment),
            wind_speed_kt=wind[0],
            wind_gust_kt=wind[1],
            wind_dir_deg=wind[2],
            wave_height_m=waves[0],
            wave_period_s=waves[1],
            sst_c=sst,
            active_alerts=list(alerts),
            source_statuses=dict(statuses),
        )
        for moment in _hour_marks(start, end)
    ]
    grid = SpotFeatureGrid(
        spot_id=bundle.spot.id,
        hours=hours,
        chlorophyll=chlorophyll,
        bloom_region=region if isinstance(region, str) else None,
    )
    return grid, tides, currents


def _hour_marks(start: datetime, end: datetime) -> list[datetime]:
    cursor = start.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    if cursor < start:
        cursor += timedelta(hours=1)
    marks: list[datetime] = []
    while cursor < end and len(marks) < 72:
        marks.append(cursor)
        cursor += timedelta(hours=1)
    return marks or [start]


def _field(data: Any, name: str, default: Any = None) -> Any:
    if data is None:
        return default
    if isinstance(data, dict):
        return data.get(name, default)
    return getattr(data, name, default)


def _result(bundle: SpotFetchBundle, name: str) -> Optional[SourceResult]:
    return bundle.results.get(name)


def _tide_samples(bundle: SpotFetchBundle) -> list[TideSample]:
    data = _field(_result(bundle, "coops_tides"), "data")
    samples: list[TideSample] = []
    for point in _field(data, "points", []) or []:
        moment = _field(point, "t")
        height = _field(point, "v_ft_mllw")
        if moment is None or height is None:
            continue
        samples.append(
            TideSample(time=moment, height_ft_mllw=float(height), kind=_field(point, "type"))
        )
    return samples


def _current_samples(bundle: SpotFetchBundle) -> list[CurrentSample]:
    data = _field(_result(bundle, "coops_currents"), "data")
    samples: list[CurrentSample] = []
    for point in _field(data, "points", []) or []:
        moment = _field(point, "t")
        velocity = _field(point, "velocity_kt")
        if moment is None or velocity is None:
            continue
        samples.append(
            CurrentSample(time=moment, velocity_kt=float(velocity), kind=_field(point, "type"))
        )
    return samples


def _nearest_tide(samples: list[TideSample], moment: datetime) -> Optional[float]:
    return _nearest(
        samples,
        moment,
        lambda sample: sample.time,
        lambda sample: sample.height_ft_mllw,
    )


def _nearest_current(samples: list[CurrentSample], moment: datetime) -> Optional[float]:
    return _nearest(samples, moment, lambda sample: sample.time, lambda sample: sample.velocity_kt)


def _slack(samples: list[CurrentSample], moment: datetime) -> Optional[bool]:
    velocity = _nearest_current(samples, moment)
    if velocity is None:
        return None
    return abs(velocity) <= 0.5


def _nearest(samples: list, moment: datetime, time_of, value_of) -> Optional[float]:
    best: Optional[float] = None
    best_gap: Optional[float] = None
    target = moment.astimezone(timezone.utc)
    for sample in samples:
        gap = abs((time_of(sample).astimezone(timezone.utc) - target).total_seconds())
        if gap > 3 * 3600:
            continue
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best = float(value_of(sample))
    return best


def _source_statuses(bundle: SpotFetchBundle) -> dict[str, SourceStatus]:
    statuses: dict[str, SourceStatus] = {}

    def put(source: str, result: Optional[SourceResult], *, downgrade: bool = False) -> None:
        if result is None:
            return
        status = result.status
        if downgrade and result.status == SourceStatus.ok:
            status = SourceStatus.unknown
        current = statuses.get(source)
        statuses[source] = status if current is None else _worse(current, status)

    put("coops_tides", _result(bundle, "coops_tides"))
    put("coops_currents", _result(bundle, "coops_currents"))
    shellfish = _result(bundle, "cdph_shellfish")
    put("alerts_shellfish", shellfish, downgrade=_cannot_confirm(shellfish))
    put("satellite_chl", _result(bundle, "erddap_chl"))
    put("sst", _result(bundle, "erddap_sst"))
    buoy = _result(bundle, "ndbc_buoy")
    put("ndbc_buoy", buoy)
    if _field(_field(buoy, "data"), "wtmp_c") is not None:
        put("sst", buoy)
    nws = _result(bundle, "nws_alerts")
    put("nws_alerts", nws)
    hazard = _field(_field(nws, "data"), "beach_hazard")
    put("nws_marine", nws, downgrade=hazard is None)
    bacteria = _result(bundle, "beachwatch_bacteria")
    put("alerts_bacteria", bacteria, downgrade=_cannot_confirm(bacteria))
    return statuses


def _worse(left: SourceStatus, right: SourceStatus) -> SourceStatus:
    rank = {
        SourceStatus.ok: 0,
        SourceStatus.degraded: 1,
        SourceStatus.stale: 2,
        SourceStatus.unknown: 3,
        SourceStatus.down: 4,
    }
    return left if rank[left] >= rank[right] else right


def _cannot_confirm(result: Optional[SourceResult]) -> bool:
    if result is None:
        return False
    return bool(_field(result.data, "cannot_confirm", False))


def _alerts(bundle: SpotFetchBundle) -> list[str]:
    alerts: list[str] = []
    shellfish = _field(_result(bundle, "cdph_shellfish"), "data")
    advisory = _field(shellfish, "any_region_advisory")
    if advisory is True:
        alerts.append("cdph_closure=true")
    elif advisory is False and not _field(shellfish, "cannot_confirm", True):
        alerts.append("cdph_closure=false")
    nws = _field(_result(bundle, "nws_alerts"), "data")
    for name in _field(nws, "active_event_names", []) or []:
        if isinstance(name, str) and name.strip():
            alerts.append(name)
    if _field(nws, "beach_hazard") is True:
        alerts.append("beach hazards")
    if _field(nws, "small_craft_advisory") is True:
        alerts.append("small craft")
    if _field(nws, "thunderstorm") is True:
        alerts.append("thunderstorm")
    bacteria = _field(_result(bundle, "beachwatch_bacteria"), "data")
    if bacteria is not None and not _field(bacteria, "cannot_confirm", True):
        text = " ".join(str(record) for record in (_field(bacteria, "records", []) or []))
        lowered = text.lower()
        if any(token in lowered for token in ("advisory", "closure", "posted", "sewage")):
            alerts.append("beach closure")
    return alerts


def _buoy(
    bundle: SpotFetchBundle,
) -> tuple[
    tuple[Optional[float], Optional[float], Optional[float]],
    tuple[Optional[float], Optional[float]],
    Optional[float],
]:
    data = _field(_result(bundle, "ndbc_buoy"), "data")
    wind = (
        _num(_field(data, "wspd_kt")),
        _num(_field(data, "gst_kt")),
        _num(_field(data, "wdir_deg")),
    )
    waves = (_num(_field(data, "wvht_m")), _num(_field(data, "dpd_s")))
    return wind, waves, _num(_field(data, "wtmp_c"))


def _sst(bundle: SpotFetchBundle) -> Optional[float]:
    return _num(_field(_field(_result(bundle, "erddap_sst"), "data"), "sst_c"))


def _chlorophyll(bundle: SpotFetchBundle, status: SourceStatus) -> Optional[ChlorophyllObservation]:
    data = _field(_result(bundle, "erddap_chl"), "data")
    observed = _field(data, "observed_at")
    value = _num(_field(data, "chla_mg_m3"))
    if observed is None:
        return None
    return ChlorophyllObservation(observed_at=observed, chl_mg_m3=value, source_status=status)


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number
