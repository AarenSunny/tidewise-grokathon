"""CDPH shellfish advisories.

The ArcGIS county-pin and special-advisory layers are not a live closure
status (no per-county/species field; pins are static). An error body or an
empty feature list must not be read as "no advisory". ``any_region_advisory``
stays None (unknown) unless a dated advisory explicitly covers the region.
``observed_at`` comes only from a timestamp in the payload (feature DATE or
layer lastEditDate), never from the fetch clock.

Review3 P3-1.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from backend.adapters.base import PermanentFetchError, SourceAdapter, TransientFetchError
from backend.models.common import SourceStatus
from backend.models.sources import SourceResult
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
    # None = unknown. False is a confirmed clear and must not be the default.
    any_region_advisory: Optional[bool] = None
    cannot_confirm: bool = True
    observed_at: Optional[datetime] = None
    notes: list[str] = Field(default_factory=list)


def _parse_data_time(value: Any) -> Optional[datetime]:
    """Parse an ArcGIS DATE / lastEditDate. Never substitutes the clock."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 10_000_000_000:  # epoch milliseconds
            seconds /= 1000.0
        if seconds <= 0:
            return None
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    text = str(value).strip()
    if text.isdigit():
        return _parse_data_time(int(text))
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _layer_edit_time(layer: Any) -> Optional[datetime]:
    if not isinstance(layer, dict):
        return None
    info = layer.get("editingInfo") if isinstance(layer.get("editingInfo"), dict) else {}
    for key in ("lastEditDate", "dataLastEditDate"):
        parsed = _parse_data_time(info.get(key))
        if parsed is not None:
            return parsed
        parsed = _parse_data_time(layer.get(key))
        if parsed is not None:
            return parsed
    return None


def _layer_failed(layer: Any) -> bool:
    """ArcGIS faults are HTTP 200 plus an ``error`` object and no features."""
    if not isinstance(layer, dict):
        return True
    if "error" in layer:
        return True
    if "features" not in layer:
        return True
    return False


class CdphShellfishAdapter(SourceAdapter):
    """ArcGIS shellfish layers. Error/empty/undated → down + cannot_confirm."""

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

    def _apply_freshness(self, result: SourceResult, now: datetime) -> SourceResult:
        result = super()._apply_freshness(result, now)
        data = result.data
        # Base leaves status=ok when observed_at is missing. That is fail-open.
        if isinstance(data, ShellfishPayload) and data.cannot_confirm:
            result.status = SourceStatus.down
            if "cannot_confirm" not in result.notes:
                result.notes = [*result.notes, "cannot_confirm"]
        elif result.observed_at is None and result.status == SourceStatus.ok:
            result.status = SourceStatus.down
            result.notes = [*result.notes, "cannot_confirm", "missing_observed_at"]
        return result

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
            verify=True,
        ) as client:
            special = await client.get(SPECIAL_ADVISORY_URL, params=params)
            counties = await client.get(COUNTY_SYMBOLS_URL, params=params)
            for label, resp in (("special", special), ("counties", counties)):
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise TransientFetchError(f"CDPH ArcGIS {label} HTTP {resp.status_code}")
                if resp.status_code >= 400:
                    raise PermanentFetchError(f"CDPH ArcGIS {label} HTTP {resp.status_code}")
            # Do not attach the fetch clock. Timestamps must come from the body.
            return {"special": special.json(), "counties": counties.json()}

    def _unconfirmed(
        self,
        *,
        specials: list[ShellfishAdvisory],
        counties: list[ShellfishAdvisory],
        region_hit: list[str],
        observed_at: Optional[datetime],
        notes: list[str],
    ) -> ShellfishPayload:
        return ShellfishPayload(
            special_advisories=specials,
            county_symbols=counties,
            region_counties_with_symbol=sorted(set(region_hit)),
            any_region_advisory=None,
            cannot_confirm=True,
            observed_at=observed_at,
            notes=[*notes, "cannot_confirm"],
        )

    def _validate(self, raw: Any) -> ShellfishPayload:
        if not isinstance(raw, dict):
            raise PermanentFetchError("CDPH: expected dict")
        special = raw.get("special") if isinstance(raw.get("special"), dict) else {}
        counties_layer = raw.get("counties") if isinstance(raw.get("counties"), dict) else {}
        observed_candidates = [
            t
            for t in (_layer_edit_time(special), _layer_edit_time(counties_layer))
            if t is not None
        ]
        layer_observed = max(observed_candidates) if observed_candidates else None

        if _layer_failed(special) or _layer_failed(counties_layer):
            return self._unconfirmed(
                specials=[],
                counties=[],
                region_hit=[],
                observed_at=layer_observed,
                notes=["arcgis_error_or_missing_features"],
            )

        special_feats = special.get("features") or []
        county_feats = counties_layer.get("features") or []
        if not special_feats and not county_feats:
            return self._unconfirmed(
                specials=[],
                counties=[],
                region_hit=[],
                observed_at=layer_observed,
                notes=["arcgis_empty_features"],
            )

        specials: list[ShellfishAdvisory] = []
        dated_region: list[datetime] = []
        for feat in special_feats:
            attrs = (feat or {}).get("attributes") or {}
            title = attrs.get("TITLE")
            description = attrs.get("DESCRIPTION")
            visible = bool(attrs.get("VISIBLE")) if attrs.get("VISIBLE") is not None else None
            feature_time = _parse_data_time(attrs.get("DATE"))
            specials.append(
                ShellfishAdvisory(
                    title=title,
                    description=description,
                    visible=visible,
                    date=feature_time.isoformat() if feature_time else None,
                )
            )
            text = f"{title or ''} {description or ''}"
            if feature_time is not None and visible and any(county in text for county in REGION_COUNTIES):
                dated_region.append(feature_time)

        counties: list[ShellfishAdvisory] = []
        region_hit: list[str] = []
        for feat in county_feats:
            attrs = (feat or {}).get("attributes") or {}
            name = attrs.get("County_Name") or attrs.get("COUNTY_NAME")
            if name and not str(name).endswith(" County") and f"{name} County" in REGION_COUNTIES:
                name = f"{name} County"
            counties.append(ShellfishAdvisory(county=name, title=name))
            if name in REGION_COUNTIES:
                region_hit.append(str(name))

        # County pins have no status or date. Presence is not a closure and
        # absence is not a clear (P3-1 / N1).
        if not dated_region:
            return self._unconfirmed(
                specials=specials,
                counties=counties,
                region_hit=region_hit,
                observed_at=layer_observed,
                notes=["arcgis_pins_are_not_a_dated_closure_status"],
            )

        observed_at = max(dated_region)
        return ShellfishPayload(
            special_advisories=specials,
            county_symbols=counties,
            region_counties_with_symbol=sorted(set(region_hit)),
            any_region_advisory=True,
            cannot_confirm=False,
            observed_at=observed_at,
            notes=["dated_region_advisory"],
        )
