"""HealthMonitor: tracks adapter success/error/latency/status."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from backend.models.common import SourceStatus
from backend.models.sources import AdapterHealth


class HealthMonitor:
    def __init__(self) -> None:
        self._health: dict[str, AdapterHealth] = {}

    def ensure(self, source_name: str) -> AdapterHealth:
        if source_name not in self._health:
            self._health[source_name] = AdapterHealth(
                source_name=source_name,
                status=SourceStatus.ok,
            )
        return self._health[source_name]

    def record_success(
        self,
        source_name: str,
        latency_ms: Optional[float] = None,
        status: SourceStatus = SourceStatus.ok,
    ) -> None:
        h = self.ensure(source_name)
        h.status = status
        h.last_success_at = datetime.now(timezone.utc)
        h.last_latency_ms = latency_ms
        h.consecutive_failures = 0

    def record_failure(self, source_name: str, error: str) -> None:
        h = self.ensure(source_name)
        h.status = SourceStatus.down
        h.last_error_at = datetime.now(timezone.utc)
        h.last_error = error
        h.consecutive_failures += 1

    def set_forced_down(self, source_name: str, forced: bool) -> None:
        h = self.ensure(source_name)
        h.forced_down = forced
        if forced:
            h.status = SourceStatus.down

    def snapshot(self) -> list[AdapterHealth]:
        return list(self._health.values())

    def overall_status(self) -> str:
        statuses = {h.status for h in self._health.values()}
        if not statuses or statuses == {SourceStatus.ok}:
            return "ok"
        if SourceStatus.down in statuses and all(
            h.status == SourceStatus.down for h in self._health.values()
        ):
            return "down"
        return "degraded"
