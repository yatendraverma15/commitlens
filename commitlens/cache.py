import time
from typing import Generic, Hashable, Optional, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._store: dict[Hashable, tuple[T, float]] = {}

    def get(self, key: Hashable) -> Optional[T]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at <= time.time():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: Hashable, value: T) -> None:
        self._store[key] = (value, time.time() + self._ttl)
