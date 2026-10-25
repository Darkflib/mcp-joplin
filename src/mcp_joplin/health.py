"""Readiness probe for the Joplin Data API, cached for cheap /health polling.

The sidecar launcher polls ``/health`` (2 s timeout, any 2xx/3xx is healthy)
and shows only the status code, so this module:

- answers from a short-lived cache and coalesces concurrent probes, so a slow
  Joplin can't make the endpoint itself time out;
- logs every state transition with its reason, because the launcher's captured
  log is the only place a human will see *why* the sidecar went unhealthy.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Literal

import httpx

from .redaction import redact

logger = logging.getLogger(__name__)

JoplinState = Literal["ok", "unreachable", "unauthorized", "error"]

# Joplin's clipper server answers GET /ping with this body
# (packages/lib/services/rest/routes/ping.ts).
_PING_BODY = "JoplinClipperServer"


@dataclass(frozen=True, slots=True)
class HealthResult:
    joplin: JoplinState
    detail: str
    checked_at: float

    @property
    def ok(self) -> bool:
        return self.joplin == "ok"

    def as_dict(self) -> dict[str, object]:
        # Safe to return unauthenticated: no URLs, no secrets, no Joplin data.
        return {"ok": self.ok, "joplin": self.joplin, "detail": self.detail}


class JoplinHealth:
    """Probe Joplin reachability and token validity, caching the result."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        ttl_seconds: float = 15.0,
        timeout_seconds: float = 1.5,
        log_transitions: bool = True,
    ) -> None:
        # timeout_seconds bounds the whole probe (both requests), not each one:
        # the default stays under the launcher's 2 s health-check timeout.
        self._timeout = timeout_seconds
        self._token = token
        self._log_transitions = log_transitions
        self._ttl = ttl_seconds
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
        )
        self._lock = asyncio.Lock()
        self._cached: HealthResult | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def check(self, *, force: bool = False) -> HealthResult:
        """Return the cached result, probing Joplin if it is stale (or ``force``)."""
        cached = self._cached
        if not force and cached is not None and time.monotonic() - cached.checked_at < self._ttl:
            return cached
        async with self._lock:
            # Another caller may have refreshed it while we waited for the lock.
            cached = self._cached
            if (
                not force
                and cached is not None
                and time.monotonic() - cached.checked_at < self._ttl
            ):
                return cached
            try:
                async with asyncio.timeout(self._timeout):
                    result = await self._probe()
            except TimeoutError:
                result = HealthResult(
                    "unreachable",
                    f"Joplin Data API did not answer within {self._timeout:g}s",
                    time.monotonic(),
                )
            if self._log_transitions:
                self._log_transition(cached, result)
            self._cached = result
            return result

    async def _probe(self) -> HealthResult:
        now = time.monotonic()
        try:
            # 1. Is the clipper service up at all? (No token needed.)
            ping = await self._client.get("/ping")
            if ping.status_code != 200 or _PING_BODY not in ping.text:
                return HealthResult(
                    "error", f"unexpected /ping response (HTTP {ping.status_code})", now
                )
            # 2. Does the token work? Cheapest authenticated call available.
            resp = await self._client.get(
                "/folders", params={"limit": 1, "fields": "id", "token": self._token}
            )
        except httpx.HTTPError as exc:
            reason = redact(str(exc) or type(exc).__name__, [self._token])
            return HealthResult(
                "unreachable",
                f"Joplin Data API not reachable ({reason}); is the Web Clipper service enabled?",
                now,
            )

        if resp.status_code in (401, 403):
            return HealthResult("unauthorized", "Joplin rejected the API token (JOPLIN_TOKEN)", now)
        if resp.status_code != 200:
            # Includes redirects (e.g. a proxy's login page): not proof the token works.
            return HealthResult("error", f"Joplin returned HTTP {resp.status_code}", now)
        try:
            body = resp.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            return HealthResult("error", "Joplin returned a non-JSON response for /folders", now)
        return HealthResult("ok", "Joplin reachable and token accepted", now)

    @staticmethod
    def _log_transition(previous: HealthResult | None, current: HealthResult) -> None:
        if previous is not None and previous.joplin == current.joplin:
            return
        if current.ok:
            logger.info("Health: %s", current.detail)
        else:
            logger.warning("Health: UNHEALTHY (%s): %s", current.joplin, current.detail)
