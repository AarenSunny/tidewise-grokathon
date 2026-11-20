"""NDBC realtime2 buoy observations.

Wind is converted from the file's m/s to knots. Water temperature stays °C.
Wave height stays meters (the realtime2 unit and the feature-model unit).
`MM` and column-specific 99/999 sentinels become None — never zero — so a
missing wind cannot pass a gate as calm. A row with no wind, waves, or water
temperature is a hard failure. Stale files stay attached to their real
timestamp so the base class can mark them down.
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
from backend.validation import is_missing_ndbc, parse_float_or_none

DEFAULT_UA = "TideWise/0.1 (https://github.com/AarenSunny/tidewise-grokathon)"
NDBC_BASE = "https://www.ndbc.noaa.gov"
# Match backend.validation.ms_to_knots (1.94384) once that helper is on main.
MS_TO_KT = 1.94384
_STATION_RE = re.compile(r"^[A-Za-z0-9]{4,10}$")
_FUTURE_SKEW = timedelta(minutes=30)
_DIR_MISSING = {"", "MM", "mm", "999", "999.0", "9999", "9999.0"}
_SCALAR_MISSING = _DIR_MISSING | {"99", "99.0", "99.00"}


def user_agent() -> str:
    raw = os.getenv("NWS_USER_AGENT", "").strip()
    if not raw or "@" in raw:
        return DEFAULT_UA
    return raw


def _window_token(start: datetime, end: datetime) -> str:
    """UTC hour span. Microseconds inside an hour do not change the key."""
    try:
        start_utc = start.astimezone(timezone.utc) if start.tzinfo else start.replace(tzinfo=timezone.utc)
        end_utc = end.astimezone(timezone.utc) if end.tzinfo else end.replace(tzinfo=timezone.utc)
    except (ValueError, OSError):
        return "bad"
    start_hour = start_utc.replace(minute=0, second=0, microsecond=0)
    end_hour = end_utc.replace(minute=0, second=0, microsecond=0)
    return f"{start_hour:%Y%m%d%H}:{end_hour:%Y%m%d%H}"


def parse_ndbc_value(token: str) -> Optional[float]:
    """Public helper for unit tests (MM / 999). Direction 99 is not a sentinel."""
    if is_missing_ndbc(token):
        return None
    return parse_float_or_none(token)


class NdbcObs(BaseModel):
    station_id: str
    observed_at: datetime
    wdir_deg: Optional[float] = None
    wspd_ms: Optional[float] = None
    wspd_kt: Optional[float] = None
    gst_ms: Optional[float] = None
    gst_kt: Optional[float] = None
    wvht_m: Optional[float] = None
    dpd_s: Optional[float] = None
    wtmp_c: Optional[float] = None
    raw_row: dict[str, str] = Field(default_factory=dict)
    stale: bool = False
    fallback_used: Optional[str] = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("observed_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return require_aware(v).astimezone(timezone.utc)


class NdbcAdapter(SourceAdapter):
    name = "ndbc_buoy"
    ttl = timedelta(minutes=15)
    max_age = timedelta(hours=3)
    max_stale_age = timedelta(hours=3)
    timeout_s = 8.0
    overall_deadline_s = 12.0
    # Wind and waves feed safety gates. Older than max_age must be down.
    safety_critical = True
    payload_model = NdbcObs

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.base_url = os.getenv("NDBC_BASE_URL", NDBC_BASE).strip().rstrip("/") or NDBC_BASE

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        """Station ids plus the UTC hour window.

        A spot with no buoy gets its own key (never 46026) so fetch() cannot
        serve another station from cache. The failure itself is not stored.
        """
        window = _window_token(start, end)
        if not spot.buoy_ids:
            return f"{self.name}:missing:{spot.id}:{window}"
        return f"{self.name}:{','.join(spot.buoy_ids)}:{window}"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        if not spot.buoy_ids:
            raise PermanentFetchError("NDBC: cannot_confirm — spot has no buoy_ids")
        failures: list[str] = []
        saw_transient = False
        stale_rows: list[tuple[datetime, int, str, str]] = []
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers={"User-Agent": user_agent(), "Accept": "text/plain"},
            follow_redirects=True,
        ) as client:
            for index, station in enumerate(spot.buoy_ids):
                if not _STATION_RE.fullmatch(station):
                    failures.append(f"{station}:invalid id")
                    continue
                try:
                    text = await self._download(client, station)
                except TransientFetchError:
                    saw_transient = True
                    failures.append(f"{station}:transient")
                    continue
                except PermanentFetchError as exc:
                    failures.append(f"{station}:{exc}")
                    continue
                try:
                    obs = _parse_realtime(text, station, max_age=self.max_age)
                except PermanentFetchError as exc:
                    failures.append(f"{station}:{exc}")
                    continue
                now = datetime.now(timezone.utc)
                if obs.observed_at > now + _FUTURE_SKEW:
                    failures.append(f"{station}:timestamp in the future")
                    continue
                if now - obs.observed_at <= self.max_age:
                    return _raw(station, text, index)
                stale_rows.append((obs.observed_at, index, station, text))

        if stale_rows:
            stale_rows.sort(key=lambda item: item[0], reverse=True)
            _, index, station, text = stale_rows[0]
            return _raw(station, text, index)
        if saw_transient:
            raise TransientFetchError("NDBC: upstream error")
        raise PermanentFetchError("NDBC: no usable buoy observation")

    async def _download(self, client: httpx.AsyncClient, station: str) -> str:
        url = f"{self.base_url}/data/realtime2/{station}.txt"
        try:
            resp = await client.get(url)
        except httpx.TimeoutException:
            raise TransientFetchError("NDBC: timeout") from None
        except httpx.TransportError:
            raise TransientFetchError("NDBC: connection failed") from None
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientFetchError(f"NDBC: HTTP {resp.status_code}")
        if resp.status_code != 200:
            raise PermanentFetchError(f"NDBC: HTTP {resp.status_code}")
        return resp.text

    def _validate(self, raw: Any) -> NdbcObs:
        if not isinstance(raw, dict):
            raise PermanentFetchError("NDBC: expected dict")
        station = str(raw.get("station_id") or "")
        if not _STATION_RE.fullmatch(station):
            raise PermanentFetchError("NDBC: invalid station id")
        obs = _parse_realtime(str(raw.get("text") or ""), station, max_age=self.max_age)
        fallback = raw.get("_fallback_used")
        if fallback:
            obs.fallback_used = str(fallback)
            obs.notes = [*obs.notes, f"fallback_used={fallback}"]
        return obs


def _raw(station: str, text: str, index: int) -> dict[str, Any]:
    payload: dict[str, Any] = {"station_id": station, "text": text}
    if index > 0:
        payload["_fallback_used"] = f"buoy:{station}"
    return payload


def _parse_realtime(text: str, station_id: str, *, max_age: timedelta) -> NdbcObs:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    header: Optional[list[str]] = None
    data: Optional[list[str]] = None
    for line in lines:
        if line.startswith("#"):
            if header is None:
                header = line.lstrip("#").split()
            continue
        tokens = line.split()
        if tokens and tokens[0].isdigit():
            data = tokens
            break
    if not header or not data:
        raise PermanentFetchError("NDBC: no data row")
    width = min(len(header), len(data))
    row = {header[i]: data[i] for i in range(width)}

    try:
        year = int(row["YY"])
        if year < 100:
            year += 2000 if year < 70 else 1900
        observed = datetime(
            year,
            int(row["MM"]),
            int(row["DD"]),
            int(row["hh"]),
            int(row["mm"]),
            tzinfo=timezone.utc,
        )
    except (KeyError, ValueError) as exc:
        raise PermanentFetchError("NDBC: bad timestamp") from exc

    now = datetime.now(timezone.utc)
    if observed > now + _FUTURE_SKEW:
        raise PermanentFetchError("NDBC: timestamp in the future")

    wdir = _column(row, "WDIR", 0, 360, missing=_DIR_MISSING)
    wspd = _column(row, "WSPD", 0, 75, missing=_SCALAR_MISSING)
    gst = _column(row, "GST", 0, 100, missing=_SCALAR_MISSING)
    wvht = _column(row, "WVHT", 0, 25, missing=_SCALAR_MISSING)
    dpd = _column(row, "DPD", 0.1, 40, missing=_SCALAR_MISSING)
    wtmp = _column(row, "WTMP", -2, 40, missing=_SCALAR_MISSING)

    notes: list[str] = []
    if wspd is not None and gst is not None and gst + 0.2 < wspd:
        gst = None
        notes.append("gust_below_wind_discarded")
    if wspd is None and wvht is None and wtmp is None:
        raise PermanentFetchError("NDBC: no usable wind, wave, or water-temperature value")

    age = now - observed
    stale = age > max_age
    notes.append(f"age_hours={age.total_seconds() / 3600:.1f}")
    return NdbcObs(
        station_id=station_id,
        observed_at=observed,
        wdir_deg=wdir,
        wspd_ms=wspd,
        wspd_kt=None if wspd is None else wspd * MS_TO_KT,
        gst_ms=gst,
        gst_kt=None if gst is None else gst * MS_TO_KT,
        wvht_m=wvht,
        dpd_s=dpd,
        wtmp_c=wtmp,
        raw_row=row,
        stale=stale,
        notes=notes,
    )


def _column(
    row: dict[str, str],
    name: str,
    lo: float,
    hi: float,
    *,
    missing: set[str],
) -> Optional[float]:
    if name not in row:
        return None
    token = row[name].strip()
    if token in missing or token.upper() == "MM":
        return None
    try:
        value = float(token)
    except ValueError:
        return None
    if value != value or value in {float("inf"), float("-inf")}:
        return None
    if value < lo or value > hi:
        return None
    return value
