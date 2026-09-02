"""Paces every Gemini call in this app against one shared quota.

Google's free tier caps requests per minute for the whole API key, not per
caller — the tenant-change classifier, the directory's diff classifier and
entry extractor, the notice drafter and the outreach drafter all draw from
the same bucket. Nothing here queues or retries; a sweep tick that's
already running sequentially (one vendor/subprocessor at a time, no new
worker) just waits its turn before each real API call, so the account-wide
limit is never exceeded no matter which combination of call sites fires in
the same tick. Hit in production without this: Sentry TRUSTPAGES-8,
2026-09-02 — "Quota exceeded ... limit: 5" during a directory sweep tick.
"""
import asyncio
import time

from app.core.config import settings


class GeminiRateLimiter:
    """Waits, if necessary, so consecutive calls stay at least
    `min_interval_seconds` apart. A single asyncio.Lock is enough:
    everything that calls Gemini already runs on the one event loop of a
    single-worker process (WEB_CONCURRENCY=1), never truly concurrently —
    this only has to serialize awaits on that same loop, not coordinate
    across processes.
    """

    def __init__(self, min_interval_seconds: float) -> None:
        self._min_interval = min_interval_seconds
        self._lock = asyncio.Lock()
        self._last_call_at: float | None = None

    async def wait_turn(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._last_call_at is not None:
                elapsed = now - self._last_call_at
                remaining = self._min_interval - elapsed
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_call_at = time.monotonic()


# One instance, shared by every Gemini call site in the app — see module
# docstring for why a single shared bucket is the point.
gemini_rate_limiter = GeminiRateLimiter(min_interval_seconds=60.0 / settings.GEMINI_FREE_TIER_RPM)
