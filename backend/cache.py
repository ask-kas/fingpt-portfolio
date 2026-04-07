"""
cache.py — Simple in-memory TTL cache. No external dependencies.
"""

import time
from typing import Any, Optional


class TTLCache:
    """Thread-safe-ish dict-based cache with per-key expiration."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            value, expires = self._store[key]
            if time.time() < expires:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl_seconds: int):
        self._store[key] = (value, time.time() + ttl_seconds)

    def clear(self):
        self._store.clear()


# Module-level singleton
cache = TTLCache()
