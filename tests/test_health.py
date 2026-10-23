"""JoplinHealth: readiness states, caching, probe coalescing, transition logging."""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest
import respx

from mcp_joplin_streamable_sse.health import JoplinHealth

BASE = "http://127.0.0.1:41184"
TOKEN = "SECRET-joplin-token-0123456789"


def make(*, ttl_seconds: float = 15.0) -> JoplinHealth:
    return JoplinHealth(base_url=BASE, token=TOKEN, ttl_seconds=ttl_seconds)


def mock_ping_ok() -> respx.Route:
    return respx.get(f"{BASE}/ping").mock(
        return_value=httpx.Response(200, text="JoplinClipService")
    )


@respx.mock
async def test_ok_when_reachable_and_token_accepted() -> None:
    mock_ping_ok()
    folders = respx.get(f"{BASE}/folders").mock(
        return_value=httpx.Response(200, json={"items": [], "has_more": False})
    )
    checker = make()
    try:
        result = await checker.check()
    finally:
        await checker.aclose()
    assert result.ok
    assert result.joplin == "ok"
    # The token is sent on the authenticated probe ...
    assert folders.calls.last.request.url.params["token"] == TOKEN
    # ... but never surfaces in what /health returns.
    assert TOKEN not in str(result.as_dict())


@pytest.mark.parametrize("status", [401, 403])
@respx.mock
async def test_unauthorized_when_token_rejected(status: int) -> None:
    mock_ping_ok()
    respx.get(f"{BASE}/folders").mock(return_value=httpx.Response(status))
    checker = make()
    try:
        result = await checker.check()
    finally:
        await checker.aclose()
    assert result.joplin == "unauthorized"
    assert "JOPLIN_TOKEN" in result.detail


@respx.mock
async def test_unreachable_on_connection_error() -> None:
    respx.get(f"{BASE}/ping").mock(side_effect=httpx.ConnectError(f"refused ?token={TOKEN}"))
    checker = make()
    try:
        result = await checker.check()
    finally:
        await checker.aclose()
    assert result.joplin == "unreachable"
    assert "Web Clipper" in result.detail
    assert TOKEN not in result.detail


@respx.mock
async def test_error_when_something_else_answers_the_port() -> None:
    respx.get(f"{BASE}/ping").mock(return_value=httpx.Response(200, text="<html>nginx</html>"))
    checker = make()
    try:
        result = await checker.check()
    finally:
        await checker.aclose()
    assert result.joplin == "error"


@respx.mock
async def test_result_is_cached_until_ttl_or_force() -> None:
    ping = mock_ping_ok()
    respx.get(f"{BASE}/folders").mock(return_value=httpx.Response(200, json={"items": []}))
    checker = make(ttl_seconds=60)
    try:
        await checker.check()
        await checker.check()
        assert ping.call_count == 1
        await checker.check(force=True)
        assert ping.call_count == 2
    finally:
        await checker.aclose()


@respx.mock
async def test_concurrent_checks_share_one_probe() -> None:
    async def slow_ping(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.05)
        return httpx.Response(200, text="JoplinClipService")

    ping = respx.get(f"{BASE}/ping").mock(side_effect=slow_ping)
    respx.get(f"{BASE}/folders").mock(return_value=httpx.Response(200, json={"items": []}))
    checker = make(ttl_seconds=60)
    try:
        results = await asyncio.gather(*(checker.check() for _ in range(10)))
    finally:
        await checker.aclose()
    assert ping.call_count == 1
    assert all(r.ok for r in results)


@respx.mock
async def test_transitions_logged_once_each(caplog: pytest.LogCaptureFixture) -> None:
    mock_ping_ok()
    folders = respx.get(f"{BASE}/folders")
    caplog.set_level(logging.INFO, logger="mcp_joplin_streamable_sse.health")
    checker = make(ttl_seconds=0)
    try:
        folders.mock(return_value=httpx.Response(403))
        await checker.check()
        await checker.check()  # same state: no new log line
        folders.mock(return_value=httpx.Response(200, json={"items": []}))
        await checker.check()
    finally:
        await checker.aclose()

    messages = [r.getMessage() for r in caplog.records]
    assert len(messages) == 2
    assert "UNHEALTHY (unauthorized)" in messages[0]
    assert caplog.records[0].levelno == logging.WARNING
    assert "token accepted" in messages[1]
    assert TOKEN not in caplog.text
