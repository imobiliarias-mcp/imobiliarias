"""Tests for rate limiting and provider throttling."""

import asyncio
import pytest

from central_mcp.limits import InFlightLimiter, ProviderThrottle, TokenBucketLimiter


def test_token_bucket_allows_within_burst():
    current_time = 100.0

    def clock():
        return current_time

    limiter = TokenBucketLimiter(rate_per_minute=60, burst=3, clock=clock)

    # 3 tokens in burst
    allowed, retry_after = limiter.check_and_consume("192.168.1.1")
    assert allowed is True
    assert retry_after == 0.0

    allowed, _ = limiter.check_and_consume("192.168.1.1")
    assert allowed is True

    allowed, _ = limiter.check_and_consume("192.168.1.1")
    assert allowed is True

    # 4th request exceeds burst
    allowed, retry_after = limiter.check_and_consume("192.168.1.1")
    assert allowed is False
    assert retry_after > 0.0


def test_token_bucket_refills_over_time():
    current_time = 100.0

    def clock():
        return current_time

    limiter = TokenBucketLimiter(rate_per_minute=60, burst=1, clock=clock)

    allowed, _ = limiter.check_and_consume("ip1")
    assert allowed is True

    allowed, retry_after = limiter.check_and_consume("ip1")
    assert allowed is False
    assert retry_after == 1.0

    # Advance clock by 1 second (1 token per second for 60/min)
    current_time = 101.0
    allowed, retry_after = limiter.check_and_consume("ip1")
    assert allowed is True
    assert retry_after == 0.0


def test_in_flight_limiter_exceeds_cap():
    limiter = InFlightLimiter(max_in_flight=2)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False

    limiter.release()
    assert limiter.try_acquire() is True


@pytest.mark.asyncio
async def test_provider_throttle_serializes_and_enforces_interval():
    current_time = 0.0

    def fake_clock():
        return current_time

    throttle = ProviderThrottle(min_interval_seconds=0.5, clock=fake_clock)
    events: list[str] = []

    async def worker(idx: int):
        async with throttle.acquire("alecorretoramg"):
            events.append(f"start-{idx}")
            await asyncio.sleep(0.01)
            events.append(f"end-{idx}")

    task1 = asyncio.create_task(worker(1))
    task2 = asyncio.create_task(worker(2))
    await asyncio.gather(task1, task2)

    assert events == ["start-1", "end-1", "start-2", "end-2"] or events == ["start-2", "end-2", "start-1", "end-1"]
