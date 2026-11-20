"""Abstract source adapter with timeout, retry, cache, freshness, and validation.

Concrete adapters implement `_fetch_live` and `_validate`. The base `fetch` owns:
  - forced-down / failure injection (via HealthMonitor when wired)
  - stable cache keys (station/product, not microsecond windows) — review1-#3
  - TTL cache lookup with typed rehydration — review1-#5
  - overall deadline + httpx-friendly retries — review1-#6/#7
  - observed_at freshness vs max_age — review1-#2
  - max_stale_age beyond which stale cache is refused — review1-#4
  - HealthMonitor reporting — review1-#9
  - error redaction — review1-#13
  - single-flight per cache key — review1-#14
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional, Type

from pydantic import BaseModel, ValidationError

from backend.cache.base import CacheBackend
from backend.models.common import SourceStatus
from backend.models.sources import SourceResult
from backend.models.spots import Spot
from backend.redact import redact, redact_error

if TYPE_CHECKING:
    from backend.health import HealthMonitor

logger = logging.getLogger(__name__)

# Process-wide single-flight map (review1-#14)
_INFLIGHT: dict[str, asyncio.Future[SourceResult]] = {}
_INFLIGHT_GUARD: asyncio.Lock | None = None


def _get_inflight_lock() -> asyncio.Lock:
    global _INFLIGHT_GUARD
    if _INFLIGHT_GUARD is None:
        _INFLIGHT_GUARD = asyncio.Lock()
    return _INFLIGHT_GUARD


class PermanentFetchError(Exception):
    """4xx / validation / config errors — do not retry (review1-#7)."""


class TransientFetchError(Exception):
    """Timeouts / 5xx / connect — may retry."""

    def __init__(self, message: str, *, retry_after_s: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


_DEFAULT_FUTURE_SKEW = timedelta(minutes=5)


class SourceAdapter(ABC):
    """Interface every feed adapter must implement."""

    name: str = "base"
    ttl: timedelta = timedelta(minutes=30)
    timeout_s: float = 8.0
    max_retries: int = 3
    backoff_base_s: float = 0.5
    overall_deadline_s: float = 12.0
    max_age: timedelta = timedelta(hours=6)
    max_stale_age: timedelta = timedelta(hours=24)
    safety_critical: bool = False
    payload_model: Optional[Type[BaseModel]] = None
    # review3 P3-2: an observed_at further in the future than this is invalid, not fresh.
    # Override per class, or globally via ADAPTER_MAX_FUTURE_SKEW_S (seconds).
    max_future_skew: Optional[timedelta] = None
    # Forecast/prediction feeds (tides, currents, sunrise) legitimately carry a future
    # observed_at (newest predicted point). They opt in explicitly; default is strict.
    allows_future_observed_at: bool = False
    # review1-#6: bound every sync parse so a hung/slow validator cannot stall the loop.
    validate_timeout_s: float = 5.0

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
        """Stable key by source + station/product (review1-#3)."""
        start_utc = (
            start.astimezone(timezone.utc)
            if start.tzinfo
            else start.replace(tzinfo=timezone.utc)
        )
        hour = start_utc.replace(minute=0, second=0, microsecond=0)
        return f"{self.name}:{spot.id}:{hour.strftime('%Y%m%d%H')}"

    def _rehydrate(self, cached: Any) -> Optional[SourceResult]:
        """Rebuild SourceResult and typed payload from cached JSON (review1-#5).

        Returns None if the cached payload cannot be validated — callers treat
        that as a cache miss / no-stale (never raise into the request path).
        """
        try:
            result = SourceResult.model_validate(cached)
        except ValidationError as exc:
            logger.warning(
                "cache rehydrate SourceResult failed source=%s err=%s",
                self.name,
                redact_error(exc),
            )
            return None

        if result.data is not None and result.data_type:
            try:
                module_path, cls_name = result.data_type.rsplit(".", 1)
                mod = importlib.import_module(module_path)
                cls = getattr(mod, cls_name)
                if issubclass(cls, BaseModel) and isinstance(result.data, dict):
                    result.data = cls.model_validate(result.data)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "cache rehydrate typed payload failed source=%s err=%s",
                    self.name,
                    redact_error(exc),
                )
                return None
        elif (
            result.data is not None
            and self.payload_model is not None
            and isinstance(result.data, dict)
        ):
            try:
                result.data = self.payload_model.model_validate(result.data)
            except ValidationError as exc:
                logger.warning(
                    "cache rehydrate payload_model failed source=%s err=%s",
                    self.name,
                    redact_error(exc),
                )
                return None
        return result

    def _serialize_for_cache(self, result: SourceResult) -> dict[str, Any]:
        if isinstance(result.data, BaseModel):
            result.data_type = (
                f"{result.data.__class__.__module__}.{result.data.__class__.__name__}"
            )
        return result.model_dump(mode="json")

    def _future_skew(self) -> timedelta:
        if self.max_future_skew is not None:
            return self.max_future_skew
        raw = os.getenv("ADAPTER_MAX_FUTURE_SKEW_S", "").strip()
        try:
            return timedelta(seconds=float(raw)) if raw else _DEFAULT_FUTURE_SKEW
        except ValueError:
            return _DEFAULT_FUTURE_SKEW

    @staticmethod
    def _worse(current: SourceStatus, candidate: SourceStatus) -> SourceStatus:
        order = {
            SourceStatus.ok: 0,
            SourceStatus.unknown: 1,
            SourceStatus.degraded: 1,
            SourceStatus.stale: 2,
            SourceStatus.down: 3,
        }
        return candidate if order[candidate] > order[current] else current

    def _apply_freshness(self, result: SourceResult, now: datetime) -> SourceResult:
        """Judge payload freshness by the observation's own time (review1-#2, review3 P3-2).

        - no payload: nothing to judge (caller already has a down/stale status).
        - observed_at missing: NOT fresh (stale, down if safety-critical). A gate that
          needs this source gets cannot_confirm, never a pass.
        - observed_at in the future beyond the skew: invalid (down), never fresh.
        """
        if result.data is None:
            return result
        degraded = SourceStatus.down if self.safety_critical else SourceStatus.stale
        if result.observed_at is None:
            result.notes = [*result.notes, "observed_at_missing_not_fresh"]
            result.status = self._worse(result.status, degraded)
            return result
        age = now - result.observed_at
        if age < -self._future_skew():
            if self.allows_future_observed_at:
                return result
            result.notes = [
                *result.notes,
                f"observed_at_in_future_invalid by {(-age).total_seconds():.0f}s",
            ]
            result.status = SourceStatus.down
            return result
        if age <= self.max_age:
            return result
        note = (
            f"observation_age={age.total_seconds():.0f}s "
            f"exceeds max_age={self.max_age.total_seconds():.0f}s"
        )
        result.notes = [*result.notes, note]
        if self.safety_critical or age > self.max_stale_age:
            result.status = SourceStatus.down
            result.notes = [*result.notes, "observation_too_old_for_safety"]
        else:
            result.status = self._worse(result.status, SourceStatus.stale)
        return result

    async def fetch(self, spot: Spot, start: datetime, end: datetime) -> SourceResult:
        """Fetch with single-flight, cache, retry, validation, freshness, stale fallback."""
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        key = self.cache_key(spot, start, end)

        # Single-flight: coalesce concurrent cache-miss fetches (review1-#14)
        lock = _get_inflight_lock()
        async with lock:
            existing = _INFLIGHT.get(key)
            if existing is not None:
                waiter: asyncio.Future[SourceResult] = asyncio.get_running_loop().create_future()

                def _chain(fut: asyncio.Future[SourceResult]) -> None:
                    if waiter.done():
                        return
                    if fut.cancelled():
                        waiter.cancel()
                    elif fut.exception() is not None:
                        waiter.set_exception(fut.exception())  # type: ignore[arg-type]
                    else:
                        waiter.set_result(fut.result())

                existing.add_done_callback(_chain)
                leader = False
                fut = waiter
            else:
                fut = asyncio.get_running_loop().create_future()
                _INFLIGHT[key] = fut
                leader = True

        if not leader:
            return await fut

        try:
            result = await asyncio.wait_for(
                self._fetch_inner(spot, start, end, key),
                timeout=self.overall_deadline_s,
            )
            if not fut.done():
                fut.set_result(result)
            return result
        except asyncio.TimeoutError:
            result = await self._fail_or_stale(
                key,
                datetime.now(timezone.utc),
                error="overall_deadline_exceeded",
            )
            if not fut.done():
                fut.set_result(result)
            return result
        except Exception as exc:  # noqa: BLE001
            if not fut.done():
                fut.set_exception(exc)
            raise
        finally:
            async with lock:
                if _INFLIGHT.get(key) is fut:
                    _INFLIGHT.pop(key, None)

    async def _fetch_inner(
        self,
        spot: Spot,
        start: datetime,
        end: datetime,
        key: str,
    ) -> SourceResult:
        now = datetime.now(timezone.utc)
        if self.forced_down:
            return await self._fail_or_stale(key, now, error="forced_down")

        cached = await self.cache.get(key)
        if cached is not None:
            result = self._rehydrate(cached)
            if result is not None:
                result.cache_hit = True
                result.notes = [*result.notes, "cache_hit"]
                result = self._apply_freshness(result, now)
                self._report(result)
                return result
            # corrupt cache entry — fall through to live
            await self.cache.delete(key)

        last_error: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                t0 = time.monotonic()
                raw = await asyncio.wait_for(
                    self._fetch_live(spot, start, end),
                    timeout=self.timeout_s,
                )
                latency_ms = (time.monotonic() - t0) * 1000
                try:
                    validated = await asyncio.wait_for(
                        asyncio.to_thread(self._validate, raw),
                        timeout=self.validate_timeout_s,
                    )
                except asyncio.TimeoutError:
                    raise PermanentFetchError("validator timed out (sync parse bounded)") from None
                if validated is None:
                    raise PermanentFetchError("validator returned None/empty")

                fetched_at = datetime.now(timezone.utc)
                observed_at = self._extract_observed_at(validated)
                result = SourceResult(
                    data=validated,
                    fetched_at=fetched_at,
                    valid_until=fetched_at + self.ttl,
                    status=SourceStatus.ok,
                    source_name=self.name,
                    notes=[f"attempt={attempt}"],
                    latency_ms=latency_ms,
                    observed_at=observed_at,
                )
                result = self._apply_freshness(result, fetched_at)
                try:
                    payload = self._serialize_for_cache(result)
                    await self.cache.set(key, payload, self.ttl)
                except Exception as ser_exc:  # noqa: BLE001
                    result.notes = [
                        *result.notes,
                        f"cache_set_failed:{type(ser_exc).__name__}",
                    ]
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
                last_error = redact_error(exc)
                logger.warning(
                    "fetch permanent_fail source=%s spot=%s err=%s",
                    self.name,
                    spot.id,
                    last_error,
                )
                break
            except Exception as exc:  # noqa: BLE001
                last_error = redact_error(exc)
                logger.warning(
                    "fetch fail source=%s spot=%s attempt=%s err=%s",
                    self.name,
                    spot.id,
                    attempt,
                    last_error,
                )
                retryable, retry_after = self._classify_retry(exc)
                if not retryable or attempt >= self.max_retries:
                    break
                if retry_after is not None:
                    delay = max(0.0, retry_after)
                else:
                    delay = self.backoff_base_s * (2 ** (attempt - 1))
                    delay *= 0.5 + random.random()
                await asyncio.sleep(delay)

        return await self._fail_or_stale(
            key, datetime.now(timezone.utc), error=last_error or "unknown"
        )

    def _classify_retry(self, exc: BaseException) -> tuple[bool, Optional[float]]:
        """Return (retryable, retry_after_s). Honour Retry-After on 429 (review1-#7)."""
        if isinstance(exc, TransientFetchError):
            return True, exc.retry_after_s
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError)):
            return True, None
        ename = type(exc).__name__
        if ename in {
            "ConnectError",
            "ReadTimeout",
            "WriteTimeout",
            "PoolTimeout",
            "RemoteProtocolError",
            "NetworkError",
        }:
            return True, None
        if ename == "HTTPStatusError":
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code == 429 or (status_code is not None and status_code >= 500):
                retry_after = None
                headers = getattr(response, "headers", None) or {}
                raw_ra = headers.get("Retry-After") or headers.get("retry-after")
                if raw_ra:
                    try:
                        retry_after = float(raw_ra)
                    except ValueError:
                        retry_after = None
                return True, retry_after
            return False, None
        return False, None

    async def _fail_or_stale(self, key: str, now: datetime, *, error: str) -> SourceResult:
        safe_error = redact(error)
        stale = await self.cache.get_stale(key, max_stale_age=self.max_stale_age)
        if stale is not None:
            result = self._as_stale(
                stale, now, notes=[f"live_failed: {safe_error}", "serving_stale"]
            )
            if result is None:
                # corrupt stale entry
                pass
            else:
                result = self._apply_freshness(result, now)
                self._report(result, failure_note=safe_error)
                return result
        result = SourceResult(
            data=None,
            fetched_at=now,
            valid_until=now,
            status=SourceStatus.down,
            source_name=self.name,
            notes=[f"live_failed: {safe_error}", "no_stale_cache"],
        )
        self._report(result, failure_note=safe_error)
        return result

    def _as_stale(
        self, cached: Any, now: datetime, notes: list[str]
    ) -> Optional[SourceResult]:
        result = self._rehydrate(cached)
        if result is None:
            return None
        result.status = SourceStatus.stale
        result.cache_hit = True
        # Bound note growth (review1-#19)
        merged = [*result.notes, *notes]
        result.notes = merged[-20:]
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
            self.health.record_failure(
                self.name, redact(failure_note or ";".join(result.notes) or "down")
            )

    def _extract_observed_at(self, validated: Any) -> Optional[datetime]:
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
