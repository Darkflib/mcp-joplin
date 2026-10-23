"""End-to-end over Streamable HTTP through the real ASGI app (auth + both protocol eras)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import httpx2
import pytest
import respx
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from starlette.applications import Starlette

from mcp_joplin_streamable_sse.asgi import create_app
from mcp_joplin_streamable_sse.settings import ConfigError, Settings

API_KEY = "test-api-key-123456"
JOPLIN = "http://127.0.0.1:41184"
# DNS rebinding protection rejects a Host header without a port.
SERVER = "http://127.0.0.1:5005"

MODES = ["legacy", "2026-07-28"]


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Starlette:
    monkeypatch.setenv("JOPLIN_TOKEN", "joplin-token-0123456789")
    monkeypatch.setenv("MCP_API_KEY", API_KEY)
    return create_app(Settings())


@asynccontextmanager
async def running(app: Starlette) -> AsyncIterator[None]:
    # httpx2's ASGITransport doesn't drive lifespan; the session manager needs it.
    async with app.router.lifespan_context(app):
        yield


def http_client(app: Starlette, headers: dict[str, str] | None = None) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url=SERVER, headers=headers
    )


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_tool_call_over_http(app: Starlette, mode: str) -> None:
    respx.get(f"{JOPLIN}/folders").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"id": "a", "title": "Alpha", "parent_id": ""},
                    {"id": "b", "title": "Beta", "parent_id": "a"},
                ],
                "has_more": False,
            },
        )
    )
    async with running(app), http_client(app, {"X-API-Key": API_KEY}) as hc:
        transport = streamable_http_client(f"{SERVER}/mcp", http_client=hc)
        async with Client(transport, mode=mode) as client:
            tools = await client.list_tools()
            assert "notes_get" in {t.name for t in tools.tools}

            result = await client.call_tool("folders_list", {})
            assert not result.is_error
            assert result.structured_content is not None
            assert [i["id"] for i in result.structured_content["items"]] == ["a", "b"]


@pytest.mark.parametrize("mode", MODES)
async def test_wrong_api_key_is_rejected(app: Starlette, mode: str) -> None:
    async with running(app), http_client(app, {"X-API-Key": "nope"}) as hc:
        transport = streamable_http_client(f"{SERVER}/mcp", http_client=hc)
        with pytest.raises(Exception):  # noqa: B017 - SDK surfaces the 401 its own way
            async with Client(transport, mode=mode) as client:
                await client.list_tools()


@respx.mock
async def test_health_needs_no_key_and_mcp_does(app: Starlette) -> None:
    respx.get(f"{JOPLIN}/ping").mock(return_value=httpx.Response(200, text="JoplinClipService"))
    respx.get(f"{JOPLIN}/folders").mock(
        return_value=httpx.Response(200, json={"items": [], "has_more": False})
    )
    async with running(app), http_client(app) as hc:
        r = await hc.get("/health")
        assert r.status_code == 200
        assert r.json()["ok"] is True

        r = await hc.get("/health/live")
        assert r.status_code == 200
        assert r.json() == {"ok": True}

        r = await hc.post("/mcp", json={})
        assert r.status_code == 401

        # Constant-time comparison must not choke on non-ASCII header bytes.
        r = await hc.post("/mcp", json={}, headers=[(b"x-api-key", b"k\xc3\xa9y\xff")])
        assert r.status_code == 401


async def test_dns_rebinding_protection_rejects_foreign_host(app: Starlette) -> None:
    async with running(app), http_client(app, {"X-API-Key": API_KEY}) as hc:
        r = await hc.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Host": "evil.example:5005"},
        )
        assert r.status_code == 421


@respx.mock
async def test_health_is_503_when_joplin_rejects_token(app: Starlette) -> None:
    respx.get(f"{JOPLIN}/ping").mock(return_value=httpx.Response(200, text="JoplinClipService"))
    respx.get(f"{JOPLIN}/folders").mock(return_value=httpx.Response(403, text="Invalid token"))
    async with running(app), http_client(app) as hc:
        r = await hc.get("/health")
        assert r.status_code == 503
        assert r.json()["joplin"] == "unauthorized"
        # Liveness is independent of Joplin.
        assert (await hc.get("/health/live")).status_code == 200


def test_serve_without_api_key_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOPLIN_TOKEN", "joplin-token-0123456789")
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="MCP_API_KEY is not set"):
        create_app(Settings(_env_file=None))


@pytest.mark.parametrize("host", ["localhost:5005", "[::1]:5005"])
async def test_other_loopback_hosts_with_port_are_accepted(app: Starlette, host: str) -> None:
    async with running(app), http_client(app, {"X-API-Key": API_KEY}) as hc:
        r = await hc.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Host": host, "Accept": "application/json, text/event-stream"},
        )
        assert r.status_code != 421


async def test_loopback_host_without_port_is_rejected(app: Starlette) -> None:
    async with running(app), http_client(app, {"X-API-Key": API_KEY}) as hc:
        r = await hc.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Host": "localhost"},
        )
        assert r.status_code == 421
