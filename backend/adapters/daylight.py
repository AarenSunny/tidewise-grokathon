"""Optional daylight cross-check via sunrise-sunset.org (research-verified).

Offline astral calc remains primary in FeatureEngine (owned elsewhere).
This adapter is optional — never required for scoring gates.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from backend.adapters.base import PermanentFetchError, SourceAdapter, TransientFetchError
from backend.models.spots import Spot

UA = os.getenv("NWS_USER_AGENT", "TideWise/0.1 (https://github.com/AarenSunny/tidewise-grokathon)")
SUNRISE_URL = "https://api.sunrise-sunset.org/json"


class DaylightPayload(BaseModel):
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None
    civil_twilight_begin: Optional[datetime] = None
    civil_twilight_end: Optional[datetime] = None
    observed_at: Optional[datetime] = None
    source: str = "sunrise-sunset.org"
    notes: list[str] = Field(default_factory=list)


class DaylightAdapter(SourceAdapter):
    name = "daylight_sunrise_api"
    ttl = timedelta(hours=12)
    max_age = timedelta(hours=36)
    max_stale_age = timedelta(days=2)
    timeout_s = 6.0
    payload_model = DaylightPayload

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        day = start.astimezone(timezone.utc).strftime("%Y%m%d")
        return f"{self.name}:{round(spot.lat, 2)}:{round(spot.lon, 2)}:{day}"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        day = start.astimezone(timezone.utc).strftime("%Y-%m-%d")
        params = {
            "lat": spot.lat,
            "lng": spot.lon,
            "date": day,
            "formatted": 0,
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=3.0),
            headers={"User-Agent": UA},
            follow_redirects=True,
        ) as client:
            resp = await client.get(SUNRISE_URL, params=params)
            if resp.status_code >= 500 or resp.status_code == 429:
                raise TransientFetchError(f"sunrise-sunset HTTP {resp.status_code}")
            if resp.status_code >= 400:
                raise PermanentFetchError(f"sunrise-sunset HTTP {resp.status_code}")
            return resp.json()

    def _validate(self, raw: Any) -> DaylightPayload:
        if not isinstance(raw, dict) or raw.get("status") != "OK":
            raise PermanentFetchError(f"sunrise-sunset bad status: {raw}")
        res = raw.get("results") or {}

        def parse(key: str) -> Optional[datetime]:
            v = res.get(key)
            if not v:
                return None
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        sunrise = parse("sunrise")
        return DaylightPayload(
            sunrise=sunrise,
            sunset=parse("sunset"),
            civil_twilight_begin=parse("civil_twilight_begin"),
            civil_twilight_end=parse("civil_twilight_end"),
            observed_at=sunrise,
            notes=["optional_cross_check", "feature_engine_owns_primary_daylight"],
        )
