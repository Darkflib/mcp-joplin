"""Joplin note-change feed → MCP ``subscriptions/listen`` (protocol 2026-07-28).

Joplin has no push API, only a cursor over its change log (``GET /events``).
``NoteEventPoller`` follows that cursor while at least one client is listening
and publishes a ``ResourceUpdated`` for ``joplin-note://{id}`` per changed note;
the SDK's listen handler forwards it to the streams subscribed to that URI.

Legacy (pre-2026-07-28) clients have no listen stream, so they get nothing
from this: they keep reading notes on demand as before.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import anyio
from mcp.server.subscriptions import InMemorySubscriptionBus, ResourceUpdated, ServerEvent

from .errors import JoplinApiError, JoplinConnectionError
from .joplin_client import JoplinClient

logger = logging.getLogger(__name__)

# Joplin's item_type for notes; /events only records note changes today, but
# filter anyway in case that grows.
NOTE_ITEM_TYPE = 1
# Pages of /events read per tick; a larger backlog continues on the next tick.
MAX_PAGES_PER_POLL = 20
MAX_BACKOFF_SECONDS = 60.0


def note_uri(note_id: str) -> str:
    return f"joplin-note://{note_id}"


class ListenerTrackingBus(InMemorySubscriptionBus):
    """The SDK's in-memory bus, plus a count of open listen streams.

    Lets the poller stay idle (no Joplin traffic) until someone is listening.
    """

    def __init__(self) -> None:
        super().__init__()
        self._active = 0
        self._listener_added: anyio.Event | None = None

    @property
    def has_listeners(self) -> bool:
        return self._active > 0

    def subscribe(self, listener: Callable[[ServerEvent], None]) -> Callable[[], None]:
        unsubscribe = super().subscribe(listener)
        self._active += 1
        if self._listener_added is not None:
            self._listener_added.set()
        done = False

        def tracked_unsubscribe() -> None:
            nonlocal done
            # The SDK's unsubscribe is idempotent; keep the count so too.
            if not done:
                done = True
                self._active -= 1
            unsubscribe()

        return tracked_unsubscribe

    async def wait_for_listeners(self) -> None:
        while not self.has_listeners:
            # Created here, not in __init__: an anyio.Event needs a running loop.
            self._listener_added = anyio.Event()
            await self._listener_added.wait()


class NoteEventPoller:
    """Follows Joplin's ``/events`` cursor and publishes note changes to ``bus``."""

    def __init__(
        self,
        joplin: JoplinClient,
        bus: ListenerTrackingBus,
        *,
        interval_seconds: float,
        max_backoff_seconds: float = MAX_BACKOFF_SECONDS,
    ) -> None:
        self._joplin = joplin
        self._bus = bus
        self._interval = interval_seconds
        self._max_backoff = max(max_backoff_seconds, interval_seconds)
        self._cursor: str | None = None

    def _backoff(self, failures: int) -> float:
        # Exponent capped so a long outage can't overflow the float.
        return min(self._interval * float(2 ** min(failures, 16)), self._max_backoff)

    async def latest_cursor(self) -> str:
        """Joplin returns its newest cursor when asked without one."""
        raw = await self._joplin.request_json("GET", "/events")
        cursor = raw.get("cursor")
        if cursor is None or cursor == "":
            raise JoplinApiError(
                status_code=200, method="GET", path="/events", detail="response had no cursor"
            )
        return str(cursor)

    async def poll_once(self, cursor: str) -> tuple[str, list[str]]:
        """Read changes after ``cursor``; return the new cursor and changed note ids.

        Ids are de-duplicated (a note saved ten times since the last tick is
        one update) and kept in first-seen order.
        """
        changed: dict[str, None] = {}
        for _ in range(MAX_PAGES_PER_POLL):
            raw: dict[str, Any] = await self._joplin.request_json(
                "GET", "/events", params={"cursor": cursor}
            )
            items = raw.get("items") or []
            for item in items:
                item_id = item.get("item_id")
                if item.get("item_type") == NOTE_ITEM_TYPE and item_id:
                    changed[str(item_id)] = None
            next_cursor = raw.get("cursor")
            if next_cursor is not None and next_cursor != "":
                cursor = str(next_cursor)
            # An empty page that claims more can't advance; stop rather than spin.
            if not raw.get("has_more") or not items:
                break
        return cursor, list(changed)

    async def run(self) -> None:
        """Poll until cancelled. Never raises: a feed failure must not take the server down."""
        failures = 0
        while True:
            if not self._bus.has_listeners:
                if self._cursor is not None:
                    logger.info("No listeners left; pausing the Joplin events feed")
                    # Start from "now" next time: nobody was listening for the gap.
                    self._cursor = None
                await self._bus.wait_for_listeners()

            delay = self._interval
            try:
                if self._cursor is None:
                    self._cursor = await self.latest_cursor()
                    logger.info("Following Joplin note changes (every %ss)", self._interval)
                else:
                    self._cursor, note_ids = await self.poll_once(self._cursor)
                    for note_id in note_ids:
                        await self._bus.publish(ResourceUpdated(uri=note_uri(note_id)))
                    if note_ids:
                        logger.debug("Published %d note change(s)", len(note_ids))
                if failures:
                    logger.info("Joplin events feed recovered after %d failure(s)", failures)
                    failures = 0
            except (JoplinApiError, JoplinConnectionError) as exc:
                failures += 1
                # Log the transition, not every retry.
                if failures == 1:
                    logger.warning("Joplin events feed failing, backing off: %s", exc)
                if isinstance(exc, JoplinApiError) and 400 <= exc.status_code < 500:
                    # e.g. a cursor Joplin no longer knows (events expire after 90
                    # days); re-anchor on the latest one rather than retry forever.
                    self._cursor = None
                delay = self._backoff(failures)
            except Exception:
                failures += 1
                logger.exception("Unexpected error in the Joplin events feed; continuing")
                self._cursor = None
                delay = self._backoff(failures)
            await anyio.sleep(delay)
