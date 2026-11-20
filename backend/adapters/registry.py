"""Adapter registry: construct adapters, wire HealthMonitor, sync forced_down."""

from __future__ import annotations

from typing import Optional

from backend.adapters.base import SourceAdapter
from backend.adapters.beachwatch import BeachwatchBacteriaAdapter
from backend.adapters.cdph import CdphShellfishAdapter
from backend.adapters.charm import CharmAdapter
from backend.adapters.coops import CoopsCurrentAdapter, CoopsTideAdapter
from backend.adapters.daylight import DaylightAdapter
from backend.adapters.epa_uv import EpaUvAdapter
from backend.adapters.erddap import ErddapChlAdapter, ErddapSstAdapter
from backend.adapters.ndbc import NdbcAdapter
from backend.cache.base import CacheBackend
from backend.cache.memory import MemoryTTLCache
from backend.health import HealthMonitor


class AdapterRegistry:
    def __init__(
        self,
        cache: Optional[CacheBackend] = None,
        health: Optional[HealthMonitor] = None,
    ) -> None:
        self.cache = cache or MemoryTTLCache()
        self.health = health or HealthMonitor()
        self._adapters: dict[str, SourceAdapter] = {}
        self._build()

    # Forecast/prediction feeds: observed_at is the newest *predicted* point, so a future
    # value is expected (review3 P3-2 keeps every other source strict).
    _FORWARD_LOOKING = frozenset(
        {"coops_tides", "coops_tides_interval", "coops_currents", "daylight_sunrise_api"}
    )

    def _add(self, adapter: SourceAdapter) -> None:
        if adapter.name in self._FORWARD_LOOKING:
            adapter.allows_future_observed_at = True
        self._adapters[adapter.name] = adapter
        self.health.register(adapter.name)

    def _build(self) -> None:
        h, c = self.health, self.cache
        self._add(CoopsTideAdapter(c, health=h, interval="hilo"))
        # Separate name for interval product via subclassing instance attribute
        interval = CoopsTideAdapter(c, health=h, interval="6")
        interval.name = "coops_tides_interval"
        self._add(interval)
        self._add(CoopsCurrentAdapter(c, health=h))
        self._add(ErddapChlAdapter(c, health=h))
        self._add(ErddapSstAdapter(c, health=h))
        self._add(CharmAdapter(c, health=h))
        self._add(CdphShellfishAdapter(c, health=h))
        self._add(NdbcAdapter(c, health=h))
        self._add(EpaUvAdapter(c, health=h))
        self._add(BeachwatchBacteriaAdapter(c, health=h))
        self._add(DaylightAdapter(c, health=h))

    def get(self, name: str) -> Optional[SourceAdapter]:
        return self._adapters.get(name)

    def all(self) -> dict[str, SourceAdapter]:
        return dict(self._adapters)

    def names(self) -> list[str]:
        return sorted(self._adapters.keys())

    def set_forced_down(self, name: str, forced: bool) -> bool:
        if name not in self._adapters:
            return False
        self.health.set_forced_down(name, forced)
        self._adapters[name].forced_down = forced
        return True

    def reset_forced_down(self) -> None:
        for name in self._adapters:
            self.set_forced_down(name, False)
