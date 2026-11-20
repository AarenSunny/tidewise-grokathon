"""C-HARM Pseudo-nitzschia / domoic acid probability (optional).

Research round 2: ERDDAP IDs 404 afternoon of 2026-11-19. Adapter tries hosts
and returns down with null probabilities — never invents bloom values.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from backend.adapters.base import PermanentFetchError, SourceAdapter, TransientFetchError
from backend.adapters.erddap import ERDDAP_HOSTS
from backend.models.spots import Spot
from backend.validation import parse_float_or_none

UA = os.getenv("NWS_USER_AGENT", "TideWise/0.1 (https://github.com/AarenSunny/tidewise-grokathon)")

DATASETS = ["wvcharmV3_0day", "wvcharmV3_0day_LonPM180"]


class CharmPayload(BaseModel):
    probability: Optional[float] = None
    observed_at: Optional[datetime] = None
    stale: bool = True
    dataset_id: Optional[str] = None
    host: Optional[str] = None
    available: bool = False
    notes: list[str] = Field(default_factory=list)


class CharmAdapter(SourceAdapter):
    name = "erddap_charm"
    ttl = timedelta(hours=6)
    max_age = timedelta(days=3)
    max_stale_age = timedelta(days=5)
    timeout_s = 8.0
    overall_deadline_s = 14.0
    max_retries = 1
    payload_model = CharmPayload
    safety_critical = True  # missing ⇒ cannot_confirm for bloom gates

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        return f"{self.name}:{round(spot.lat, 1)}:{round(spot.lon, 1)}"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        # C-HARM lon often 0–360
        lon360 = spot.lon if spot.lon >= 0 else spot.lon + 360.0
        lat0, lat1 = spot.lat - 0.05, spot.lat + 0.05
        errors: list[str] = []
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers={"User-Agent": UA},
            follow_redirects=True,
        ) as client:
            for host in ERDDAP_HOSTS:
                for ds in DATASETS:
                    # Try a couple of common variable names
                    for var in ("PNprob", "pDA", "Pseudo_nitzschia_Probability"):
                        if "LonPM180" in ds:
                            lon0, lon1 = spot.lon - 0.05, spot.lon + 0.05
                        else:
                            lon0, lon1 = lon360 - 0.05, lon360 + 0.05
                        q = f"{var}[(last)][({lat0}):1:({lat1})][({lon0}):1:({lon1})]"
                        url = f"{host}/griddap/{ds}.json?{q}"
                        try:
                            resp = await client.get(url)
                            if resp.status_code in {404, 503, 502}:
                                errors.append(f"{ds}:{resp.status_code}")
                                continue
                            if resp.status_code >= 400:
                                errors.append(f"{ds}:{resp.status_code}")
                                continue
                            data = resp.json()
                            data["_host"] = host
                            data["_dataset_id"] = ds
                            data["_var"] = var
                            return data
                        except httpx.HTTPError:
                            errors.append(f"{ds}:http_error")
                            continue
        raise TransientFetchError(f"C-HARM unavailable: {errors[:8]}")

    def _validate(self, raw: Any) -> CharmPayload:
        if not isinstance(raw, dict):
            raise PermanentFetchError("C-HARM: expected dict")
        table = raw.get("table") or {}
        cols = table.get("columnNames") or []
        rows = table.get("rows") or []
        if not rows or not cols:
            return CharmPayload(
                available=False,
                stale=True,
                notes=["empty_or_missing", "cannot_confirm_bloom"],
                dataset_id=raw.get("_dataset_id"),
                host=raw.get("_host"),
            )
        time_i = cols.index("time") if "time" in cols else 0
        var = raw.get("_var")
        val_i = cols.index(var) if var in cols else len(cols) - 1
        vals = [parse_float_or_none(r[val_i]) for r in rows if val_i < len(r)]
        vals = [v for v in vals if v is not None]
        mean = sum(vals) / len(vals) if vals else None
        from backend.adapters.erddap import _parse_erddap_time

        observed = _parse_erddap_time(str(rows[0][time_i]))
        age = datetime.now(timezone.utc) - observed
        return CharmPayload(
            probability=mean,
            observed_at=observed,
            stale=age > timedelta(days=3) or mean is None,
            available=mean is not None,
            dataset_id=raw.get("_dataset_id"),
            host=raw.get("_host"),
            notes=[f"age_days={age.total_seconds()/86400:.1f}"],
        )
