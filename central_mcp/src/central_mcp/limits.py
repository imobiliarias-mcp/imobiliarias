"""In-memory rate limiting and provider throttling utilities."""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager


class TokenBucketLimiter:
    """Per-client IP token bucket rate limiter."""

    def __init__(
        self,
        rate_per_minute: float,
        burst: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._rate_per_second = rate_per_minute / 60.0
        self._burst = float(burst)
        self._clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}

    def check_and_consume(self, key: str) -> tuple[bool, float]:
        """Check if request is allowed; returns (allowed, retry_after_seconds)."""
        now = self._clock()
        tokens, last_time = self._buckets.get(key, (self._burst, now))
        elapsed = max(0.0, now - last_time)
        tokens = min(self._burst, tokens + elapsed * self._rate_per_second)
        if tokens < 1.0:
            deficit = 1.0 - tokens
            retry_after = math.ceil(deficit / self._rate_per_second)
            self._buckets[key] = (tokens, now)
            return False, float(retry_after)
        self._buckets[key] = (tokens - 1.0, now)
        return True, 0.0


class InFlightLimiter:
    """Global concurrency ceiling for in-flight requests."""

    def __init__(self, max_in_flight: int) -> None:
        self._max = max_in_flight
        self._current = 0

    @property
    def current(self) -> int:
        return self._current

    def try_acquire(self) -> bool:
        """Attempt to increment in-flight counter if under limit."""
        if self._current >= self._max:
            return False
        self._current += 1
        return True

    def release(self) -> None:
        """Decrement in-flight counter."""
        if self._current > 0:
            self._current -= 1


class ProviderThrottle:
    """Enforces strict concurrency 1 and minimum delay between requests per provider."""

    def __init__(
        self,
        min_interval_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._min_interval = min_interval_seconds
        self._clock = clock
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_invoked: dict[str, float] = {}

    def _get_lock(self, provider: str) -> asyncio.Lock:
        if provider not in self._locks:
            self._locks[provider] = asyncio.Lock()
        return self._locks[provider]

    @asynccontextmanager
    async def acquire(self, provider: str) -> AsyncIterator[None]:
        """Acquire serialized provider execution with interval pacing."""
        lock = self._get_lock(provider)
        async with lock:
            now = self._clock()
            last = self._last_invoked.get(provider, 0.0)
            elapsed = now - last
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            try:
                yield
            finally:
                self._last_invoked[provider] = self._clock()
