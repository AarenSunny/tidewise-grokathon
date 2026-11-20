"""Build the scorers' hourly SpotFeatureGrid from real adapter output (PR3-1/PR3-2).

Rules (default-deny):
- A source's status is the *worst* of: the adapter's status, a max_age check of its
  ``observed_at`` made here (PR3-2), a missing/invalid ``observed_at``, and payload-level
  stale/cannot_confirm flags. Values from a non-ok source are dropped (None).
- An empty CDPH advisory list is never "clear": the shellfish source is ``ok`` only when the
  adapter confirmed a dated current status (``cannot_confirm`` False, ``any_region_advisory``
  not None). Otherwise it is ``unknown`` and the gate is cannot_confirm.
- No NWS adapter on main: ``nws_*`` statuses are absent (cannot_confirm).
- NDBC wind is m/s at the adapter; converted to knots here (x1.94384).
- Wind/waves are one observation, attached only to the hour containing it (no forecast).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.models.common import SourceStatus
from backend.models.features import (
    ChlorophyllObservation,
    CurrentSample,
    HourlyFeatures,
    SpotFeatureGrid,
    TideSample,
)
from backend.models.sources import SourceResult
from backend.models.spots import Spot
from backend.source_aliases import SCORER_TO_REGISTRY

MS_TO_KT = 1.94384
SLACK_MAX_KT = 0.5
FUTURE_SKEW = timedelta(minutes=5)
FORWARD_LOOKING = {"coops_tides", "coops_currents"}  # observed_at = newest predicted point
_RANK = {
    SourceStatus.ok: 0,
    SourceStatus.degraded: 1,
    SourceStatus.stale: 2,
    SourceStatus.unknown: 3,
    SourceStatus.down: 4,
}


def ms_to_kt(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value * MS_TO_KT, 2)


def _worst(a: SourceStatus, b: SourceStatus) -> SourceStatus:
    return a if _RANK[a] >= _RANK[b] else b


def effective_status(
    registry_name: str,
    result: Optional[SourceResult],
    *,
    max_age: Optional[timedelta],
    now: datetime,
    error: Optional[str] = None,
) -> tuple[SourceStatus, list[str]]:
    """Worst-of adapter status and an independent max_age/observed_at check."""
    if result is None:
        return SourceStatus.down, [f"{registry_name}: {error or 'no result'}"]
    status = result.status
    notes: list[str] = []
    if result.data is None:
        return _worst(status, SourceStatus.down), [f"{registry_name}: no data"]
    obs = result.observed_at
    if obs is None:
        return _worst(status, SourceStatus.stale), [f"{registry_name}: observed_at missing"]
    age = now - obs
    if age < -FUTURE_SKEW and registry_name not in FORWARD_LOOKING:
        return SourceStatus.down, [f"{registry_name}: observed_at in the future"]
    if max_age is not None and age > max_age and registry_name not in FORWARD_LOOKING:
        status = _worst(status, SourceStatus.stale)
        notes.append(f"{registry_name}: observation {age.total_seconds() / 3600:.1f} h old > max_age")
    return status, notes


SHELLFISH_CLEAR = "any_region_advisory=false"
SHELLFISH_CLOSED = "any_region_advisory=true"


def shellfish_alert_tokens(payload: Any, status: Optional[SourceStatus]) -> list[str]:
    """The ONLY values the scorer's CDPH gate may see (see scorers.predicates).

    Exactly one boolean token, and only from a fresh (status ok), confirmed CDPH result:
    ``any_region_advisory=false`` for an explicit False, ``any_region_advisory=true`` for an
    explicit True. Everything else (None, empty list, county names, truthy/falsy non-bools,
    non-ok status, cannot_confirm) yields no token, i.e. None -> cannot_confirm.
    """
    if payload is None or status is not SourceStatus.ok:
        return []
    if getattr(payload, "cannot_confirm", True) is not False:
        return []
    value = getattr(payload, "any_region_advisory", None)
    if value is False:
        return [SHELLFISH_CLEAR]
    if value is True:
        return [SHELLFISH_CLOSED]
    return []


@dataclass
class GridBuild:
    grid: SpotFeatureGrid
    tides: list[TideSample] = field(default_factory=list)
    currents: list[CurrentSample] = field(default_factory=list)
    statuses: dict[str, SourceStatus] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _cos_interp(points: list[tuple[datetime, float]], t: datetime) -> Optional[float]:
    """Cosine interpolation between consecutive extrema; None outside the span."""
    if len(points) < 2 or t < points[0][0] or t > points[-1][0]:
        return None
    for (t0, v0), (t1, v1) in zip(points, points[1:], strict=False):
        if t0 <= t <= t1:
            span = (t1 - t0).total_seconds()
            if span <= 0:
                return v0
            frac = (t - t0).total_seconds() / span
            return v0 + (v1 - v0) * (1 - math.cos(math.pi * frac)) / 2
    return None


def build_grid(
    spot: Spot,
    results: dict[str, SourceResult],
    errors: dict[str, str],
    start: datetime,
    end: datetime,
    *,
    now: Optional[datetime] = None,
    max_ages: Optional[dict[str, timedelta]] = None,
) -> GridBuild:
    from backend.features.timeutil import LA

    now = now or datetime.now(timezone.utc)
    max_ages = max_ages or {}
    notes: list[str] = []
    statuses: dict[str, SourceStatus] = {}
    data: dict[str, Any] = {}
    raw_payloads: dict[str, Any] = {}

    for key, reg in SCORER_TO_REGISTRY.items():
        if reg is None:
            continue  # no adapter: leave absent so gates are cannot_confirm
        res = results.get(reg)
        st, n = effective_status(reg, res, max_age=max_ages.get(reg), now=now, error=errors.get(reg))
        notes.extend(n)
        payload = res.data if res is not None else None
        # payload-level guards (defense in depth on top of adapter flags)
        if payload is not None and st is SourceStatus.ok:
            if key == "alerts_shellfish":
                if getattr(payload, "cannot_confirm", True) is not False or not isinstance(
                    getattr(payload, "any_region_advisory", None), bool
                ):
                    st = SourceStatus.unknown
                    notes.append("cdph_shellfish: no dated closure status; empty list is not 'clear'")
            elif key == "alerts_bacteria":
                # records are not parsed into exceedances here, so never a confirmed clear
                st = SourceStatus.unknown
                notes.append("beachwatch_bacteria: not parsed into a clear/closed status")
            elif key in ("satellite_chl", "sst") and getattr(payload, "stale", True):
                st = SourceStatus.stale
                notes.append(f"{reg}: payload flagged stale")
        statuses[key] = st
        raw_payloads[key] = payload
        data[key] = payload if st is SourceStatus.ok else None

    # --- predictions -------------------------------------------------------
    tides: list[TideSample] = []
    tide_pts: list[tuple[datetime, float]] = []
    if statuses.get("coops_tides") is SourceStatus.ok and data.get("coops_tides"):
        for p in data["coops_tides"].points:
            tides.append(TideSample(time=p.t, height_ft_mllw=p.v_ft_mllw, kind=p.type))
            tide_pts.append((p.t, p.v_ft_mllw))
    tide_pts.sort()
    currents: list[CurrentSample] = []
    cur_pts: list[tuple[datetime, float]] = []
    if statuses.get("coops_currents") is SourceStatus.ok and data.get("coops_currents"):
        for p in data["coops_currents"].points:
            if p.velocity_kt is None:
                continue
            currents.append(CurrentSample(time=p.t, velocity_kt=p.velocity_kt, kind=p.type))
            cur_pts.append((p.t, p.velocity_kt))
    cur_pts.sort()

    # --- single observations ----------------------------------------------
    ndbc = data.get("ndbc_buoy")
    ndbc_hour = None
    if ndbc is not None and ndbc.observed_at is not None:
        ndbc_hour = ndbc.observed_at.astimezone(LA).replace(minute=0, second=0, microsecond=0)
    sst = data.get("sst")
    sst_c = getattr(sst, "sst_c", None) if sst is not None else None

    alerts = shellfish_alert_tokens(
        data.get("alerts_shellfish"), statuses.get("alerts_shellfish")
    )

    # --- hourly grid -------------------------------------------------------
    first = start.astimezone(LA).replace(minute=0, second=0, microsecond=0)
    last = end.astimezone(LA)
    hours: list[HourlyFeatures] = []
    t = first
    while t < last:
        t_utc = t.astimezone(timezone.utc)
        mid = t_utc + timedelta(minutes=30)
        height = _cos_interp(tide_pts, mid)
        nxt = _cos_interp(tide_pts, mid + timedelta(minutes=30))
        prv = _cos_interp(tide_pts, mid - timedelta(minutes=30))
        phase = None
        if height is not None and nxt is not None and prv is not None:
            phase = "rising" if nxt > prv else "falling"
        vel = _cos_interp(cur_pts, mid)
        wind = gust = wdir = wave = per = spread = None
        if ndbc is not None and ndbc_hour is not None and t == ndbc_hour:
            wind = ms_to_kt(ndbc.wspd_ms)
            gust = ms_to_kt(ndbc.gst_ms)
            wdir = ndbc.wdir_deg
            wave = ndbc.wvht_m
            per = ndbc.dpd_s
            if wind is not None and gust is not None:
                spread = round(gust - wind, 2)
        hours.append(
            HourlyFeatures(
                hour=t,
                tide_height_ft_mllw=None if height is None else round(height, 2),
                tide_phase=phase,
                is_minus_tide=None if height is None else height <= 0,
                is_slack_water=None if vel is None else abs(vel) <= SLACK_MAX_KT,
                current_velocity_kt=None if vel is None else round(vel, 2),
                wind_speed_kt=wind,
                wind_gust_kt=gust,
                wind_dir_deg=wdir,
                gust_spread_kt=spread,
                wave_height_m=wave,
                wave_period_s=per,
                sst_c=sst_c,
                active_alerts=list(alerts),
                source_statuses={k: v for k, v in statuses.items()},
            )
        )
        t += timedelta(hours=1)

    chl = raw_payloads.get("satellite_chl")
    chl_obs = None
    if chl is not None and chl.observed_at is not None:
        ok = statuses["satellite_chl"] is SourceStatus.ok
        chl_obs = ChlorophyllObservation(
            observed_at=chl.observed_at,
            # stale/down values are dropped (None): they can only be cannot_confirm
            chl_mg_m3=getattr(chl, "chla_mg_m3", None) if ok else None,
            source_status=statuses["satellite_chl"],
        )
    grid = SpotFeatureGrid(spot_id=spot.id, hours=hours, chlorophyll=chl_obs)
    return GridBuild(grid=grid, tides=tides, currents=currents, statuses=statuses, notes=notes)
