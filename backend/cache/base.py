"""Cache backend interface (memory now; optional SQLite later)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any, Optional


class CacheBackend(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Return value if present and not expired."""

    @abstractmethod
    async def get_stale(self, key: str) -> Optional[Any]:
        """Return value even if expired (for last-known-good)."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: timedelta) -> None:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...
