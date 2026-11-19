"""In-memory TTL cache with stale retention for last-known-good."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.cache.base import CacheBackend


@dataclass
class _Entry:
    value: Any
    expires_at: datetime


class MemoryTTLCache(CacheBackend):
    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._now():
            return None
        return entry.value

    async def get_stale(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        return None if entry is None else entry.value

    async def set(self, key: str, value: Any, ttl: timedelta) -> None:
        self._store[key] = _Entry(value=value, expires_at=self._now() + ttl)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
