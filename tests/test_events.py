"""Joplin /events → subscriptions/listen note-change feed."""

from __future__ import annotations

import logging
from typing import Any

import anyio
import httpx
import pytest
import respx
from mcp import Client
from mcp.server.subscriptions import ResourceUpdated, ServerEvent
from pydantic import ValidationError

from mcp_joplin_streamable_sse.events import (
    ListenerTrackingBus,
    NoteEventPoller,
)
from mcp_joplin_streamable_sse.joplin_client import JoplinClient
from mcp_joplin_streamable_sse.mcp_server import create_mcp_server
from mcp_joplin_streamable_sse.settings import Settings

JOPLIN = "http://127.0.0.1:41184"
TOKEN = "joplin-token-0123456789"


def event(item_id: str, *, item_type: int = 1, change: int = 2) -> dict[str, Any]:
    return {"id": 1, "item_type": item_type, "item_id": item_id, "type": change}


def events_feed(pages: dict[str | None, dict[str, Any]]) -> respx.Route:
    """Mock /events keyed by the cursor sent (None = no cursor = 'latest')."""

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        if cursor not in pages:
            return httpx.Response(200, json={"items": [], "has_more": False, "cursor": cursor})
        return httpx.Response(200, json=pages[cursor])

    return respx.get(f"{JOPLIN}/events").mock(side_effect=handler)


@pytest.fixture
async def joplin() -> Any:
    client = JoplinClient(base_url=JOPLIN, token=TOKEN)
    yield client
    await client.aclose()


# ------------------------------------------------------------------- the bus


def test_bus_counts_listeners_and_unsubscribe_is_idempotent() -> None:
    bus = ListenerTrackingBus()
    assert not bus.has_listeners
    unsub_a = bus.subscribe(lambda e: None)
    unsub_b = bus.subscribe(lambda e: None)
    unsub_a()
    unsub_a()  # a second call must not under-count
    assert bus.has_listeners
    unsub_b()
    assert not bus.has_listeners


async def test_wait_for_listeners_wakes_on_subscribe() -> None:
    bus = ListenerTrackingBus()
    woke = anyio.Event()

    async def waiter() -> None:
        await bus.wait_for_listeners()
        woke.set()

    async with anyio.create_task_group() as tg:
        tg.start_soon(waiter)
        await anyio.sleep(0.01)
        assert not woke.is_set()
        bus.subscribe(lambda e: None)
        with anyio.fail_after(1):
            await woke.wait()


# ------------------------------------------------------------------ poll_once


@respx.mock
async def test_poll_once_dedupes_filters_and_follows_pages(joplin: JoplinClient) -> None:
    events_feed(
        {
            "10": {
                "items": [event("n1"), event("n2"), event("n1"), event("f1", item_type=2)],
                "has_more": True,
                "cursor": "14",
            },
            "14": {
                "items": [event("n3", change=3), event("n2")],
                "has_more": False,
                "cursor": "16",
            },
        }
    )
    poller = NoteEventPoller(joplin, ListenerTrackingBus(), interval_seconds=1)
    cursor, note_ids = await poller.poll_once("10")
    assert cursor == "16"
    assert note_ids == ["n1", "n2", "n3"]  # deletions count; non-notes don't


@respx.mock
async def test_poll_once_stops_on_empty_page_claiming_more(joplin: JoplinClient) -> None:
    route = events_feed({"10": {"items": [], "has_more": True, "cursor": "10"}})
    poller = NoteEventPoller(joplin, ListenerTrackingBus(), interval_seconds=1)
    assert await poller.poll_once("10") == ("10", [])
    assert route.call_count == 1


@respx.mock
async def test_latest_cursor_requires_a_cursor(joplin: JoplinClient) -> None:
    respx.get(f"{JOPLIN}/events").mock(return_value=httpx.Response(200, json={"items": []}))
    poller = NoteEventPoller(joplin, ListenerTrackingBus(), interval_seconds=1)
    with pytest.raises(Exception, match="no cursor"):
        await poller.latest_cursor()


# ------------------------------------------------------------------------ run


async def collect_events(
    bus: ListenerTrackingBus, poller: NoteEventPoller, want: int
) -> list[ServerEvent]:
    received: list[ServerEvent] = []
    done = anyio.Event()

    def listener(e: ServerEvent) -> None:
        received.append(e)
        if len(received) >= want:
            done.set()

    bus.subscribe(listener)
    async with anyio.create_task_group() as tg:
        tg.start_soon(poller.run)
        with anyio.fail_after(3):
            await done.wait()
        tg.cancel_scope.cancel()
    return received


@respx.mock
async def test_run_starts_from_latest_cursor_and_publishes(joplin: JoplinClient) -> None:
    events_feed(
        {
            None: {"cursor": "10"},
            "10": {"items": [event("n1"), event("n2")], "has_more": False, "cursor": "12"},
        }
    )
    bus = ListenerTrackingBus()
    poller = NoteEventPoller(joplin, bus, interval_seconds=0.01)
    received = await collect_events(bus, poller, want=2)
    assert received == [
        ResourceUpdated(uri="joplin-note://n1"),
        ResourceUpdated(uri="joplin-note://n2"),
    ]


@respx.mock
async def test_run_idles_without_listeners(joplin: JoplinClient) -> None:
    route = events_feed({None: {"cursor": "10"}})
    poller = NoteEventPoller(joplin, ListenerTrackingBus(), interval_seconds=0.01)
    async with anyio.create_task_group() as tg:
        tg.start_soon(poller.run)
        await anyio.sleep(0.1)
        tg.cancel_scope.cancel()
    assert route.call_count == 0


@respx.mock
async def test_run_reanchors_after_client_error_and_logs_once(
    joplin: JoplinClient, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        calls.append(cursor)
        if cursor is None:
            # First anchor at 5; after the 4xx, re-anchor at 20.
            return httpx.Response(200, json={"cursor": "5" if len(calls) == 1 else "20"})
        if cursor == "5":
            return httpx.Response(400, text="Invalid cursor")
        return httpx.Response(200, json={"items": [event("n9")], "has_more": False, "cursor": "21"})

    respx.get(f"{JOPLIN}/events").mock(side_effect=handler)
    bus = ListenerTrackingBus()
    poller = NoteEventPoller(joplin, bus, interval_seconds=0.01, max_backoff_seconds=0.02)
    with caplog.at_level(logging.INFO, logger="mcp_joplin_streamable_sse.events"):
        received = await collect_events(bus, poller, want=1)
    assert received == [ResourceUpdated(uri="joplin-note://n9")]
    assert calls[:4] == [None, "5", None, "20"]
    messages = [r.getMessage() for r in caplog.records]
    assert sum("failing" in m for m in messages) == 1
    assert any("recovered" in m for m in messages)
    assert not any(TOKEN in m for m in messages)


@respx.mock
async def test_run_survives_connection_errors(joplin: JoplinClient) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise httpx.ConnectError("refused")
        if "cursor" not in request.url.params:
            return httpx.Response(200, json={"cursor": "1"})
        return httpx.Response(200, json={"items": [event("n1")], "has_more": False, "cursor": "2"})

    respx.get(f"{JOPLIN}/events").mock(side_effect=handler)
    bus = ListenerTrackingBus()
    poller = NoteEventPoller(joplin, bus, interval_seconds=0.01, max_backoff_seconds=0.02)
    assert await collect_events(bus, poller, want=1) == [ResourceUpdated(uri="joplin-note://n1")]


# ------------------------------------------------------- end to end, over MCP


def make_settings(monkeypatch: pytest.MonkeyPatch, poll: str) -> Settings:
    monkeypatch.setenv("JOPLIN_TOKEN", TOKEN)
    monkeypatch.setenv("MCP_API_KEY", "test-api-key-123456")
    monkeypatch.setenv("MCP_EVENTS_POLL_SECONDS", poll)
    return Settings(_env_file=None)


@respx.mock
async def test_listen_receives_note_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    events_feed(
        {
            None: {"cursor": "10"},
            "10": {
                "items": [event("other"), event("n1")],
                "has_more": False,
                "cursor": "12",
            },
        }
    )
    server = create_mcp_server(make_settings(monkeypatch, "0.5"))
    async with Client(server, mode="2026-07-28") as client:
        async with client.listen(resource_subscriptions=["joplin-note://n1"]) as sub:
            with anyio.fail_after(5):
                async for got in sub:
                    received = got
                    break
    # Only the subscribed note; "other" changed too but wasn't asked for.
    assert received == ResourceUpdated(uri="joplin-note://n1")


@respx.mock
async def test_feed_disabled_by_zero_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    route = events_feed({None: {"cursor": "10"}})
    server = create_mcp_server(make_settings(monkeypatch, "0"))
    async with Client(server, mode="2026-07-28") as client:
        async with client.listen(resource_subscriptions=["joplin-note://n1"]):
            await anyio.sleep(0.2)
    assert route.call_count == 0


@pytest.mark.parametrize("value", ["0.1", "-1"])
def test_poll_interval_floor(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(monkeypatch, value)
