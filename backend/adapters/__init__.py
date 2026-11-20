"""Source adapters: one class per feed, shared SourceAdapter interface."""

from backend.adapters.base import PermanentFetchError, SourceAdapter, TransientFetchError
from backend.adapters.registry import AdapterRegistry

__all__ = [
    "SourceAdapter",
    "PermanentFetchError",
    "TransientFetchError",
    "AdapterRegistry",
]
