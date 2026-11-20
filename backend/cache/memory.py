"""In-memory TTL cache with stale retention, max age, and size cap (review1-#4)."""

from __future__ import annotations

import copy
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.cache.base import CacheBackend


@dataclass
class _Entry:
    value: Any
    expires_at: datetime
    stored_at: datetime


class MemoryTTLCache(CacheBackend):
    """LRU-ish TTL cache. get() honours TTL; get_stale() returns last-known-good
    unless the entry age is >= max_stale_age (review1-#4).
    Values are deep-copied on read so callers cannot mutate the cache (review1-#19).
    """

    def __init__(
        self,
        *,
        max_entries: int = 512,
        default_max_stale_age: timedelta = timedelta(hours=24),
    ) -> None:
        self._store: OrderedDict[str, _Entry] = OrderedDict()
        self.max_entries = max_entries
        self.default_max_stale_age = default_max_stale_age

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _evict_if_needed(self) -> None:
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def _copy(self, value: Any) -> Any:
        try:
            return copy.deepcopy(value)
        except Exception:  # noqa: BLE001
            return value

    async def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._now():
            return None
        self._store.move_to_end(key)
        return self._copy(entry.value)

    async def get_stale(
        self,
        key: str,
        *,
        max_stale_age: Optional[timedelta] = None,
    ) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        age_limit = max_stale_age if max_stale_age is not None else self.default_max_stale_age
        # age >= limit ⇒ refuse (max_stale_age=0 never serves stale)
        if self._now() - entry.stored_at >= age_limit:
            return None
        self._store.move_to_end(key)
        return self._copy(entry.value)

    async def set(self, key: str, value: Any, ttl: timedelta) -> None:
        now = self._now()
        self._store[key] = _Entry(
            value=self._copy(value),
            expires_at=now + ttl,
            stored_at=now,
        )
        self._store.move_to_end(key)
        self._evict_if_needed()

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def __len__(self) -> int:
        return len(self._store)
