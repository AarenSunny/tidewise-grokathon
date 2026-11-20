"""EPA Envirofacts hourly UV by ZIP. Do NOT use NASA POWER UV_INDEX (all -999)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from backend.adapters.base import PermanentFetchError, SourceAdapter, TransientFetchError
from backend.models.spots import Spot
from backend.validation import parse_float_or_none

UA = os.getenv("NWS_USER_AGENT", "TideWise/0.1 (https://github.com/AarenSunny/tidewise-grokathon)")
EPA_URL = "https://data.epa.gov/efservice/getEnvirofactsUVHOURLY/ZIP/{zip}/JSON"

# Rough ZIP by county/spot cluster
DEFAULT_ZIP = "94121"


class UvPayload(BaseModel):
    zip_code: str
    uv_index: Optional[float] = None
    observed_at: Optional[datetime] = None
    samples: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EpaUvAdapter(SourceAdapter):
    name = "epa_uv"
    ttl = timedelta(minutes=30)
    max_age = timedelta(hours=6)
    max_stale_age = timedelta(hours=12)
    timeout_s = 10.0
    payload_model = UvPayload

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        z = self._zip_for_spot(spot)
        hour = start.astimezone(timezone.utc).strftime("%Y%m%d%H")
        return f"{self.name}:{z}:{hour}"

    def _zip_for_spot(self, spot: Spot) -> str:
        # Minimal mapping; extend via config later
        if spot.lat < 37.55:
            return "94019"  # HMB area
        if spot.lat < 37.7:
            return "94044"  # Pacifica
        return DEFAULT_ZIP

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        z = self._zip_for_spot(spot)
        url = EPA_URL.format(zip=z)
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers={"User-Agent": UA},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise TransientFetchError(f"EPA UV HTTP {resp.status_code}")
            if resp.status_code >= 400:
                raise PermanentFetchError(f"EPA UV HTTP {resp.status_code}")
            data = resp.json()
            return {"zip": z, "rows": data}

    def _validate(self, raw: Any) -> UvPayload:
        rows = raw.get("rows") or []
        if not isinstance(rows, list) or not rows:
            raise PermanentFetchError("EPA UV: empty")
        samples = []
        best = None
        for row in rows:
            uv = parse_float_or_none(row.get("UV_VALUE"))
            samples.append({"date_time": row.get("DATE_TIME"), "uv": uv})
            if uv is not None:
                best = uv if best is None else max(best, uv)
        return UvPayload(
            zip_code=str(raw.get("zip")),
            uv_index=best,
            observed_at=datetime.now(timezone.utc),
            samples=samples,
            notes=["source=epa_envirofacts", "not_nasa_power"],
        )
