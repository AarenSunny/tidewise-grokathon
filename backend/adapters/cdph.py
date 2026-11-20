"""CDPH shellfish / biotoxin advisories via ArcGIS FeatureServer (not HTML)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from backend.adapters.base import PermanentFetchError, SourceAdapter, TransientFetchError
from backend.models.spots import Spot

UA = os.getenv("NWS_USER_AGENT", "TideWise/0.1 (https://github.com/AarenSunny/tidewise-grokathon)")

SPECIAL_ADVISORY_URL = (
    "https://services2.arcgis.com/wi1yEacfYjH5viqb/arcgis/rest/services/"
    "All_Bivalve_Shellfish_Health_Advisory_Special_Advisory/FeatureServer/3/query"
)
COUNTY_SYMBOLS_URL = (
    "https://services2.arcgis.com/wi1yEacfYjH5viqb/arcgis/rest/services/"
    "Health_Advisory_Symbols_(Red)/FeatureServer/0/query"
)

REGION_COUNTIES = {
    "San Mateo County",
    "San Francisco County",
    "Marin County",
    "Sonoma County",
    "Contra Costa County",
    "Alameda County",
}


class ShellfishAdvisory(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    county: Optional[str] = None
    visible: Optional[bool] = None
    date: Optional[str] = None


class ShellfishPayload(BaseModel):
    special_advisories: list[ShellfishAdvisory] = Field(default_factory=list)
    county_symbols: list[ShellfishAdvisory] = Field(default_factory=list)
    region_counties_with_symbol: list[str] = Field(default_factory=list)
    any_region_advisory: bool = False
    observed_at: Optional[datetime] = None
    notes: list[str] = Field(default_factory=list)


class CdphShellfishAdapter(SourceAdapter):
    """ArcGIS-backed shellfish advisories. Safety-critical: short max stale."""

    name = "cdph_shellfish"
    ttl = timedelta(minutes=10)
    max_age = timedelta(hours=6)
    max_stale_age = timedelta(hours=6)
    safety_critical = True
    timeout_s = 8.0
    overall_deadline_s = 12.0
    payload_model = ShellfishPayload

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        return f"{self.name}:region"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "false",
            "f": "json",
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers={"User-Agent": UA},
            follow_redirects=True,
        ) as client:
            special = await client.get(SPECIAL_ADVISORY_URL, params=params)
            counties = await client.get(COUNTY_SYMBOLS_URL, params=params)
            for label, resp in (("special", special), ("counties", counties)):
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise TransientFetchError(f"CDPH ArcGIS {label} HTTP {resp.status_code}")
                if resp.status_code >= 400:
                    raise PermanentFetchError(f"CDPH ArcGIS {label} HTTP {resp.status_code}")
            return {
                "special": special.json(),
                "counties": counties.json(),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

    def _validate(self, raw: Any) -> ShellfishPayload:
        if not isinstance(raw, dict):
            raise PermanentFetchError("CDPH: expected dict")
        special_feats = (raw.get("special") or {}).get("features") or []
        county_feats = (raw.get("counties") or {}).get("features") or []
        specials: list[ShellfishAdvisory] = []
        for f in special_feats:
            attrs = f.get("attributes") or {}
            specials.append(
                ShellfishAdvisory(
                    title=attrs.get("TITLE"),
                    description=attrs.get("DESCRIPTION"),
                    visible=bool(attrs.get("VISIBLE")) if attrs.get("VISIBLE") is not None else None,
                    date=str(attrs.get("DATE")) if attrs.get("DATE") is not None else None,
                )
            )
        counties: list[ShellfishAdvisory] = []
        region_hit: list[str] = []
        for f in county_feats:
            attrs = f.get("attributes") or {}
            name = attrs.get("County_Name") or attrs.get("COUNTY_NAME")
            if name and not str(name).endswith(" County") and f"{name} County" in REGION_COUNTIES:
                name = f"{name} County"
            adv = ShellfishAdvisory(county=name, title=name)
            counties.append(adv)
            if name in REGION_COUNTIES:
                region_hit.append(str(name))
        now = datetime.now(timezone.utc)
        any_adv = bool(region_hit) or any(s.visible for s in specials if s.visible is not None)
        return ShellfishPayload(
            special_advisories=specials,
            county_symbols=counties,
            region_counties_with_symbol=sorted(set(region_hit)),
            any_region_advisory=any_adv,
            observed_at=now,
            notes=["source=arcgis_featureserver", "html_not_used"],
        )
