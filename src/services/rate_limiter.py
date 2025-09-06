"""Rate limiting service."""

import asyncio
import logging
import time
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, config: dict[str, Any]):
        """Initialize rate limiter with configuration."""
        self.requests_per_minute = config.get("requests_per_minute", 60)
        self.burst_size = config.get("burst_size", 10)

        # Token bucket parameters
        self.tokens = self.burst_size  # Start with full bucket
        self.last_refill = time.time()
        self.refill_rate = self.requests_per_minute / 60.0  # tokens per second

        # Request tracking for sliding window
        self.request_times: deque = deque()

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info(
            "Rate limiter initialized",
            extra={
                "requests_per_minute": self.requests_per_minute,
                "burst_size": self.burst_size,
                "refill_rate": self.refill_rate,
            },
        )

    async def acquire(self, tokens_requested: int = 1) -> bool:
        """Acquire tokens from the rate limiter."""
        async with self._lock:
            current_time = time.time()

            # Refill tokens based on time elapsed
            await self._refill_tokens(current_time)

            # Check if we have enough tokens
            if self.tokens >= tokens_requested:
                self.tokens -= tokens_requested
                self.request_times.append(current_time)

                logger.debug(
                    "Rate limit tokens acquired",
                    extra={
                        "tokens_requested": tokens_requested,
                        "tokens_remaining": self.tokens,
                    },
                )

                return True
            else:
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "tokens_requested": tokens_requested,
                        "tokens_available": self.tokens,
                    },
                )

                return False

    async def _refill_tokens(self, current_time: float) -> None:
        """Refill token bucket based on elapsed time."""
        time_elapsed = current_time - self.last_refill

        if time_elapsed > 0:
            tokens_to_add = time_elapsed * self.refill_rate
            self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
            self.last_refill = current_time

            # Clean old request times (older than 1 minute)
            cutoff_time = current_time - 60.0
            while self.request_times and self.request_times[0] < cutoff_time:
                self.request_times.popleft()

    async def wait_for_tokens(
        self, tokens_requested: int = 1, timeout: float = 30.0
    ) -> bool:
        """Wait for tokens to become available."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if await self.acquire(tokens_requested):
                return True

            # Calculate wait time until next token is available
            async with self._lock:
                if self.refill_rate > 0:
                    wait_time = min(1.0 / self.refill_rate, 1.0)  # Max 1 second
                else:
                    wait_time = 1.0

            logger.debug(
                "Waiting for rate limit tokens",
                extra={"wait_time": wait_time, "tokens_requested": tokens_requested},
            )

            await asyncio.sleep(wait_time)

        logger.error(
            "Rate limiter timeout",
            extra={"timeout": timeout, "tokens_requested": tokens_requested},
        )

        return False

    async def get_status(self) -> dict[str, Any]:
        """Get current rate limiter status."""
        async with self._lock:
            current_time = time.time()
            await self._refill_tokens(current_time)

            # Calculate requests in last minute
            cutoff_time = current_time - 60.0
            recent_requests = sum(
                1 for req_time in self.request_times if req_time >= cutoff_time
            )

            status = {
                "tokens_available": round(self.tokens, 2),
                "max_tokens": self.burst_size,
                "requests_per_minute_limit": self.requests_per_minute,
                "requests_in_last_minute": recent_requests,
                "refill_rate_per_second": round(self.refill_rate, 3),
                "utilization_percent": round(
                    (recent_requests / self.requests_per_minute) * 100, 1
                ),
            }

            return status

    async def reset(self) -> None:
        """Reset rate limiter state."""
        async with self._lock:
            self.tokens = self.burst_size
            self.last_refill = time.time()
            self.request_times.clear()

            logger.info("Rate limiter reset")

    def configure(
        self, requests_per_minute: int | None = None, burst_size: int | None = None
    ) -> None:
        """Reconfigure rate limiter parameters."""
        if requests_per_minute is not None:
            self.requests_per_minute = requests_per_minute
            self.refill_rate = requests_per_minute / 60.0

        if burst_size is not None:
            self.burst_size = burst_size
            # Adjust current tokens if burst size changed
            self.tokens = min(self.tokens, burst_size)

        logger.info(
            "Rate limiter reconfigured",
            extra={
                "requests_per_minute": self.requests_per_minute,
                "burst_size": self.burst_size,
            },
        )


class RateLimitedClient:
    """Wrapper that adds rate limiting to any async client."""

    def __init__(self, client, rate_limiter: RateLimiter):
        """Initialize rate limited client wrapper."""
        self.client = client
        self.rate_limiter = rate_limiter

    async def _rate_limited_call(self, method_name: str, *args, **kwargs):
        """Execute client method with rate limiting."""
        # Wait for rate limit tokens
        if not await self.rate_limiter.acquire():
            raise Exception("Rate limit exceeded - no tokens available")

        # Execute the original method
        method = getattr(self.client, method_name)
        return await method(*args, **kwargs)

    def __getattr__(self, name):
        """Proxy method calls through rate limiter."""
        if hasattr(self.client, name):
            attr = getattr(self.client, name)
            if callable(attr):
                # Wrap async methods with rate limiting
                if asyncio.iscoroutinefunction(attr):

                    async def rate_limited_method(*args, **kwargs):
                        return await self._rate_limited_call(name, *args, **kwargs)

                    return rate_limited_method
                else:
                    return attr
            else:
                return attr
        else:
            raise AttributeError(
                f"'{type(self.client).__name__}' object has no attribute '{name}'"
            )
