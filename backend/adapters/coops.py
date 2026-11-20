"""NOAA CO-OPS tide predictions (hi/lo and 6-minute) and current predictions.

Times are requested with time_zone=gmt and stored as timezone-aware UTC.
DATA_SOURCES.md shows lst_ldt examples; those strings have no offset and are
ambiguous on the DST fallback hour (review #10), so this adapter does not use them.

Heights are feet MLLW (units=english, datum=MLLW). Current speeds are knots
(units=english); ebb is negative. A missing station, empty series, unknown
units, or unparseable payload is a hard failure (status down) — never a
substituted station and never a zero filled in for a missing speed.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field, field_validator

from backend.adapters.base import PermanentFetchError, SourceAdapter, TransientFetchError
from backend.models.common import require_aware
from backend.models.spots import Spot
from backend.validation import parse_float_or_none

DEFAULT_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
DEFAULT_UA = "TideWise/0.1 (https://github.com/AarenSunny/tidewise-grokathon)"
_STATION_RE = re.compile(r"^[A-Za-z0-9]{4,15}$")
# SF Bay tide extremes sit well inside this; outside it is garbage, not a clamp.
_TIDE_LO_FT = -6.0
_TIDE_HI_FT = 12.0
_CURRENT_ABS_MAX_KT = 10.0
_MAX_WINDOW = timedelta(days=31)


def user_agent() -> str:
    raw = os.getenv("NWS_USER_AGENT", "").strip()
    if not raw or "@" in raw:
        return DEFAULT_UA
    return raw


def _as_utc(dt: datetime) -> datetime:
    aware = require_aware(dt)
    return aware.astimezone(timezone.utc)


def _parse_coops_time(token: str) -> datetime:
    """Parse CO-OPS 'YYYY-MM-DD HH:MM' as UTC.

    Callers must request time_zone=gmt. Naive local strings are not accepted.
    """
    text = str(token).strip()
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise PermanentFetchError("CO-OPS: unparseable timestamp") from exc
    return dt.replace(tzinfo=timezone.utc)


def _check_station(station_id: str, *, what: str) -> str:
    sid = (station_id or "").strip()
    if not _STATION_RE.fullmatch(sid):
        raise PermanentFetchError(f"CO-OPS {what}: missing or invalid station id")
    return sid


def _window_dates(start: datetime, end: datetime) -> tuple[datetime, datetime, str, str]:
    try:
        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
    except ValueError as exc:
        raise PermanentFetchError("CO-OPS: datetimes must be timezone-aware") from exc
    if end_utc <= start_utc:
        raise PermanentFetchError("CO-OPS: end must be after start")
    if end_utc - start_utc > _MAX_WINDOW:
        raise PermanentFetchError("CO-OPS: window exceeds 31 days")
    # Half-open [start, end): a midnight end stays on the previous UTC date.
    inclusive_end = end_utc - timedelta(microseconds=1)
    begin = start_utc.strftime("%Y%m%d")
    end_s = inclusive_end.strftime("%Y%m%d")
    return start_utc, end_utc, begin, end_s


def _short_message(data: dict[str, Any]) -> str:
    err = data.get("error")
    if isinstance(err, dict):
        msg = str(err.get("message") or "")
    else:
        msg = str(err or "")
    msg = " ".join(msg.split())[:120]
    lowered = msg.lower()
    if not msg or "http://" in lowered or "https://" in lowered or "@" in msg:
        return "product unavailable"
    return msg


class TidePoint(BaseModel):
    t: datetime
    v_ft_mllw: float
    type: Optional[str] = None  # H / L for hi/lo; None for 6-minute

    @field_validator("t")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _as_utc(v)


class TidePayload(BaseModel):
    station_id: str
    product: str  # predictions_hilo | predictions_6
    datum: str = "MLLW"
    units: str = "ft"
    points: list[TidePoint] = Field(default_factory=list)
    observed_at: datetime
    # Optional so callers/tests that only have a series still construct.
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    dropped_points: int = 0
    notes: list[str] = Field(default_factory=list)

    @field_validator("observed_at", "window_start", "window_end")
    @classmethod
    def _utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        return _as_utc(v)


class CurrentPoint(BaseModel):
    t: datetime
    velocity_kt: float
    type: str  # slack | flood | ebb
    depth_ft: Optional[float] = None
    bin_id: Optional[str] = None

    @field_validator("t")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _as_utc(v)


class CurrentPayload(BaseModel):
    station_id: str
    units: str = "knots"
    points: list[CurrentPoint] = Field(default_factory=list)
    observed_at: datetime
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    depth_ft: Optional[float] = None
    bin_id: Optional[str] = None
    dropped_points: int = 0
    notes: list[str] = Field(default_factory=list)

    @field_validator("observed_at", "window_start", "window_end")
    @classmethod
    def _utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        return _as_utc(v)


class CoopsTideAdapter(SourceAdapter):
    """Hi/lo (`interval=hilo`) or 6-minute (`interval=6`) tide predictions."""

    name = "coops_tides"
    ttl = timedelta(hours=6)
    max_age = timedelta(hours=36)
    max_stale_age = timedelta(hours=12)
    timeout_s = 8.0
    overall_deadline_s = 12.0
    # An old tide series must not be served as a usable ok/stale pass.
    safety_critical = True
    payload_model = TidePayload

    def __init__(self, *args: Any, interval: str = "hilo", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if interval not in {"hilo", "6"}:
            raise PermanentFetchError(f"CO-OPS tide: unsupported interval {interval}")
        self.interval = interval
        self.base_url = os.getenv("NOAA_COOPS_API_BASE_URL", DEFAULT_BASE).strip() or DEFAULT_BASE

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        station = spot.tide_station_id or "missing"
        try:
            _, _, begin, end_s = _window_dates(start, end)
        except (PermanentFetchError, ValueError):
            begin, end_s = "bad", "bad"
        return f"{self.name}:{station}:{self.interval}:{begin}:{end_s}"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        station = _check_station(spot.tide_station_id or "", what="tide")
        start_utc, end_utc, begin, end_s = _window_dates(start, end)
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
            "application": "TideWise",
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers={"User-Agent": user_agent(), "Accept": "application/json"},
            follow_redirects=True,
        ) as client:
            data = await self._get_json(client, params, what="tide")
        if not isinstance(data, dict):
            raise PermanentFetchError("CO-OPS tide: expected JSON object")
        meta = data.get("metadata")
        if isinstance(meta, dict) and meta.get("id") and str(meta["id"]) != station:
            raise PermanentFetchError("CO-OPS tide: station id mismatch")
        data["_station_id"] = station
        data["_window_start"] = start_utc.isoformat()
        data["_window_end"] = end_utc.isoformat()
        return data

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        params: dict[str, str],
        *,
        what: str,
    ) -> dict[str, Any]:
        try:
            resp = await client.get(self.base_url, params=params)
        except httpx.TimeoutException:
            raise TransientFetchError(f"CO-OPS {what}: timeout") from None
        except httpx.TransportError:
            raise TransientFetchError(f"CO-OPS {what}: connection failed") from None
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientFetchError(f"CO-OPS {what}: HTTP {resp.status_code}")
        if resp.status_code != 200:
            raise PermanentFetchError(f"CO-OPS {what}: HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError:
            raise PermanentFetchError(f"CO-OPS {what}: response was not JSON") from None
        if isinstance(data, dict) and "error" in data:
            raise PermanentFetchError(f"CO-OPS {what}: {_short_message(data)}")
        if not isinstance(data, dict):
            raise PermanentFetchError(f"CO-OPS {what}: expected JSON object")
        return data

    def _validate(self, raw: Any) -> TidePayload:
        if not isinstance(raw, dict):
            raise PermanentFetchError("CO-OPS tide: expected dict")
        if "error" in raw:
            raise PermanentFetchError(f"CO-OPS tide: {_short_message(raw)}")
        station = _check_station(str(raw.get("_station_id") or ""), what="tide")
        preds = raw.get("predictions")
        if not isinstance(preds, list) or not preds:
            raise PermanentFetchError("CO-OPS tide: empty predictions")

        points: list[TidePoint] = []
        dropped = 0
        for row in preds:
            if not isinstance(row, dict):
                dropped += 1
                continue
            height = parse_float_or_none(row.get("v"))
            if height is None or height < _TIDE_LO_FT or height > _TIDE_HI_FT:
                dropped += 1
                continue
            try:
                when = _parse_coops_time(str(row.get("t") or ""))
            except PermanentFetchError:
                dropped += 1
                continue
            kind: Optional[str] = None
            raw_type = row.get("type")
            if raw_type is not None and str(raw_type).strip():
                kind = str(raw_type).strip().upper()
            if self.interval == "hilo":
                if kind not in {"H", "L"}:
                    dropped += 1
                    continue
            elif kind not in {"H", "L"}:
                kind = None
            points.append(TidePoint(t=when, v_ft_mllw=height, type=kind))

        if not points:
            raise PermanentFetchError("CO-OPS tide: no valid points after validation")
        points.sort(key=lambda p: (p.t, p.type or ""))
        deduped: list[TidePoint] = []
        seen: set[tuple[datetime, Optional[str]]] = set()
        for point in points:
            key = (point.t, point.type)
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
            deduped.append(point)
        notes: list[str] = []
        if dropped:
            notes.append(f"dropped_invalid_points={dropped}")
        window_start, window_end = _optional_window(raw, deduped[0].t, deduped[-1].t)
        return TidePayload(
            station_id=station,
            product=f"predictions_{self.interval}",
            points=deduped,
            observed_at=max(p.t for p in deduped),
            window_start=window_start,
            window_end=window_end,
            dropped_points=dropped,
            notes=notes,
        )


class CoopsCurrentAdapter(SourceAdapter):
    """Current predictions (MAX_SLACK) in knots. Ebb is negative."""

    name = "coops_currents"
    ttl = timedelta(hours=3)
    max_age = timedelta(hours=36)
    max_stale_age = timedelta(hours=6)
    timeout_s = 8.0
    overall_deadline_s = 12.0
    safety_critical = True
    payload_model = CurrentPayload

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.base_url = os.getenv("NOAA_COOPS_API_BASE_URL", DEFAULT_BASE).strip() or DEFAULT_BASE

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        station = spot.current_station_id or "missing"
        try:
            _, _, begin, end_s = _window_dates(start, end)
        except (PermanentFetchError, ValueError):
            begin, end_s = "bad", "bad"
        return f"{self.name}:{station}:MAX_SLACK:{begin}:{end_s}"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        station = _check_station(spot.current_station_id or "", what="currents")
        start_utc, end_utc, begin, end_s = _window_dates(start, end)
        params = {
            "begin_date": begin,
            "end_date": end_s,
            "station": station,
            "product": "currents_predictions",
            "time_zone": "gmt",
            "units": "english",
            "format": "json",
            "interval": "MAX_SLACK",
            "application": "TideWise",
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers={"User-Agent": user_agent(), "Accept": "application/json"},
            follow_redirects=True,
        ) as client:
            try:
                resp = await client.get(self.base_url, params=params)
            except httpx.TimeoutException:
                raise TransientFetchError("CO-OPS currents: timeout") from None
            except httpx.TransportError:
                raise TransientFetchError("CO-OPS currents: connection failed") from None
            if resp.status_code == 429 or resp.status_code >= 500:
                raise TransientFetchError(f"CO-OPS currents: HTTP {resp.status_code}")
            if resp.status_code != 200:
                raise PermanentFetchError(f"CO-OPS currents: HTTP {resp.status_code}")
            try:
                data = resp.json()
            except ValueError:
                raise PermanentFetchError("CO-OPS currents: response was not JSON") from None
        if isinstance(data, dict) and "error" in data:
            raise PermanentFetchError(f"CO-OPS currents: {_short_message(data)}")
        if not isinstance(data, dict):
            raise PermanentFetchError("CO-OPS currents: expected JSON object")
        data["_station_id"] = station
        data["_window_start"] = start_utc.isoformat()
        data["_window_end"] = end_utc.isoformat()
        return data

    def _validate(self, raw: Any) -> CurrentPayload:
        if not isinstance(raw, dict):
            raise PermanentFetchError("CO-OPS currents: expected dict")
        if "error" in raw:
            raise PermanentFetchError(f"CO-OPS currents: {_short_message(raw)}")
        station = _check_station(str(raw.get("_station_id") or ""), what="currents")
        block = raw.get("current_predictions")
        units_text = ""
        rows: Any = None
        if isinstance(block, dict):
            units_text = str(block.get("units") or "")
            # Live shape is {"units": "feet, knots", "cp": [...]} (probe 2026-11-19).
            rows = block.get("cp")
            if rows is None:
                rows = block.get("current_predictions") or block.get("predictions")
        elif isinstance(block, list):
            rows = block
        if rows is None:
            rows = raw.get("predictions")
        if not isinstance(rows, list) or not rows:
            raise PermanentFetchError("CO-OPS currents: empty predictions")
        if units_text and "knot" not in units_text.lower():
            raise PermanentFetchError("CO-OPS currents: units are not knots")
        if not units_text:
            raise PermanentFetchError("CO-OPS currents: units unconfirmed")

        parsed: list[CurrentPoint] = []
        dropped = 0
        for row in rows:
            point = _parse_current_row(row)
            if point is None:
                dropped += 1
                continue
            parsed.append(point)
        if not parsed:
            raise PermanentFetchError("CO-OPS currents: no valid points after validation")

        chosen_bin, depth = _select_bin(parsed)
        points = [p for p in parsed if p.bin_id == chosen_bin]
        dropped += len(parsed) - len(points)
        points.sort(key=lambda p: p.t)
        deduped: list[CurrentPoint] = []
        seen: set[datetime] = set()
        for point in points:
            if point.t in seen:
                dropped += 1
                continue
            seen.add(point.t)
            deduped.append(point)
        if not deduped:
            raise PermanentFetchError("CO-OPS currents: no valid points after bin select")
        notes: list[str] = []
        if dropped:
            notes.append(f"dropped_invalid_points={dropped}")
        if chosen_bin is not None:
            notes.append(f"bin={chosen_bin}")
        window_start, window_end = _optional_window(raw, deduped[0].t, deduped[-1].t)
        if raw.get("_window_start") and raw.get("_window_end"):
            if not _series_covers(deduped, window_start, window_end):
                raise PermanentFetchError(
                    "CO-OPS currents: predictions do not cover the requested window"
                )
        return CurrentPayload(
            station_id=station,
            points=deduped,
            observed_at=max(p.t for p in deduped),
            window_start=window_start,
            window_end=window_end,
            depth_ft=depth,
            bin_id=chosen_bin,
            dropped_points=dropped,
            notes=notes,
        )


def _series_covers(points: list[CurrentPoint], start: datetime, end: datetime) -> bool:
    """True when at least one prediction falls on a UTC date inside [start, end)."""
    if end <= start:
        return False
    last = (end - timedelta(microseconds=1)).astimezone(timezone.utc).date()
    first = start.astimezone(timezone.utc).date()
    requested = {first}
    day = first
    while day < last:
        day = day.fromordinal(day.toordinal() + 1)
        requested.add(day)
    return any(point.t.astimezone(timezone.utc).date() in requested for point in points)


def _optional_window(
    raw: dict[str, Any],
    fallback_start: datetime,
    fallback_end: datetime,
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Attach the requested window when the fetch path recorded it."""
    ws = raw.get("_window_start")
    we = raw.get("_window_end")
    if not ws or not we:
        return fallback_start, fallback_end
    try:
        return _as_utc(datetime.fromisoformat(str(ws))), _as_utc(datetime.fromisoformat(str(we)))
    except ValueError as exc:
        raise PermanentFetchError("CO-OPS: bad window timestamp") from exc


def _parse_current_row(row: Any) -> Optional[CurrentPoint]:
    if not isinstance(row, dict):
        return None
    kind = str(row.get("Type") or row.get("type") or "").strip().lower()
    if kind not in {"slack", "flood", "ebb"}:
        return None
    when_raw = row.get("Time") or row.get("t")
    if not when_raw:
        return None
    try:
        when = _parse_coops_time(str(when_raw))
    except PermanentFetchError:
        return None
    # Missing speed must stay missing. Never coerce it to 0 (that looks like slack).
    if row.get("Velocity_Major") is None and row.get("v") is None:
        return None
    speed = parse_float_or_none(row.get("Velocity_Major") if row.get("Velocity_Major") is not None else row.get("v"))
    if speed is None or abs(speed) > _CURRENT_ABS_MAX_KT:
        return None
    depth = parse_float_or_none(row.get("Depth"))
    if depth is not None and (depth < 0 or depth > 400):
        depth = None
    bin_raw = row.get("Bin")
    bin_id = str(bin_raw).strip() if bin_raw is not None and str(bin_raw).strip() else None
    return CurrentPoint(
        t=when,
        velocity_kt=speed,
        type=kind,
        depth_ft=depth,
        bin_id=bin_id,
    )


def _select_bin(points: list[CurrentPoint]) -> tuple[Optional[str], Optional[float]]:
    """Keep a single bin. Averaging bins can invent a false slack."""
    bins: dict[Optional[str], list[CurrentPoint]] = {}
    for point in points:
        bins.setdefault(point.bin_id, []).append(point)
    if len(bins) == 1:
        only = next(iter(bins))
        depth = next((p.depth_ft for p in bins[only] if p.depth_ft is not None), None)
        return only, depth

    def sort_key(item: tuple[Optional[str], list[CurrentPoint]]) -> tuple[int, float, str]:
        bin_id, rows = item
        depth = next((p.depth_ft for p in rows if p.depth_ft is not None), 1e9)
        return (-len(rows), depth if depth is not None else 1e9, bin_id or "")

    bin_id, rows = sorted(bins.items(), key=sort_key)[0]
    depth = next((p.depth_ft for p in rows if p.depth_ft is not None), None)
    return bin_id, depth
