"""NDBC buoy helper: MM sentinel parsing + stale row detection."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from backend.adapters.base import PermanentFetchError, SourceAdapter, TransientFetchError
from backend.models.spots import Spot
from backend.validation import in_range, is_missing_ndbc, parse_float_or_none

UA = os.getenv("NWS_USER_AGENT", "TideWise/0.1 (https://github.com/AarenSunny/tidewise-grokathon)")
NDBC_BASE = os.getenv("NDBC_BASE_URL", "https://www.ndbc.noaa.gov")


class NdbcObs(BaseModel):
    station_id: str
    observed_at: Optional[datetime] = None
    wdir_deg: Optional[float] = None
    wspd_ms: Optional[float] = None
    gst_ms: Optional[float] = None
    wvht_m: Optional[float] = None
    dpd_s: Optional[float] = None
    wtmp_c: Optional[float] = None
    raw_row: dict[str, str] = Field(default_factory=dict)
    stale: bool = False
    notes: list[str] = Field(default_factory=list)


class NdbcAdapter(SourceAdapter):
    name = "ndbc_buoy"
    ttl = timedelta(minutes=15)
    max_age = timedelta(hours=3)
    max_stale_age = timedelta(hours=12)
    timeout_s = 8.0
    payload_model = NdbcObs

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        sid = (spot.buoy_ids or ["46026"])[0]
        return f"{self.name}:{sid}"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        if not spot.buoy_ids:
            raise PermanentFetchError("NDBC: spot has no buoy_ids")
        station = spot.buoy_ids[0]
        url = f"{NDBC_BASE}/data/realtime2/{station}.txt"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers={"User-Agent": UA},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 500 or resp.status_code == 429:
                raise TransientFetchError(f"NDBC HTTP {resp.status_code}")
            if resp.status_code >= 400:
                raise PermanentFetchError(f"NDBC HTTP {resp.status_code}")
            return {"station_id": station, "text": resp.text}

    def _validate(self, raw: Any) -> NdbcObs:
        text = raw.get("text") or ""
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) < 3:
            raise PermanentFetchError("NDBC: too few lines")
        # Header: #YY MM DD hh mm ...
        header = lines[0].lstrip("#").split()
        # Find first data row (not units line)
        data_line = None
        for ln in lines[2:]:
            if ln.startswith("#"):
                continue
            data_line = ln
            break
        if data_line is None:
            raise PermanentFetchError("NDBC: no data row")
        parts = data_line.split()
        if len(parts) < len(header):
            # pad
            parts = parts + ["MM"] * (len(header) - len(parts))
        row = {header[i]: parts[i] for i in range(min(len(header), len(parts)))}

        def f(col: str, lo: float, hi: float) -> Optional[float]:
            if col not in row or is_missing_ndbc(row[col]):
                return None
            return in_range(parse_float_or_none(row[col]), lo, hi)

        try:
            observed = datetime(
                int(row["YY"]),
                int(row["MM"]),
                int(row["DD"]),
                int(row["hh"]),
                int(row["mm"]),
                tzinfo=timezone.utc,
            )
        except Exception as exc:  # noqa: BLE001
            raise PermanentFetchError(f"NDBC: bad timestamp {exc}") from exc

        age = datetime.now(timezone.utc) - observed
        stale = age > self.max_age
        return NdbcObs(
            station_id=str(raw["station_id"]),
            observed_at=observed,
            wdir_deg=f("WDIR", 0, 360),
            wspd_ms=f("WSPD", 0, 75),
            gst_ms=f("GST", 0, 100),
            wvht_m=f("WVHT", 0, 25),
            dpd_s=f("DPD", 0, 40),
            wtmp_c=f("WTMP", -2, 40),
            raw_row=row,
            stale=stale,
            notes=[f"age_hours={age.total_seconds()/3600:.1f}"],
        )


def parse_ndbc_value(token: str) -> Optional[float]:
    """Public helper for unit tests (MM / 99 / 999)."""
    if is_missing_ndbc(token):
        return None
    return parse_float_or_none(token)
