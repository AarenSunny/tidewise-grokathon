"""Abstract source adapter with timeout, retry, cache, and validation hooks.

Concrete adapters (NDBC, CO-OPS, NWS, satellite SST/chl, alerts) implement
`_fetch_live` and `_validate`. The base `fetch` method owns:
  - forced-down / failure injection
  - TTL cache lookup
  - timeout + exponential backoff (max 3 attempts)
  - sentinel / range validation
  - stale-cache serve on live failure
  - structured logging hooks via notes + HealthMonitor callback
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.cache.base import CacheBackend
from backend.models.common import SourceStatus
from backend.models.sources import SourceResult
from backend.models.spots import Spot

logger = logging.getLogger(__name__)


class SourceAdapter(ABC):
    """Interface every feed adapter must implement."""

    name: str = "base"
    # Per-source TTL defaults (overridden by subclasses)
    ttl: timedelta = timedelta(minutes=30)
    timeout_s: float = 8.0
    max_retries: int = 3
    backoff_base_s: float = 0.5

    def __init__(
        self,
        cache: CacheBackend,
        *,
        forced_down: bool = False,
    ) -> None:
        self.cache = cache
        self.forced_down = forced_down

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        return f"{self.name}:{spot.id}:{start.isoformat()}:{end.isoformat()}"

    async def fetch(self, spot: Spot, start: datetime, end: datetime) -> SourceResult:
        """Fetch with cache, retry, validation, and stale fallback."""
        now = datetime.now(timezone.utc)
        key = self.cache_key(spot, start, end)

        if self.forced_down:
            stale = await self.cache.get_stale(key)
            if stale is not None:
                return self._as_stale(stale, now, notes=["forced_down; serving stale cache"])
            return SourceResult(
                data=None,
                fetched_at=now,
                valid_until=now,
                status=SourceStatus.down,
                source_name=self.name,
                notes=["forced_down; no stale cache"],
            )

        cached = await self.cache.get(key)
        if cached is not None:
            result = SourceResult.model_validate(cached)
            result.cache_hit = True
            result.notes = [*result.notes, "cache_hit"]
            return result

        last_error: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                t0 = asyncio.get_event_loop().time()
                raw = await asyncio.wait_for(
                    self._fetch_live(spot, start, end),
                    timeout=self.timeout_s,
                )
                latency_ms = (asyncio.get_event_loop().time() - t0) * 1000
                validated = self._validate(raw)
                result = SourceResult(
                    data=validated,
                    fetched_at=now,
                    valid_until=now + self.ttl,
                    status=SourceStatus.ok,
                    source_name=self.name,
                    notes=[f"attempt={attempt}"],
                    latency_ms=latency_ms,
                )
                await self.cache.set(key, result.model_dump(mode="json"), self.ttl)
                logger.info(
                    "fetch ok source=%s spot=%s latency_ms=%.0f attempt=%s",
                    self.name,
                    spot.id,
                    latency_ms,
                    attempt,
                )
                return result
            except Exception as exc:  # noqa: BLE001 — adapters must never crash the app
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "fetch fail source=%s spot=%s attempt=%s err=%s",
                    self.name,
                    spot.id,
                    attempt,
                    last_error,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_base_s * (2 ** (attempt - 1)))

        stale = await self.cache.get_stale(key)
        if stale is not None:
            return self._as_stale(
                stale,
                now,
                notes=[f"live_failed: {last_error}", "serving_stale"],
            )

        return SourceResult(
            data=None,
            fetched_at=now,
            valid_until=now,
            status=SourceStatus.down,
            source_name=self.name,
            notes=[f"live_failed: {last_error}", "no_stale_cache"],
        )

    def _as_stale(self, cached: Any, now: datetime, notes: list[str]) -> SourceResult:
        result = SourceResult.model_validate(cached)
        result.status = SourceStatus.stale
        result.cache_hit = True
        result.notes = [*result.notes, *notes]
        result.fetched_at = result.fetched_at  # keep original
        result.valid_until = now  # already expired
        return result

    @abstractmethod
    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        """Perform the live HTTP/API call. Raise on failure."""

    @abstractmethod
    def _validate(self, raw: Any) -> Any:
        """Reject sentinels and impossible values; return cleaned data or raise."""
