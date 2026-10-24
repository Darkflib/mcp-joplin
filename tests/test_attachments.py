"""Binary attachments: the joplin-resource:// template and the resources_read tool."""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import respx
from mcp import Client
from mcp.types import (
    AudioContent,
    BlobResourceContents,
    EmbeddedResource,
    ImageContent,
    TextContent,
    TextResourceContents,
)

from mcp_joplin_streamable_sse.errors import AttachmentTooLargeError
from mcp_joplin_streamable_sse.joplin_client import JoplinClient
from mcp_joplin_streamable_sse.mcp_server import create_mcp_server
from mcp_joplin_streamable_sse.settings import Settings

JOPLIN = "http://127.0.0.1:41184"
RID = "0123456789abcdef0123456789abcdef"
MODES = ["legacy", "2026-07-28"]
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256))


def make_settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    monkeypatch.setenv("JOPLIN_TOKEN", "joplin-token-0123456789")
    monkeypatch.setenv("MCP_API_KEY", "test-api-key-123456")
    monkeypatch.setenv("MCP_EVENTS_POLL_SECONDS", "0")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    return make_settings(monkeypatch)


def mock_attachment(
    data: bytes, mime: str | None, *, size: int | None = None, filename: str = "file"
) -> respx.Route:
    """Mock the metadata and file endpoints; return the file route."""
    meta: dict[str, Any] = {"id": RID, "title": filename, "filename": filename}
    if mime is not None:
        meta["mime"] = mime
    meta["size"] = len(data) if size is None else size
    respx.get(f"{JOPLIN}/resources/{RID}").mock(return_value=httpx.Response(200, json=meta))
    return respx.get(f"{JOPLIN}/resources/{RID}/file").mock(
        return_value=httpx.Response(200, content=data)
    )


# ------------------------------------------------------------ resource template


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_resource_read_serves_bytes_with_attachment_mime(
    settings: Settings, mode: str
) -> None:
    mock_attachment(PNG, "image/png")
    async with Client(create_mcp_server(settings), mode=mode) as client:
        result = await client.read_resource(f"joplin-resource://{RID}")
    (contents,) = result.contents
    assert isinstance(contents, BlobResourceContents)
    # Per-attachment MIME type, not the template's static fallback.
    assert contents.mime_type == "image/png"
    assert base64.b64decode(contents.blob) == PNG


@respx.mock
async def test_resource_read_falls_back_on_junk_mime(settings: Settings) -> None:
    mock_attachment(b"\x00\x01", "not a mime type")
    async with Client(create_mcp_server(settings)) as client:
        result = await client.read_resource(f"joplin-resource://{RID}")
    assert result.contents[0].mime_type == "application/octet-stream"


@respx.mock
async def test_resource_read_strips_mime_parameters(settings: Settings) -> None:
    mock_attachment(b"hi", "Text/Plain; charset=utf-8")
    async with Client(create_mcp_server(settings)) as client:
        result = await client.read_resource(f"joplin-resource://{RID}")
    assert result.contents[0].mime_type == "text/plain"


@respx.mock
async def test_resource_read_refuses_oversized_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = make_settings(monkeypatch, MCP_MAX_ATTACHMENT_BYTES="100")
    file_route = mock_attachment(b"x" * 101, "application/pdf")
    async with Client(create_mcp_server(settings)) as client:
        with pytest.raises(Exception) as excinfo:
            await client.read_resource(f"joplin-resource://{RID}")
    assert "100-byte attachment limit" in str(excinfo.value)
    # Refused from the metadata alone: the file was never fetched.
    assert file_route.call_count == 0


# -------------------------------------------------------------- resources_read


async def call_read(settings: Settings, mode: str = "2026-07-28") -> Any:
    async with Client(create_mcp_server(settings), mode=mode) as client:
        return await client.call_tool("resources_read", {"resource_id": RID})


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_resources_read_returns_viewable_image(settings: Settings, mode: str) -> None:
    mock_attachment(PNG, "image/png", filename="chart.png")
    result = await call_read(settings, mode)
    assert not result.is_error
    summary, image = result.content
    assert isinstance(summary, TextContent)
    assert "chart.png" in summary.text and "image/png" in summary.text
    assert isinstance(image, ImageContent)
    assert image.mime_type == "image/png"
    assert base64.b64decode(image.data) == PNG


@respx.mock
async def test_resources_read_returns_audio(settings: Settings) -> None:
    mock_attachment(b"ID3fake", "audio/mpeg")
    result = await call_read(settings)
    assert isinstance(result.content[1], AudioContent)
    assert result.content[1].mime_type == "audio/mpeg"


@pytest.mark.parametrize(
    ("mime", "data"),
    [
        ("text/markdown", "# Heading\n\ncafé".encode()),
        ("application/json", b'{"a": 1}'),
        ("image/svg+xml", b"<svg/>"),  # an image, but not one to send as pixels
    ],
)
@respx.mock
async def test_resources_read_returns_text_files_as_text(
    settings: Settings, mime: str, data: bytes
) -> None:
    mock_attachment(data, mime)
    result = await call_read(settings)
    block = result.content[1]
    assert isinstance(block, EmbeddedResource)
    assert isinstance(block.resource, TextResourceContents)
    assert block.resource.text == data.decode()
    assert block.resource.uri == f"joplin-resource://{RID}"


@pytest.mark.parametrize(
    ("mime", "data"),
    [
        ("application/pdf", b"%PDF-1.7\x00\xff"),
        ("image/tiff", b"II*\x00"),
        ("text/plain", b"\xff\xfe\x00not utf-8"),  # mislabelled binary
    ],
)
@respx.mock
async def test_resources_read_returns_other_files_as_blobs(
    settings: Settings, mime: str, data: bytes
) -> None:
    mock_attachment(data, mime)
    result = await call_read(settings)
    block = result.content[1]
    assert isinstance(block, EmbeddedResource)
    assert isinstance(block.resource, BlobResourceContents)
    assert block.resource.mime_type == mime
    assert base64.b64decode(block.resource.blob) == data


@respx.mock
async def test_resources_read_refuses_by_metadata_size(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = make_settings(monkeypatch, MCP_MAX_ATTACHMENT_BYTES="1000")
    file_route = mock_attachment(b"tiny", "image/png", size=5000)
    result = await call_read(settings)
    assert result.is_error
    assert "1000-byte attachment limit (5000 bytes)" in result.content[0].text
    assert file_route.call_count == 0


@respx.mock
async def test_resources_read_refuses_when_metadata_understates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(monkeypatch, MCP_MAX_ATTACHMENT_BYTES="1000")
    mock_attachment(b"x" * 2000, "image/png", size=10)
    result = await call_read(settings)
    assert result.is_error
    assert "1000-byte attachment limit" in result.content[0].text


@respx.mock
async def test_resources_read_rejects_malformed_id(settings: Settings) -> None:
    route = respx.get(url__regex=rf"{JOPLIN}/.*").mock(return_value=httpx.Response(500))
    async with Client(create_mcp_server(settings)) as client:
        result = await client.call_tool("resources_read", {"resource_id": "../notes"})
    assert result.is_error
    assert route.call_count == 0


@respx.mock
async def test_resources_get_content_is_unchanged_and_uncapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Least surprise: the original base64 tool keeps its shape and ignores the cap.
    settings = make_settings(monkeypatch, MCP_MAX_ATTACHMENT_BYTES="10")
    mock_attachment(PNG, "image/png", filename="chart.png")
    async with Client(create_mcp_server(settings)) as client:
        result = await client.call_tool("resources_get_content", {"resource_id": RID})
    assert not result.is_error
    assert result.structured_content is not None
    assert base64.b64decode(result.structured_content["data_base64"]) == PNG
    assert result.structured_content["mime"] == "image/png"


# ------------------------------------------------------- JoplinClient.download


async def chunks(n: int, size: int) -> AsyncIterator[bytes]:
    for _ in range(n):
        yield b"x" * size


@respx.mock
async def test_download_caps_streamed_body_without_content_length() -> None:
    # No Content-Length: only counting the stream can catch it.
    respx.get(f"{JOPLIN}/resources/{RID}/file").mock(
        return_value=httpx.Response(200, content=chunks(10, 100))
    )
    client = JoplinClient(base_url=JOPLIN, token="joplin-token-0123456789")
    try:
        with pytest.raises(AttachmentTooLargeError) as excinfo:
            await client.download(f"/resources/{RID}/file", max_bytes=250)
    finally:
        await client.aclose()
    assert "joplin-token" not in str(excinfo.value)


@respx.mock
async def test_download_returns_body_within_cap() -> None:
    respx.get(f"{JOPLIN}/resources/{RID}/file").mock(
        return_value=httpx.Response(200, content=chunks(3, 100))
    )
    client = JoplinClient(base_url=JOPLIN, token="joplin-token-0123456789")
    try:
        assert await client.download(f"/resources/{RID}/file", max_bytes=300) == b"x" * 300
    finally:
        await client.aclose()


@respx.mock
async def test_download_error_is_token_free() -> None:
    respx.get(f"{JOPLIN}/resources/{RID}/file").mock(
        return_value=httpx.Response(404, text="no such file for joplin-token-0123456789")
    )
    client = JoplinClient(base_url=JOPLIN, token="joplin-token-0123456789")
    try:
        with pytest.raises(Exception) as excinfo:
            await client.download(f"/resources/{RID}/file", max_bytes=300)
    finally:
        await client.aclose()
    assert "404" in str(excinfo.value)
    assert "joplin-token-0123456789" not in str(excinfo.value)
