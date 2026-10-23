"""Async client for the Joplin Data API (Web Clipper)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from .errors import JoplinApiError, JoplinConnectionError
from .redaction import redact


class JoplinClient:
    """Thin wrapper around Joplin's REST API."""

    def __init__(self, *, base_url: str, token: str, timeout_seconds: float = 15.0) -> None:
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _send(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        files: Any = None,
    ) -> httpx.Response:
        """Send a request with the token attached; raise token-free errors on failure."""
        method = method.upper()
        url_path = path if path.startswith("/") else f"/{path}"
        q = dict(params or {})
        q["token"] = self._token

        try:
            resp = await self._client.request(
                method, url_path, params=q, json=json_body, files=files
            )
        except httpx.HTTPError as exc:
            # `from None`: the httpx exception's context can carry the full URL.
            reason = redact(str(exc) or type(exc).__name__, [self._token])
            raise JoplinConnectionError(method=method, path=url_path, reason=reason) from None

        if resp.status_code >= 400:
            raise JoplinApiError(
                status_code=resp.status_code,
                method=method,
                path=url_path,
                detail=redact((resp.text or "").strip(), [self._token]),
            )
        return resp

    def _json_object(self, resp: httpx.Response, method: str, path: str) -> dict[str, Any]:
        # Joplin always returns JSON for API routes.
        try:
            data = resp.json()
        except ValueError:
            raise JoplinApiError(
                status_code=resp.status_code,
                method=method.upper(),
                path=path,
                detail="Response was not valid JSON",
            ) from None
        if not isinstance(data, dict):
            raise JoplinApiError(
                status_code=resp.status_code,
                method=method.upper(),
                path=path,
                detail=f"Unexpected JSON type: {type(data).__name__}",
            )
        return data

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resp = await self._send(method, path, params=params, json_body=json_body)
        return self._json_object(resp, method, path)

    async def get_paged(
        self,
        path: str,
        *,
        page: int = 1,
        limit: int = 20,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        q = dict(params or {})
        q.update({"page": page, "limit": limit})
        return await self.request_json("GET", path, params=q)

    async def request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        resp = await self._send(method, path, params=params)
        return resp.content, dict(resp.headers)

    async def create_resource(
        self,
        *,
        filename: str,
        data: bytes,
        mime: str,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Create a Joplin resource (attachment) via multipart upload."""
        files = {
            "data": (filename, data, mime),
            "props": (None, json.dumps({"title": title or filename})),
        }
        resp = await self._send("POST", "/resources", files=files)
        return self._json_object(resp, "POST", "/resources")
