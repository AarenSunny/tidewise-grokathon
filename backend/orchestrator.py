"""Orchestrator stub — wires intent → adapters → features → scorers → explainer."""

from __future__ import annotations

# Implemented in Phase 6. Phase 1 only reserves the module boundary.


class Orchestrator:
    """Manages bots and adapters as separate modules with clear interfaces."""

    def __init__(self) -> None:
        raise NotImplementedError("Orchestrator lands in Phase 6")
