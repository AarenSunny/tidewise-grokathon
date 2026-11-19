"""CoastWatch ERDDAP adapters: VIIRS chlorophyll-a and MUR SST.

Fallback chain when primary host returns 404/503:
  1. coastwatch.pfeg.noaa.gov primary dataset
  2. coastwatch.noaa.gov same dataset
  3. Alternate dataset IDs (nesdisVHNchlaDaily / ncdcOisst21NrtAgg)
Never invent bloom/SST values; down + null ⇒ cannot_confirm for scorers.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field

from backend.adapters.base import PermanentFetchError, SourceAdapter, TransientFetchError
from backend.models.spots import Spot
from backend.validation import parse_float_or_none

UA = os.getenv("NWS_USER_AGENT", "TideWise/0.1 (https://github.com/AarenSunny/tidewise-grokathon)")

ERDDAP_HOSTS = [
    "https://coastwatch.pfeg.noaa.gov/erddap",
    "https://coastwatch.noaa.gov/erddap",
]

# Observation older than this ⇒ stale flag True (also base max_age)
CHL_STALE_DAYS = 10
SST_STALE_DAYS = 3


class ChlPayload(BaseModel):
    chla_mg_m3: Optional[float] = None
    observed_at: Optional[datetime] = None
    stale: bool = True  # default True so missing never looks fresh
    dataset_id: Optional[str] = None
    host: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    notes: list[str] = Field(default_factory=list)


class SstPayload(BaseModel):
    sst_c: Optional[float] = None
    observed_at: Optional[datetime] = None
    stale: bool = True
    dataset_id: Optional[str] = None
    host: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    notes: list[str] = Field(default_factory=list)


def _parse_erddap_time(token: str) -> datetime:
    # e.g. 2026-11-09T00:00:00Z
    t = token.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _bbox(spot: Spot, pad: float = 0.05) -> tuple[float, float, float, float]:
    return (spot.lat - pad, spot.lat + pad, spot.lon - pad, spot.lon + pad)


def _table_mean(rows: list[list[Any]], value_idx: int) -> Optional[float]:
    vals = []
    for row in rows:
        if value_idx >= len(row):
            continue
        v = parse_float_or_none(row[value_idx])
        if v is not None:
            vals.append(v)
    if not vals:
        return None
    return sum(vals) / len(vals)


class ErddapChlAdapter(SourceAdapter):
    """VIIRS chlorophyll-a via CoastWatch ERDDAP with mirror/dataset fallback."""

    name = "erddap_chl"
    ttl = timedelta(hours=24)
    max_age = timedelta(days=CHL_STALE_DAYS)
    max_stale_age = timedelta(days=14)
    timeout_s = 10.0
    overall_deadline_s = 18.0
    max_retries = 2
    payload_model = ChlPayload
    safety_critical = False  # stale chl → stale status; scorers must cannot_confirm bloom if missing

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        # Quantize to 0.1° so nearby requests share cache
        lat_q = round(spot.lat, 1)
        lon_q = round(spot.lon, 1)
        return f"{self.name}:{lat_q}:{lon_q}"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        lat0, lat1, lon0, lon1 = _bbox(spot)
        # (host, dataset, var, query_suffix) — altitude dim required for erdVHNchla*
        attempts = []
        for host in ERDDAP_HOSTS:
            attempts.append(
                (
                    host,
                    "erdVHNchla8day",
                    "chla",
                    f"chla[(last)][(0.0)][({lat0}):1:({lat1})][({lon0}):1:({lon1})]",
                )
            )
            attempts.append(
                (
                    host,
                    "erdVHNchla3day",
                    "chla",
                    f"chla[(last)][(0.0)][({lat0}):1:({lat1})][({lon0}):1:({lon1})]",
                )
            )
            attempts.append(
                (
                    host,
                    "nesdisVHNchlaDaily",
                    "chlor_a",
                    f"chlor_a[(last)][({lat0}):1:({lat1})][({lon0}):1:({lon1})]",
                )
            )

        errors: list[str] = []
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers={"User-Agent": UA},
            follow_redirects=True,
        ) as client:
            for host, dataset, var, q in attempts:
                url = f"{host}/griddap/{dataset}.json?{q}"
                try:
                    resp = await client.get(url)
                    if resp.status_code in {404, 503, 502, 500}:
                        errors.append(f"{host}/{dataset}:{resp.status_code}")
                        continue
                    if resp.status_code == 429:
                        raise TransientFetchError("ERDDAP chl 429")
                    if resp.status_code >= 400:
                        errors.append(f"{host}/{dataset}:{resp.status_code}")
                        continue
                    data = resp.json()
                    data["_host"] = host
                    data["_dataset_id"] = dataset
                    data["_var"] = var
                    return data
                except httpx.TimeoutException as exc:
                    errors.append(f"{host}/{dataset}:timeout")
                    continue
                except httpx.TransportError as exc:
                    errors.append(f"{host}/{dataset}:{type(exc).__name__}")
                    continue
        raise TransientFetchError(f"ERDDAP chl all mirrors failed: {errors[:6]}")

    def _validate(self, raw: Any) -> ChlPayload:
        if not isinstance(raw, dict):
            raise PermanentFetchError("ERDDAP chl: expected dict")
        table = raw.get("table") or {}
        cols = table.get("columnNames") or []
        rows = table.get("rows") or []
        if not cols or not rows:
            # Honest empty — no invented bloom
            return ChlPayload(
                chla_mg_m3=None,
                observed_at=None,
                stale=True,
                dataset_id=raw.get("_dataset_id"),
                host=raw.get("_host"),
                notes=["empty_table"],
            )
        try:
            time_i = cols.index("time")
        except ValueError as exc:
            raise PermanentFetchError("ERDDAP chl: no time column") from exc
        var = raw.get("_var") or "chla"
        try:
            val_i = cols.index(var)
        except ValueError:
            # try common aliases
            for cand in ("chla", "chlor_a", "chlorophyll"):
                if cand in cols:
                    val_i = cols.index(cand)
                    break
            else:
                raise PermanentFetchError(f"ERDDAP chl: no value column in {cols}")

        mean_v = _table_mean(rows, val_i)
        observed = _parse_erddap_time(str(rows[0][time_i]))
        now = datetime.now(timezone.utc)
        age = now - observed
        stale = age > timedelta(days=CHL_STALE_DAYS)
        lat = lon = None
        if "latitude" in cols and "longitude" in cols:
            li, loi = cols.index("latitude"), cols.index("longitude")
            lat = parse_float_or_none(rows[0][li])
            lon = parse_float_or_none(rows[0][loi])
        return ChlPayload(
            chla_mg_m3=mean_v,
            observed_at=observed,
            stale=stale or mean_v is None,
            dataset_id=raw.get("_dataset_id"),
            host=raw.get("_host"),
            lat=lat,
            lon=lon,
            notes=[f"age_days={age.total_seconds()/86400:.1f}"],
        )


class ErddapSstAdapter(SourceAdapter):
    """MUR SST via CoastWatch ERDDAP with OISST NRT fallback."""

    name = "erddap_sst"
    ttl = timedelta(hours=24)
    max_age = timedelta(days=SST_STALE_DAYS)
    max_stale_age = timedelta(days=7)
    timeout_s = 10.0
    overall_deadline_s = 18.0
    max_retries = 2
    payload_model = SstPayload

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        lat_q = round(spot.lat, 1)
        lon_q = round(spot.lon, 1)
        return f"{self.name}:{lat_q}:{lon_q}"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        lat0, lat1, lon0, lon1 = _bbox(spot, pad=0.05)
        attempts = []
        for host in ERDDAP_HOSTS:
            attempts.append(
                (
                    host,
                    "jplMURSST41",
                    "analysed_sst",
                    f"analysed_sst[(last)][({lat0}):1:({lat1})][({lon0}):1:({lon1})]",
                )
            )
            # OISST NRT has altitude dim
            attempts.append(
                (
                    host,
                    "ncdcOisst21NrtAgg",
                    "sst",
                    f"sst[(last)][(0.0)][({spot.lat}):1:({spot.lat})][({spot.lon}):1:({spot.lon})]",
                )
            )

        errors: list[str] = []
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers={"User-Agent": UA},
            follow_redirects=True,
        ) as client:
            for host, dataset, var, q in attempts:
                url = f"{host}/griddap/{dataset}.json?{q}"
                try:
                    resp = await client.get(url)
                    if resp.status_code in {404, 503, 502, 500}:
                        errors.append(f"{host}/{dataset}:{resp.status_code}")
                        continue
                    if resp.status_code == 429:
                        raise TransientFetchError("ERDDAP sst 429")
                    if resp.status_code >= 400:
                        errors.append(f"{host}/{dataset}:{resp.status_code}")
                        continue
                    data = resp.json()
                    data["_host"] = host
                    data["_dataset_id"] = dataset
                    data["_var"] = var
                    return data
                except httpx.TimeoutException:
                    errors.append(f"{host}/{dataset}:timeout")
                    continue
                except httpx.TransportError as exc:
                    errors.append(f"{host}/{dataset}:{type(exc).__name__}")
                    continue
        raise TransientFetchError(f"ERDDAP sst all mirrors failed: {errors[:6]}")

    def _validate(self, raw: Any) -> SstPayload:
        if not isinstance(raw, dict):
            raise PermanentFetchError("ERDDAP sst: expected dict")
        table = raw.get("table") or {}
        cols = table.get("columnNames") or []
        rows = table.get("rows") or []
        if not cols or not rows:
            return SstPayload(
                sst_c=None,
                observed_at=None,
                stale=True,
                dataset_id=raw.get("_dataset_id"),
                host=raw.get("_host"),
                notes=["empty_table"],
            )
        time_i = cols.index("time")
        var = raw.get("_var") or "analysed_sst"
        if var not in cols:
            for cand in ("analysed_sst", "sst"):
                if cand in cols:
                    var = cand
                    break
            else:
                raise PermanentFetchError(f"ERDDAP sst: no value col in {cols}")
        val_i = cols.index(var)
        mean_v = _table_mean(rows, val_i)
        # SST range check °C
        if mean_v is not None and (mean_v < -2 or mean_v > 40):
            mean_v = None
        observed = _parse_erddap_time(str(rows[0][time_i]))
        now = datetime.now(timezone.utc)
        age = now - observed
        stale = age > timedelta(days=SST_STALE_DAYS) or mean_v is None
        return SstPayload(
            sst_c=mean_v,
            observed_at=observed,
            stale=stale,
            dataset_id=raw.get("_dataset_id"),
            host=raw.get("_host"),
            notes=[f"age_days={age.total_seconds()/86400:.1f}"],
        )
