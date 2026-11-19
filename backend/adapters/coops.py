"""NOAA CO-OPS tides + currents adapters."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field

from backend.adapters.base import PermanentFetchError, SourceAdapter, TransientFetchError
from backend.models.spots import Spot
from backend.validation import parse_float_or_none

DEFAULT_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
FALLBACK_TIDE_STATION = "9414290"  # San Francisco
DEFAULT_CURRENT_STATION = "SFB1201"  # SF Bay Entrance
UA = os.getenv("NWS_USER_AGENT", "TideWise/0.1 (https://github.com/AarenSunny/tidewise-grokathon)")


class TidePoint(BaseModel):
    t: datetime  # UTC aware
    v_ft_mllw: float
    type: Optional[str] = None  # H / L for hilo; None for interval


class TidePayload(BaseModel):
    station_id: str
    product: str  # predictions_hilo | predictions_interval
    points: list[TidePoint] = Field(default_factory=list)
    observed_at: Optional[datetime] = None
    fallback_used: Optional[str] = None


class CurrentPoint(BaseModel):
    t: datetime
    velocity_kt: Optional[float] = None
    type: Optional[str] = None  # slack / flood / ebb


class CurrentPayload(BaseModel):
    station_id: str
    points: list[CurrentPoint] = Field(default_factory=list)
    observed_at: Optional[datetime] = None


def _parse_coops_time(token: str, *, assume_utc: bool = True) -> datetime:
    """Parse CO-OPS 'YYYY-MM-DD HH:MM' as UTC (we request time_zone=gmt)."""
    dt = datetime.strptime(token.strip(), "%Y-%m-%d %H:%M")
    return dt.replace(tzinfo=timezone.utc)


class CoopsTideAdapter(SourceAdapter):
    """Hi/lo and interval tide predictions. TTL 24h. Station fallback chain."""

    name = "coops_tides"
    ttl = timedelta(hours=24)
    max_age = timedelta(hours=36)  # predictions are forward-looking; obs age = newest point
    max_stale_age = timedelta(hours=48)
    timeout_s = 8.0
    overall_deadline_s = 12.0
    payload_model = TidePayload

    def __init__(self, *args: Any, interval: str = "hilo", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.interval = interval  # hilo | 6
        self.base_url = os.getenv("NOAA_COOPS_API_BASE_URL", DEFAULT_BASE)

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        station = spot.tide_station_id or FALLBACK_TIDE_STATION
        day = start.astimezone(timezone.utc).strftime("%Y%m%d")
        return f"{self.name}:{station}:{self.interval}:{day}"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        stations: list[str] = []
        if spot.tide_station_id:
            stations.append(spot.tide_station_id)
        if FALLBACK_TIDE_STATION not in stations:
            stations.append(FALLBACK_TIDE_STATION)

        last_err: Optional[Exception] = None
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers={"User-Agent": UA},
            follow_redirects=True,
        ) as client:
            for i, station in enumerate(stations):
                try:
                    raw = await self._get_predictions(client, station, start, end)
                    raw["_station_id"] = station
                    if i > 0:
                        raw["_fallback_used"] = f"station:{station}"
                    return raw
                except PermanentFetchError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
                    continue
        raise TransientFetchError(f"all tide stations failed: {last_err}")

    async def _get_predictions(
        self,
        client: httpx.AsyncClient,
        station: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        # Request GMT to avoid ambiguous lst_ldt (review1-#10)
        begin = start.astimezone(timezone.utc).strftime("%Y%m%d")
        end_s = end.astimezone(timezone.utc).strftime("%Y%m%d")
        params = {
            "begin_date": begin,
            "end_date": end_s,
            "station": station,
            "product": "predictions",
            "datum": "MLLW",
            "time_zone": "gmt",
            "interval": self.interval,
            "units": "english",
            "format": "json",
        }
        # Also support "today" style when window is current day
        if begin == end_s == datetime.now(timezone.utc).strftime("%Y%m%d"):
            params = {
                "date": "today",
                "station": station,
                "product": "predictions",
                "datum": "MLLW",
                "time_zone": "gmt",
                "interval": self.interval,
                "units": "english",
                "format": "json",
            }
        resp = await client.get(self.base_url, params=params)
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientFetchError(f"CO-OPS HTTP {resp.status_code}")
        if resp.status_code >= 400:
            raise PermanentFetchError(f"CO-OPS HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if isinstance(data, dict) and "error" in data:
            msg = data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"])
            raise PermanentFetchError(f"CO-OPS error JSON: {msg}")
        return data

    def _validate(self, raw: Any) -> TidePayload:
        if not isinstance(raw, dict):
            raise PermanentFetchError("CO-OPS tide: expected dict")
        if "error" in raw:
            raise PermanentFetchError(f"CO-OPS error: {raw['error']}")
        preds = raw.get("predictions")
        if not preds:
            raise PermanentFetchError("CO-OPS tide: empty predictions")
        points: list[TidePoint] = []
        for row in preds:
            v = parse_float_or_none(row.get("v"))
            if v is None:
                continue
            # Reasonable MLLW ft range
            if v < -8 or v > 16:
                continue
            t = _parse_coops_time(row["t"])
            points.append(TidePoint(t=t, v_ft_mllw=v, type=row.get("type")))
        if not points:
            raise PermanentFetchError("CO-OPS tide: no valid points after validation")
        observed = max(p.t for p in points)
        return TidePayload(
            station_id=str(raw.get("_station_id") or ""),
            product=f"predictions_{self.interval}",
            points=points,
            observed_at=observed,
            fallback_used=raw.get("_fallback_used"),
        )


class CoopsCurrentAdapter(SourceAdapter):
    """Current predictions (MAX_SLACK) for entrance station."""

    name = "coops_currents"
    ttl = timedelta(hours=3)
    max_age = timedelta(hours=12)
    max_stale_age = timedelta(hours=12)
    timeout_s = 8.0
    overall_deadline_s = 12.0
    payload_model = CurrentPayload

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.base_url = os.getenv("NOAA_COOPS_API_BASE_URL", DEFAULT_BASE)

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        station = spot.current_station_id or DEFAULT_CURRENT_STATION
        day = start.astimezone(timezone.utc).strftime("%Y%m%d")
        return f"{self.name}:{station}:MAX_SLACK:{day}"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        station = spot.current_station_id or DEFAULT_CURRENT_STATION
        params = {
            "date": "today",
            "station": station,
            "product": "currents_predictions",
            "time_zone": "gmt",
            "units": "english",
            "format": "json",
            "interval": "MAX_SLACK",
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers={"User-Agent": UA},
            follow_redirects=True,
        ) as client:
            resp = await client.get(self.base_url, params=params)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise TransientFetchError(f"CO-OPS currents HTTP {resp.status_code}")
            if resp.status_code >= 400:
                raise PermanentFetchError(f"CO-OPS currents HTTP {resp.status_code}")
            data = resp.json()
            if isinstance(data, dict) and "error" in data:
                raise PermanentFetchError(f"CO-OPS currents error: {data['error']}")
            data["_station_id"] = station
            return data

    def _validate(self, raw: Any) -> CurrentPayload:
        if not isinstance(raw, dict):
            raise PermanentFetchError("CO-OPS currents: expected dict")
        # Live shape: current_predictions.current_predictions list OR nested
        block = raw.get("current_predictions") or raw.get("predictions") or raw
        rows = block
        if isinstance(block, dict):
            rows = block.get("current_predictions") or block.get("predictions") or []
        if not rows:
            raise PermanentFetchError("CO-OPS currents: empty")
        points: list[CurrentPoint] = []
        for row in rows:
            t_raw = row.get("Time") or row.get("t")
            if not t_raw:
                continue
            t = _parse_coops_time(str(t_raw))
            vel = parse_float_or_none(row.get("Velocity_Major") or row.get("v"))
            points.append(
                CurrentPoint(
                    t=t,
                    velocity_kt=vel,
                    type=row.get("Type") or row.get("type"),
                )
            )
        if not points:
            raise PermanentFetchError("CO-OPS currents: no valid points")
        return CurrentPayload(
            station_id=str(raw.get("_station_id") or ""),
            points=points,
            observed_at=max(p.t for p in points),
        )
