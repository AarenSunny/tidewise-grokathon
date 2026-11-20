"""Build a scorer grid from orchestrator SourceResults.

Payloads are duck-typed (attributes or dicts). This module does not import
concrete adapters, so a new feed can show up under the registry name and
still reach the gates when its fields match.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from backend.features.timeutil import to_utc
from backend.models.common import SourceStatus
from backend.models.features import (
    ChlorophyllObservation,
    CurrentSample,
    HourlyFeatures,
    SpotFeatureGrid,
    TideSample,
)
from backend.models.scoring import ScoredWindow
from backend.models.sources import SourceResult
from backend.models.spots import Spot

_MS_TO_KT = 1.9438444924406
_SPARSE_GAP_S = 20 * 60


def score_fetched(
    spot: Spot,
    results: dict[str, SourceResult],
    activity: str,
    start: datetime,
    end: datetime,
) -> list[ScoredWindow]:
    """Rank activity windows for one spot from a finished fan-out."""

    from backend.scorers.windows import ranked_windows

    grid, tides, currents = assemble_features(spot, results, start, end)
    return ranked_windows(
        grid,
        activity,
        start,
        end,
        latitude=spot.lat,
        longitude=spot.lon,
        tides=tides or None,
        currents=currents or None,
        as_of=start,
    )


def assemble_features(
    spot: Spot,
    results: dict[str, SourceResult],
    start: datetime,
    end: datetime,
) -> tuple[SpotFeatureGrid, list[TideSample], list[CurrentSample]]:
    """Hourly grid plus the tide and current series the window finder wants."""

    tide_result, tides = _prefer_tides(results)
    current_result, currents = _currents(results.get("coops_currents"))
    ndbc = results.get("ndbc_buoy")
    sst = results.get("erddap_sst")
    chl = results.get("erddap_chl")
    charm = results.get("erddap_charm")
    shellfish = results.get("cdph_shellfish")
    beach = results.get("beachwatch_bacteria")

    statuses: dict[str, SourceStatus] = {}
    if tide_result is not None:
        statuses["coops_tides"] = _effective_status(tide_result)
    if current_result is not None:
        statuses["coops_currents"] = _effective_status(current_result)
    if ndbc is not None:
        statuses["ndbc_buoy"] = _effective_status(ndbc)
    if sst is not None:
        statuses["sst"] = _effective_status(sst)
    elif ndbc is not None and _num(_get(ndbc.data, "wtmp_c")) is not None:
        statuses["sst"] = _effective_status(ndbc)
    if chl is not None:
        statuses["satellite_chl"] = _effective_status(chl)
    if shellfish is not None:
        statuses["alerts_shellfish"] = _effective_status(shellfish)
    if beach is not None:
        statuses["alerts_bacteria"] = _effective_status(beach)

    alerts: list[str] = []
    if shellfish is not None:
        alerts.extend(_shellfish_alerts(shellfish.data, spot))
    if beach is not None:
        alerts.extend(_beach_alerts(beach.data))
    for name, result in results.items():
        if "nws" not in name:
            continue
        alerts.extend(_nws_alerts(result.data))
        status = _nws_status(result)
        statuses["nws_alerts"] = _worse(statuses.get("nws_alerts"), status)
        statuses["nws_marine"] = _worse(statuses.get("nws_marine"), status)

    wind_kt, gust_kt, wind_dir, wave_m, period_s, buoy_sst = _buoy(ndbc.data if ndbc else None)
    sst_c = _num(_get(sst.data, "sst_c")) if sst is not None else None
    if sst_c is None:
        sst_c = buoy_sst
    onshore = _onshore_kt(wind_kt, wind_dir, spot.shoreline_orientation_deg)
    gust_spread = None if wind_kt is None or gust_kt is None else gust_kt - wind_kt

    tide_points = [(to_utc(sample.time, "tide time"), sample.height_ft_mllw) for sample in tides]
    current_points = [(to_utc(sample.time, "current time"), sample.velocity_kt) for sample in currents]
    hours: list[HourlyFeatures] = []
    previous_height: float | None = None
    for stamp in _hour_stamps(start, end):
        height = _sample_series(tide_points, stamp)
        velocity = _sample_series(current_points, stamp, cosine=False)
        phase = _phase(previous_height, height)
        previous_height = height if height is not None else previous_height
        hours.append(
            HourlyFeatures(
                hour=stamp,
                tide_height_ft_mllw=height,
                tide_phase=phase,
                is_slack_water=(abs(velocity) <= 0.5) if velocity is not None else None,
                is_minus_tide=(height <= 0.0) if height is not None else None,
                wind_speed_kt=wind_kt,
                wind_gust_kt=gust_kt,
                wind_dir_deg=wind_dir,
                wind_onshore_component_kt=onshore,
                gust_spread_kt=gust_spread,
                wave_height_m=wave_m,
                wave_period_s=period_s,
                current_velocity_kt=velocity,
                sst_c=sst_c,
                active_alerts=list(alerts),
                source_statuses=dict(statuses),
            )
        )

    grid = SpotFeatureGrid(spot_id=spot.id, hours=hours, chlorophyll=_chlorophyll(chl, charm))
    return grid, tides, currents


def _prefer_tides(results: dict[str, SourceResult]) -> tuple[SourceResult | None, list[TideSample]]:
    chosen: tuple[int, SourceResult, list[TideSample]] | None = None
    for name in ("coops_tides_interval", "coops_tides"):
        result = results.get(name)
        if result is None:
            continue
        samples = _tide_samples(result.data)
        candidate = (len(samples), result, samples)
        if chosen is None or candidate[0] > chosen[0]:
            chosen = candidate
    if chosen is None:
        return None, []
    return chosen[1], chosen[2]


def _currents(result: SourceResult | None) -> tuple[SourceResult | None, list[CurrentSample]]:
    if result is None:
        return None, []
    samples: list[CurrentSample] = []
    for point in _points(result.data):
        moment = _aware(_get(point, "t") or _get(point, "time"))
        velocity = _num(_get(point, "velocity_kt"))
        if moment is None or velocity is None:
            continue
        samples.append(
            CurrentSample(
                time=moment,
                velocity_kt=velocity,
                kind=_get(point, "type") or _get(point, "kind"),
            )
        )
    samples.sort(key=lambda sample: sample.time)
    return result, samples


def _tide_samples(payload: Any) -> list[TideSample]:
    samples: list[TideSample] = []
    for point in _points(payload):
        moment = _aware(_get(point, "t") or _get(point, "time"))
        height = _num(_get(point, "v_ft_mllw") if _has(point, "v_ft_mllw") else _get(point, "height_ft_mllw"))
        if moment is None or height is None:
            continue
        samples.append(
            TideSample(
                time=moment,
                height_ft_mllw=height,
                kind=_get(point, "type") or _get(point, "kind"),
            )
        )
    samples.sort(key=lambda sample: sample.time)
    return samples


def _chlorophyll(
    chl: SourceResult | None,
    charm: SourceResult | None,
) -> ChlorophyllObservation | None:
    if chl is None:
        return None
    observed = _aware(_get(chl.data, "observed_at")) or _aware(chl.observed_at) or _aware(chl.fetched_at)
    if observed is None:
        return None
    probability = _num(_get(charm.data, "probability")) if charm is not None else None
    return ChlorophyllObservation(
        observed_at=observed,
        chl_mg_m3=_num(_get(chl.data, "chla_mg_m3")),
        pseudo_nitzschia_p=probability,
        source_status=_effective_status(chl),
    )


def _shellfish_alerts(payload: Any, spot: Spot) -> list[str]:
    """Only an explicit CDPH boolean is a clear or a closure.

    County pins and free text are not a pass. ``any_region_advisory`` left
    unset stays off the alert list so the shellfish gate cannot_confirm.
    """

    del spot  # county pins are not a dated closure status
    advisory = _get(payload, "any_region_advisory")
    if advisory is True:
        return ["any_region_advisory=true", "cdph_closure=true"]
    if advisory is False:
        return ["any_region_advisory=false", "cdph_closure=false"]
    return []


def _beach_alerts(payload: Any) -> list[str]:
    alerts: list[str] = []
    for record in _get(payload, "records") or []:
        if not isinstance(record, dict):
            continue
        blob = " ".join(str(value) for value in record.values() if isinstance(value, str))
        lowered = blob.lower()
        if any(word in lowered for word in ("advisory", "closure", "sewage", "contamination", "bacteria")):
            alerts.append(blob[:180])
    return alerts


def _nws_alerts(payload: Any) -> list[str]:
    found = _string_list(payload)
    for alert in _get(payload, "alerts") or []:
        if isinstance(alert, str):
            if alert.strip():
                found.append(alert)
            continue
        if _get(alert, "intersects_window") is False:
            continue
        event = _get(alert, "event")
        headline = _get(alert, "headline")
        if isinstance(event, str) and event.strip():
            found.append(event)
        if isinstance(headline, str) and headline.strip():
            found.append(headline)
    if _get(payload, "small_craft_advisory") is True or _get(payload, "gale_warning") is True:
        found.append("small craft advisory")
    if _get(payload, "gale_warning") is True:
        found.append("gale warning")
    if _get(payload, "beach_hazard") is True:
        found.append("beach hazards")
    if _get(payload, "thunderstorm") is True:
        found.append("thunderstorm")
    return found


def _nws_status(result: SourceResult) -> SourceStatus:
    status = _effective_status(result)
    flag_names = ("small_craft_advisory", "gale_warning", "beach_hazard", "thunderstorm")
    present = [name for name in flag_names if _has(result.data, name)]
    if status == SourceStatus.ok and present and any(_get(result.data, name) is None for name in present):
        return SourceStatus.unknown
    return status


def _string_list(payload: Any) -> list[str]:
    found: list[str] = []
    for key in ("alert_texts", "events", "active_event_names"):
        raw = _get(payload, key)
        if isinstance(raw, list):
            found.extend(str(item) for item in raw if isinstance(item, str) and item.strip())
    return found


def _buoy(payload: Any) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    speed = _num(_get(payload, "wspd_ms"))
    gust = _num(_get(payload, "gst_ms"))
    return (
        None if speed is None else speed * _MS_TO_KT,
        None if gust is None else gust * _MS_TO_KT,
        _num(_get(payload, "wdir_deg")),
        _num(_get(payload, "wvht_m")),
        _num(_get(payload, "dpd_s")),
        _num(_get(payload, "wtmp_c")),
    )


def _onshore_kt(speed_kt: float | None, wind_dir: float | None, shore_deg: float | None) -> float | None:
    if speed_kt is None or wind_dir is None or shore_deg is None:
        return None
    return speed_kt * math.cos(math.radians(wind_dir - shore_deg))


def _hour_stamps(start: datetime, end: datetime) -> list[datetime]:
    start_utc = to_utc(start, "window start")
    end_utc = to_utc(end, "window end")
    cursor = start_utc.replace(minute=0, second=0, microsecond=0)
    stamps: list[datetime] = []
    while cursor < end_utc:
        stamp = cursor if cursor >= start_utc else start_utc
        if start_utc <= stamp < end_utc:
            stamps.append(stamp)
        cursor += timedelta(hours=1)
    if not stamps and end_utc > start_utc:
        stamps.append(start_utc)
    return stamps


def _sample_series(
    points: list[tuple[datetime, float]],
    moment: datetime,
    *,
    cosine: bool | None = None,
) -> float | None:
    if len(points) < 2:
        if len(points) == 1 and points[0][0] == moment:
            return points[0][1]
        return None
    if moment < points[0][0] or moment > points[-1][0]:
        return None
    for (time_a, value_a), (time_b, value_b) in zip(points, points[1:]):
        if time_a <= moment <= time_b:
            span = (time_b - time_a).total_seconds()
            if span <= 0:
                return value_b
            fraction = (moment - time_a).total_seconds() / span
            use_cosine = span > _SPARSE_GAP_S if cosine is None else cosine
            if use_cosine:
                midpoint = 0.5 * (value_a + value_b)
                amplitude = 0.5 * (value_a - value_b)
                return midpoint + amplitude * math.cos(math.pi * fraction)
            return value_a + (value_b - value_a) * fraction
    return None


def _phase(previous: float | None, height: float | None) -> str | None:
    if previous is None or height is None:
        return None
    if abs(height - previous) < 0.05:
        return "slack"
    if height < previous:
        return "falling"
    return "rising"


def _effective_status(result: SourceResult) -> SourceStatus:
    status = result.status
    if _get(result.data, "cannot_confirm") is True and status == SourceStatus.ok:
        return SourceStatus.unknown
    if _get(result.data, "stale") is True and status == SourceStatus.ok:
        return SourceStatus.stale
    return status


def _worse(left: SourceStatus | None, right: SourceStatus) -> SourceStatus:
    if left is None:
        return right
    rank = {
        SourceStatus.ok: 0,
        SourceStatus.degraded: 1,
        SourceStatus.stale: 2,
        SourceStatus.unknown: 3,
        SourceStatus.down: 4,
    }
    return left if rank.get(left, 3) >= rank.get(right, 3) else right


def _points(payload: Any) -> list[Any]:
    raw = _get(payload, "points") or []
    return list(raw) if isinstance(raw, list) else []


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _has(obj: Any, key: str) -> bool:
    if isinstance(obj, dict):
        return key in obj
    return hasattr(obj, key)


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return None
    return value


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number
