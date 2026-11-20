"""NWS active alerts (api.weather.gov) for marine and beach hazards.

The active-alert feed is safety-critical. A failed, partial, or untimestamped
response is a hard failure — never an all-clear. Boolean flags are tri-state:

* True — a qualifying Actual alert intersects the requested window
* False — the relevant query succeeded and none do
* None — cannot confirm (marine zone not checked, or an alert has no end time)

Small-craft and gale/storm flags are False only when the spot's marine zone
was queried. Beach-hazard flags are False only when the point query succeeded.
Absence is never filled in as False.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, field_validator

from backend.adapters.base import PermanentFetchError, SourceAdapter, TransientFetchError
from backend.models.common import require_aware
from backend.models.spots import Spot

DEFAULT_BASE = "https://api.weather.gov"
DEFAULT_UA = "TideWise/0.1 (https://github.com/AarenSunny/tidewise-grokathon)"
_ZONE_RE = re.compile(r"^[A-Z]{3}[0-9]{3}$")

# Event names as published by api.weather.gov (matched case-insensitively).
_SMALL_CRAFT = {
    "small craft advisory",
    "small craft advisory for hazardous seas",
    "small craft advisory for winds",
    "small craft advisory for wind",
    "small craft advisory for rough bar",
    "brisk wind advisory",
}
_GALE = {
    "gale warning",
    "gale watch",
    "storm warning",
    "storm watch",
    "hurricane force wind warning",
    "hurricane force wind watch",
    "hurricane warning",
    "hurricane watch",
    "tropical storm warning",
    "tropical storm watch",
    "special marine warning",
    "hazardous seas warning",
    "hazardous seas watch",
}
_BEACH = {
    "beach hazards statement",
    "high surf advisory",
    "high surf warning",
    "rip current statement",
    "coastal flood advisory",
    "coastal flood warning",
    "coastal flood statement",
    "tsunami warning",
    "tsunami advisory",
    "tsunami watch",
}
_THUNDER = {
    "thunderstorm warning",
    "severe thunderstorm warning",
    "severe thunderstorm watch",
    "tornado warning",
    "tornado watch",
}


def user_agent() -> str:
    """NWS rejects anonymous clients. Identify the project without an email."""
    raw = os.getenv("NWS_USER_AGENT", "").strip()
    if not raw or "@" in raw:
        return DEFAULT_UA
    return raw


def _as_utc(dt: datetime) -> datetime:
    return require_aware(dt).astimezone(timezone.utc)


def _parse_time(token: Any) -> Optional[datetime]:
    if token is None or token == "":
        return None
    text = str(token).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise PermanentFetchError("NWS: unparseable alert time") from exc
    if parsed.tzinfo is None:
        raise PermanentFetchError("NWS: alert time is not timezone-aware")
    return parsed.astimezone(timezone.utc)


class NwsAlert(BaseModel):
    id: str
    event: str
    severity: Optional[str] = None
    urgency: Optional[str] = None
    certainty: Optional[str] = None
    headline: Optional[str] = None
    onset: Optional[datetime] = None
    ends: Optional[datetime] = None
    sent: Optional[datetime] = None
    zones: list[str] = Field(default_factory=list)
    intersects_window: Optional[bool] = None

    @field_validator("onset", "ends", "sent")
    @classmethod
    def _utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        return _as_utc(v)


class NwsAlertsPayload(BaseModel):
    observed_at: datetime
    alerts: list[NwsAlert] = Field(default_factory=list)
    # None means cannot confirm. False is a confirmed absence, not a guess.
    small_craft_advisory: Optional[bool] = None
    gale_warning: Optional[bool] = None
    beach_hazard: Optional[bool] = None
    thunderstorm: Optional[bool] = None
    any_hazard: Optional[bool] = None
    marine_zone: Optional[str] = None
    marine_zone_checked: bool = False
    point_checked: bool = False
    active_event_names: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("observed_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _as_utc(v)


class NwsAlertsAdapter(SourceAdapter):
    """Active NWS alerts for one spot: point geometry plus marine zone."""

    name = "nws_alerts"
    ttl = timedelta(minutes=10)
    max_age = timedelta(hours=2)
    # Do not serve a stale all-clear while the feed is down.
    max_stale_age = timedelta(0)
    timeout_s = 8.0
    overall_deadline_s = 12.0
    safety_critical = True
    payload_model = NwsAlertsPayload

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.base_url = os.getenv("NWS_API_BASE_URL", DEFAULT_BASE).strip().rstrip("/") or DEFAULT_BASE

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        zone = spot.nws_zone or "nozone"
        try:
            start_utc = _as_utc(start)
            end_utc = _as_utc(end)
            span = f"{start_utc.strftime('%Y%m%d%H')}:{end_utc.strftime('%Y%m%d%H')}"
        except ValueError:
            span = "bad"
        return f"{self.name}:{spot.lat:.3f}:{spot.lon:.3f}:{zone}:{span}"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        try:
            start_utc = _as_utc(start)
            end_utc = _as_utc(end)
        except ValueError as exc:
            raise PermanentFetchError("NWS: datetimes must be timezone-aware") from exc
        if end_utc <= start_utc:
            raise PermanentFetchError("NWS: end must be after start")
        if not _point_ok(spot.lat, spot.lon):
            raise PermanentFetchError("NWS: spot lat/lon out of range")
        zone = (spot.nws_zone or "").strip() or None
        if zone is not None and not _ZONE_RE.fullmatch(zone):
            raise PermanentFetchError("NWS: invalid marine zone id")

        headers = {"User-Agent": user_agent(), "Accept": "application/geo+json"}
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers=headers,
            follow_redirects=True,
        ) as client:
            point = await self._get_collection(
                client,
                "/alerts/active",
                {"point": f"{spot.lat:.4f},{spot.lon:.4f}"},
            )
            zone_body = None
            if zone is not None:
                zone_body = await self._get_collection(
                    client,
                    "/alerts/active",
                    {"zone": zone},
                )
        return {
            "point": point,
            "zone": zone_body,
            "marine_zone": zone,
            "_window_start": start_utc.isoformat(),
            "_window_end": end_utc.isoformat(),
        }

    async def _get_collection(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict[str, str],
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        pages: list[dict[str, Any]] = []
        next_url: Optional[str] = url
        next_params: Optional[dict[str, str]] = params
        for _ in range(3):
            if next_url is None:
                break
            body = await self._get_json(client, next_url, next_params)
            pages.append(body)
            nxt = _next_link(body)
            if nxt is None:
                break
            if urlparse(nxt).netloc and urlparse(nxt).netloc != urlparse(self.base_url).netloc:
                raise PermanentFetchError("NWS: pagination left the API host")
            next_url = nxt
            next_params = None
        if not pages:
            raise PermanentFetchError("NWS: empty alert response")
        features: list[Any] = []
        updated = None
        for page in pages:
            if page.get("type") != "FeatureCollection" or not isinstance(page.get("features"), list):
                raise PermanentFetchError("NWS: response is not a FeatureCollection")
            features.extend(page["features"])
            if page.get("updated"):
                updated = page["updated"]
        return {"type": "FeatureCollection", "features": features, "updated": updated}

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[dict[str, str]],
    ) -> dict[str, Any]:
        try:
            resp = await client.get(url, params=params)
        except httpx.TimeoutException:
            raise TransientFetchError("NWS: timeout") from None
        except httpx.TransportError:
            raise TransientFetchError("NWS: connection failed") from None
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientFetchError(f"NWS: HTTP {resp.status_code}")
        if resp.status_code != 200:
            raise PermanentFetchError(f"NWS: HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError:
            raise PermanentFetchError("NWS: response was not JSON") from None
        if not isinstance(data, dict):
            raise PermanentFetchError("NWS: expected JSON object")
        return data

    def _validate(self, raw: Any) -> NwsAlertsPayload:
        if not isinstance(raw, dict):
            raise PermanentFetchError("NWS: expected dict")
        try:
            window_start = _as_utc(datetime.fromisoformat(str(raw["_window_start"])))
            window_end = _as_utc(datetime.fromisoformat(str(raw["_window_end"])))
        except (KeyError, ValueError) as exc:
            raise PermanentFetchError("NWS: missing window") from exc
        point = raw.get("point")
        if not isinstance(point, dict):
            raise PermanentFetchError("NWS: point alerts missing")
        zone_body = raw.get("zone")
        zone_id = raw.get("marine_zone")
        marine_checked = zone_id is not None
        if marine_checked and not isinstance(zone_body, dict):
            raise PermanentFetchError("NWS: marine zone alerts missing")

        merged = _merge_features(point, zone_body if isinstance(zone_body, dict) else None)
        observed = _collection_time(point, zone_body if isinstance(zone_body, dict) else None, merged)
        alerts = [_parse_feature(feature, window_start, window_end) for feature in merged]
        # A real alert with an unknown window beats a confirmed miss.
        small = _flag(alerts, _SMALL_CRAFT, checked=marine_checked)
        gale = _flag(alerts, _GALE, checked=marine_checked)
        beach = _flag(alerts, _BEACH, checked=True)
        thunder = _flag(alerts, _THUNDER, checked=True)
        names = sorted({a.event for a in alerts if a.intersects_window is not False})
        return NwsAlertsPayload(
            observed_at=observed,
            alerts=alerts,
            small_craft_advisory=small,
            gale_warning=gale,
            beach_hazard=beach,
            thunderstorm=thunder,
            any_hazard=_any_hazard(small, gale, beach, thunder),
            marine_zone=str(zone_id) if zone_id else None,
            marine_zone_checked=marine_checked,
            point_checked=True,
            active_event_names=names,
        )


def _point_ok(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180


def _next_link(body: dict[str, Any]) -> Optional[str]:
    pagination = body.get("pagination")
    if not isinstance(pagination, dict):
        return None
    nxt = pagination.get("next")
    if not nxt:
        return None
    return str(nxt)


def _merge_features(point: dict[str, Any], zone: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    collections = [point] if zone is None else [point, zone]
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for collection in collections:
        if collection.get("type") != "FeatureCollection" or not isinstance(collection.get("features"), list):
            raise PermanentFetchError("NWS: response is not a FeatureCollection")
        for feature in collection["features"]:
            if not isinstance(feature, dict):
                raise PermanentFetchError("NWS: alert feature is not an object")
            props = feature.get("properties")
            if not isinstance(props, dict):
                raise PermanentFetchError("NWS: alert is missing properties")
            ident = str(props.get("id") or feature.get("id") or "")
            if not ident:
                raise PermanentFetchError("NWS: alert is missing id")
            if ident in seen:
                continue
            seen.add(ident)
            merged.append(feature)
    return merged


def _collection_time(
    point: dict[str, Any],
    zone: Optional[dict[str, Any]],
    features: list[dict[str, Any]],
) -> datetime:
    stamps: list[datetime] = []
    for collection in (point, zone):
        if not isinstance(collection, dict) or not collection.get("updated"):
            continue
        parsed = _parse_time(collection.get("updated"))
        if parsed is not None:
            stamps.append(parsed)
    for feature in features:
        props = feature.get("properties") or {}
        sent = _parse_time(props.get("sent"))
        if sent is not None:
            stamps.append(sent)
    if not stamps:
        raise PermanentFetchError("NWS: no observed_at on alert feed")
    newest = max(stamps)
    if newest > datetime.now(timezone.utc) + timedelta(minutes=10):
        raise PermanentFetchError("NWS: alert timestamp is in the future")
    return newest


def _parse_feature(feature: dict[str, Any], start: datetime, end: datetime) -> NwsAlert:
    props = feature["properties"]
    event = str(props.get("event") or "").strip()
    if not event:
        raise PermanentFetchError("NWS: alert is missing event")
    status = str(props.get("status") or "").strip()
    if not status:
        raise PermanentFetchError("NWS: alert is missing status")
    onset = _parse_time(props.get("onset"))
    ends = _parse_time(props.get("ends"))
    sent = _parse_time(props.get("sent"))
    zones_raw = (props.get("geocode") or {}).get("UGC") if isinstance(props.get("geocode"), dict) else []
    zones = [str(z) for z in zones_raw] if isinstance(zones_raw, list) else []
    headline = props.get("headline")
    if isinstance(headline, str):
        headline = headline[:300]
    else:
        headline = None
    message_type = str(props.get("messageType") or "Alert").strip().lower()
    countable = status.lower() == "actual" and message_type not in {"cancel", "error"}
    if not countable:
        intersects: Optional[bool] = False
    else:
        intersects = _intersects(onset, ends, start, end)
    return NwsAlert(
        id=str(props.get("id") or feature.get("id")),
        event=event,
        severity=props.get("severity"),
        urgency=props.get("urgency"),
        certainty=props.get("certainty"),
        headline=headline,
        onset=onset,
        ends=ends,
        sent=sent,
        zones=zones,
        intersects_window=intersects,
    )


def _intersects(
    onset: Optional[datetime],
    ends: Optional[datetime],
    start: datetime,
    end: datetime,
) -> Optional[bool]:
    if ends is None:
        return None
    begin = onset or start
    if ends <= start or begin >= end:
        return False
    return True


def _flag(alerts: list[NwsAlert], names: set[str], *, checked: bool) -> Optional[bool]:
    relevant = [a for a in alerts if a.event.lower() in names]
    if any(a.intersects_window is True for a in relevant):
        return True
    if any(a.intersects_window is None for a in relevant):
        return None
    if checked:
        return False
    return None


def _any_hazard(*flags: Optional[bool]) -> Optional[bool]:
    if any(flag is True for flag in flags):
        return True
    if any(flag is None for flag in flags):
        return None
    return False
