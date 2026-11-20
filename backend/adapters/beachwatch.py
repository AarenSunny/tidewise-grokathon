"""BeachWatch bacteria / advisories via CA open data.

Research: San Mateo bacteria max date ~2026-03-02 — STALE for same-day swim.
Missing/stale must never pass a swim safety gate (cannot_confirm).
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
DATASTORE = "https://data.ca.gov/api/3/action/datastore_search"
BACTERIA_RESOURCE_ID = "7bd961cf-abe4-433b-8033-378161237ff3"
ADVISORY_RESOURCE_ID = "d5cd6a23-829c-426d-a63e-689a55a3db9c"


class BeachwatchPayload(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list)
    latest_sample_date: Optional[datetime] = None
    observed_at: Optional[datetime] = None
    stale: bool = True
    cannot_confirm: bool = True
    notes: list[str] = Field(default_factory=list)


class BeachwatchBacteriaAdapter(SourceAdapter):
    name = "beachwatch_bacteria"
    ttl = timedelta(hours=1)
    max_age = timedelta(days=7)
    max_stale_age = timedelta(days=14)
    safety_critical = True
    timeout_s = 12.0
    payload_model = BeachwatchPayload

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        return f"{self.name}:{spot.county or 'region'}"

    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        rid = os.getenv("BEACHWATCH_BACTERIA_RESOURCE_ID", BACTERIA_RESOURCE_ID)
        q = (spot.county or "San Mateo").replace(" County", "")
        params = {"resource_id": rid, "limit": 50, "q": q}
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s, connect=4.0),
            headers={"User-Agent": UA},
            follow_redirects=True,
        ) as client:
            resp = await client.get(DATASTORE, params=params)
            if resp.status_code >= 500 or resp.status_code == 429:
                raise TransientFetchError(f"BeachWatch HTTP {resp.status_code}")
            if resp.status_code >= 400:
                raise PermanentFetchError(f"BeachWatch HTTP {resp.status_code}")
            return resp.json()

    def _validate(self, raw: Any) -> BeachwatchPayload:
        result = (raw or {}).get("result") or {}
        records = result.get("records") or []
        latest: Optional[datetime] = None
        for rec in records:
            for key in ("SampleDate", "sample_date", "DATE", "ActivityStartDate", "DateofAdvisory"):
                if key in rec and rec[key]:
                    try:
                        raw_d = str(rec[key])[:10]
                        dt = datetime.strptime(raw_d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        if latest is None or dt > latest:
                            latest = dt
                    except ValueError:
                        continue
        now = datetime.now(timezone.utc)
        stale = True
        cannot_confirm = True
        notes = ["swim_gate_requires_fresh_bacteria"]
        if latest is not None:
            age = now - latest
            notes.append(f"latest_sample={latest.date().isoformat()} age_days={age.days}")
            if age <= timedelta(days=7):
                stale = False
                cannot_confirm = False
            else:
                notes.append("stale_bacteria_cannot_confirm")
        else:
            notes.append("no_sample_date_cannot_confirm")
        return BeachwatchPayload(
            records=records[:20],
            latest_sample_date=latest,
            observed_at=latest or now,
            stale=stale,
            cannot_confirm=cannot_confirm,
            notes=notes,
        )
