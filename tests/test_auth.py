from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from mcp_joplin_streamable_sse.asgi import create_app


def test_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOPLIN_TOKEN", "t")
    monkeypatch.setenv("MCP_API_KEY", "test-api-key-123456")
    app = create_app()
    with TestClient(app) as client:
        # Health checks are intentionally unauthenticated.
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True}

        # MCP endpoint is protected by X-API-Key.
        r2 = client.get("/mcp")
        assert r2.status_code == 401

        r3 = client.get("/mcp", headers={"x-api-key": "test-api-key-123456"})
        assert r3.status_code != 401
