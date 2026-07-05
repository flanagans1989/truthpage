"""Shared sliding-window rate limiter and client IP resolution.

In-memory: correct for a single-worker asyncio deploy (current Render setup).
If the app ever runs multiple workers, this must move to a shared store.
"""
from collections import deque
from datetime import UTC, datetime

from cachetools import TTLCache
from fastapi import Request


class SlidingWindowLimiter:
    def __init__(self, max_requests: int = 3, window_seconds: int = 60, maxsize: int = 10000):
        self._max = max_requests
        self._window = window_seconds
        self._store: TTLCache = TTLCache(maxsize=maxsize, ttl=window_seconds)

    def allow(self, key: str) -> bool:
        """Return True if the request is allowed; False if the limit is exceeded."""
        now = datetime.now(UTC).timestamp()
        cutoff = now - self._window
        dq = self._store.get(key)
        if dq is None:
            dq = deque()
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= self._max:
            return False
        dq.append(now)
        self._store[key] = dq
        return True


def get_client_ip(request: Request) -> str:
    """Client IP behind Render's proxy.

    Use the LAST entry of X-Forwarded-For: it is appended by the proxy we
    actually trust, while earlier entries are client-supplied and spoofable.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"
