"""Abstract source adapter with timeout, retry, cache, freshness, and validation.

Concrete adapters implement `_fetch_live` and `_validate`. The base `fetch` owns:
  - forced-down / failure injection (via HealthMonitor when wired)
  - stable cache keys (station/product, not microsecond windows) — review1-#3
  - TTL cache lookup with typed rehydration — review1-#5
  - overall deadline + httpx-friendly retries — review1-#6/#7
  - observed_at freshness vs max_age — review1-#2
  - max_stale_age beyond which stale cache is refused — review1-#4
  - HealthMonitor reporting — review1-#9
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional, Type

from pydantic import BaseModel

from backend.cache.base import CacheBackend
from backend.models.common import SourceStatus
from backend.models.sources import SourceResult
from backend.models.spots import Spot

if TYPE_CHECKING:
    from backend.health import HealthMonitor

logger = logging.getLogger(__name__)


class PermanentFetchError(Exception):
    """4xx / validation / config errors — do not retry (review1-#7)."""


class TransientFetchError(Exception):
    """Timeouts / 5xx / connect — may retry."""


class SourceAdapter(ABC):
    """Interface every feed adapter must implement."""

    name: str = "base"
    ttl: timedelta = timedelta(minutes=30)
    timeout_s: float = 8.0
    max_retries: int = 3
    backoff_base_s: float = 0.5
    # Overall wall-clock budget for one fetch() call (review1-#6)
    overall_deadline_s: float = 12.0
    # Observation age beyond which live success is still stale/down (review1-#2)
    max_age: timedelta = timedelta(hours=6)
    # How long a last-known-good cache entry may be served (review1-#4)
    max_stale_age: timedelta = timedelta(hours=24)
    # If True, age > max_age ⇒ down (not just stale) — for closures/alerts
    safety_critical: bool = False
    # Optional pydantic model for data rehydration from cache (review1-#5)
    payload_model: Optional[Type[BaseModel]] = None

    def __init__(
        self,
        cache: CacheBackend,
        *,
        forced_down: bool = False,
        health: Optional["HealthMonitor"] = None,
    ) -> None:
        self.cache = cache
        self._forced_down = forced_down
        self.health = health

    @property
    def forced_down(self) -> bool:
        if self.health is not None:
            return self.health.is_forced_down(self.name)
        return self._forced_down

    @forced_down.setter
    def forced_down(self, value: bool) -> None:
        self._forced_down = value
        if self.health is not None:
            self.health.set_forced_down(self.name, value)

    def cache_key(self, spot: Spot, start: datetime, end: datetime) -> str:
        """Stable key by source + station/product (review1-#3).

        Subclasses should override to include station/grid IDs. Default uses
        spot id + quantized UTC hour of start (not microseconds).
        """
        start_utc = start.astimezone(timezone.utc) if start.tzinfo else start.replace(tzinfo=timezone.utc)
        hour = start_utc.replace(minute=0, second=0, microsecond=0)
        return f"{self.name}:{spot.id}:{hour.strftime('%Y%m%d%H')}"

    def _rehydrate(self, cached: Any) -> SourceResult:
        """Rebuild SourceResult and typed payload from cached JSON (review1-#5)."""
        result = SourceResult.model_validate(cached)
        if result.data is not None and result.data_type:
            try:
                module_path, cls_name = result.data_type.rsplit(".", 1)
                mod = importlib.import_module(module_path)
                cls = getattr(mod, cls_name)
                if issubclass(cls, BaseModel) and isinstance(result.data, dict):
                    result.data = cls.model_validate(result.data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("cache rehydrate failed source=%s err=%s", self.name, exc)
        elif result.data is not None and self.payload_model is not None and isinstance(result.data, dict):
            result.data = self.payload_model.model_validate(result.data)
        return result

    def _serialize_for_cache(self, result: SourceResult) -> dict[str, Any]:
        """Serialize outside the retry try-block (review1-#5)."""
        if isinstance(result.data, BaseModel):
            result.data_type = f"{result.data.__class__.__module__}.{result.data.__class__.__name__}"
        return result.model_dump(mode="json")

    def _apply_freshness(self, result: SourceResult, now: datetime) -> SourceResult:
        """Mark stale/down from observed_at vs max_age (review1-#2)."""
        if result.observed_at is None or result.data is None:
            return result
        age = now - result.observed_at
        if age <= self.max_age:
            return result
        note = f"observation_age={age.total_seconds():.0f}s exceeds max_age={self.max_age.total_seconds():.0f}s"
        result.notes = [*result.notes, note]
        if self.safety_critical or age > self.max_stale_age:
            result.status = SourceStatus.down
            result.notes = [*result.notes, "observation_too_old_for_safety"]
        else:
            result.status = SourceStatus.stale
        return result

    async def fetch(self, spot: Spot, start: datetime, end: datetime) -> SourceResult:
        """Fetch with cache, retry, validation, freshness, and stale fallback."""
        now = datetime.now(timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        key = self.cache_key(spot, start, end)

        try:
            return await asyncio.wait_for(
                self._fetch_inner(spot, start, end, now, key),
                timeout=self.overall_deadline_s,
            )
        except asyncio.TimeoutError:
            return await self._fail_or_stale(
                key,
                now,
                error="overall_deadline_exceeded",
            )

    async def _fetch_inner(
        self,
        spot: Spot,
        start: datetime,
        end: datetime,
        now: datetime,
        key: str,
    ) -> SourceResult:
        if self.forced_down:
            return await self._fail_or_stale(key, now, error="forced_down")

        cached = await self.cache.get(key)
        if cached is not None:
            result = self._rehydrate(cached)
            result.cache_hit = True
            result.notes = [*result.notes, "cache_hit"]
            result = self._apply_freshness(result, now)
            self._report(result)
            return result

        last_error: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                t0 = asyncio.get_running_loop().time()
                raw = await asyncio.wait_for(
                    self._fetch_live(spot, start, end),
                    timeout=self.timeout_s,
                )
                latency_ms = (asyncio.get_running_loop().time() - t0) * 1000
                validated = self._validate(raw)
                if validated is None:
                    raise PermanentFetchError("validator returned None/empty")

                observed_at = self._extract_observed_at(validated)
                result = SourceResult(
                    data=validated,
                    fetched_at=now,
                    valid_until=now + self.ttl,
                    status=SourceStatus.ok,
                    source_name=self.name,
                    notes=[f"attempt={attempt}"],
                    latency_ms=latency_ms,
                    observed_at=observed_at,
                )
                result = self._apply_freshness(result, now)
                # Cache serialization outside retry classification path
                try:
                    payload = self._serialize_for_cache(result)
                    await self.cache.set(key, payload, self.ttl)
                except Exception as ser_exc:  # noqa: BLE001
                    result.notes = [*result.notes, f"cache_set_failed:{type(ser_exc).__name__}"]
                logger.info(
                    "fetch ok source=%s spot=%s latency_ms=%.0f attempt=%s status=%s",
                    self.name,
                    spot.id,
                    latency_ms,
                    attempt,
                    result.status.value,
                )
                self._report(result)
                return result
            except PermanentFetchError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "fetch permanent_fail source=%s spot=%s err=%s",
                    self.name,
                    spot.id,
                    last_error,
                )
                break
            except Exception as exc:  # noqa: BLE001 — transient or unexpected
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "fetch fail source=%s spot=%s attempt=%s err=%s",
                    self.name,
                    spot.id,
                    attempt,
                    last_error,
                )
                # Retry only transient-ish errors (review1-#7)
                retryable = isinstance(
                    exc,
                    (
                        TransientFetchError,
                        asyncio.TimeoutError,
                        TimeoutError,
                        ConnectionError,
                        OSError,
                    ),
                )
                # httpx errors by name to avoid hard import dependency at module level
                ename = type(exc).__name__
                if ename in {"ConnectError", "ReadTimeout", "WriteTimeout", "PoolTimeout", "RemoteProtocolError"}:
                    retryable = True
                if ename == "HTTPStatusError":
                    status_code = getattr(getattr(exc, "response", None), "status_code", None)
                    if status_code is not None and (status_code == 429 or status_code >= 500):
                        retryable = True
                    else:
                        retryable = False
                if not retryable or attempt >= self.max_retries:
                    break
                delay = self.backoff_base_s * (2 ** (attempt - 1))
                delay *= 0.5 + random.random()  # jitter
                await asyncio.sleep(delay)

        return await self._fail_or_stale(key, now, error=last_error or "unknown")

    async def _fail_or_stale(self, key: str, now: datetime, *, error: str) -> SourceResult:
        stale = await self.cache.get_stale(key, max_stale_age=self.max_stale_age)
        if stale is not None:
            result = self._as_stale(stale, now, notes=[f"live_failed: {error}", "serving_stale"])
            result = self._apply_freshness(result, now)
            # If freshness demoted to down, keep that
            self._report(result, failure_note=error)
            return result
        result = SourceResult(
            data=None,
            fetched_at=now,
            valid_until=now,
            status=SourceStatus.down,
            source_name=self.name,
            notes=[f"live_failed: {error}", "no_stale_cache"],
        )
        self._report(result, failure_note=error)
        return result

    def _as_stale(self, cached: Any, now: datetime, notes: list[str]) -> SourceResult:
        result = self._rehydrate(cached)
        result.status = SourceStatus.stale
        result.cache_hit = True
        result.notes = [*result.notes, *notes]
        result.valid_until = now
        return result

    def _report(self, result: SourceResult, failure_note: Optional[str] = None) -> None:
        if self.health is None:
            return
        if result.status in {SourceStatus.ok, SourceStatus.stale, SourceStatus.degraded}:
            self.health.record_success(
                self.name,
                latency_ms=result.latency_ms,
                status=result.status,
            )
        else:
            self.health.record_failure(self.name, failure_note or ";".join(result.notes) or "down")

    def _extract_observed_at(self, validated: Any) -> Optional[datetime]:
        """Pull observation time from validated payload if present."""
        if isinstance(validated, BaseModel):
            for attr in ("observed_at", "time", "observation_time"):
                v = getattr(validated, attr, None)
                if isinstance(v, datetime):
                    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if isinstance(validated, dict):
            for key in ("observed_at", "time", "observation_time"):
                v = validated.get(key)
                if isinstance(v, datetime):
                    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return None

    @abstractmethod
    async def _fetch_live(self, spot: Spot, start: datetime, end: datetime) -> Any:
        """Perform the live HTTP/API call. Raise on failure."""

    @abstractmethod
    def _validate(self, raw: Any) -> Any:
        """Reject sentinels and impossible values; return cleaned data or raise."""
