"""ASGI app hosting the MCP Streamable HTTP endpoint."""

from __future__ import annotations

import contextlib
import secrets
from collections.abc import AsyncIterator

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from .mcp_server import create_mcp_server
from .settings import Settings


class ApiKeyMiddleware:
    """Require ``X-API-Key`` on every HTTP request except health/discovery probes.

    Plain ASGI rather than ``BaseHTTPMiddleware``: it never buffers or wraps the
    response, so long-lived streamed responses pass straight through.
    """

    def __init__(self, app: ASGIApp, *, api_key: str) -> None:
        self._app = app
        self._api_key = api_key.encode("utf-8")

    @staticmethod
    def _bypass_auth(path: str) -> bool:
        # Allow unauthenticated health checks and OAuth discovery probes.
        # Some MCP clients probe these endpoints before sending custom headers.
        return path == "/health" or path.startswith("/.well-known/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._bypass_auth(scope.get("path", "")):
            await self._app(scope, receive, send)
            return

        presented = b""
        for name, value in scope.get("headers", []):
            if name == b"x-api-key":
                presented = value
                break
        if not presented or not secrets.compare_digest(presented, self._api_key):
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)


async def health(_: Request) -> Response:
    return JSONResponse({"ok": True})


def create_app(settings: Settings | None = None) -> Starlette:
    settings = settings or Settings()
    mcp = create_mcp_server(settings)

    # MCP 2.x: transport options live here, not on the MCPServer constructor.
    # Stateless + JSON keeps legacy (pre-2026-07-28) clients session-free too;
    # 2026-07-28 clients are stateless by protocol. `host` drives the SDK's DNS
    # rebinding protection (on by default for localhost binds).
    mcp_app = mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        host=settings.mcp_host,
    )

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        # A mounted sub-app's lifespan never runs, so drive the session manager
        # from here. It only exists once streamable_http_app() has been called.
        async with mcp.session_manager.run():
            yield

    app = Starlette(
        routes=[
            Route("/health", endpoint=health, methods=["GET"]),
            # The MCP sub-app serves its endpoint at /mcp.
            Mount("/", app=mcp_app),
        ],
        lifespan=lifespan,
    )
    app.add_middleware(ApiKeyMiddleware, api_key=settings.mcp_api_key)
    return app
