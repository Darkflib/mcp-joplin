"""The Joplin token must never reach MCP clients or log output."""

from __future__ import annotations

import logging
import sys

import httpx
import pytest
import respx
from mcp import Client

from mcp_joplin_streamable_sse.errors import JoplinApiError, JoplinConnectionError
from mcp_joplin_streamable_sse.joplin_client import JoplinClient
from mcp_joplin_streamable_sse.mcp_server import create_mcp_server
from mcp_joplin_streamable_sse.redaction import RedactingFilter, install_log_redaction, redact
from mcp_joplin_streamable_sse.settings import Settings

TOKEN = "SECRET-joplin-token-0123456789"
BASE = "http://127.0.0.1:41184"


def test_redact_masks_token_query_param_and_literal() -> None:
    url = f"{BASE}/notes/abc?fields=id&token={TOKEN}&page=2"
    assert TOKEN not in redact(url)
    assert "token=***&page=2" in redact(url)
    assert redact(f"echo {TOKEN} back", [TOKEN]) == "echo *** back"
    # Short values are ignored rather than mangling unrelated text.
    assert redact("a b c", ["a"]) == "a b c"


def test_redacting_filter_scrubs_args_and_tracebacks() -> None:
    record = logging.LogRecord(
        "x", logging.INFO, __file__, 1, "GET %s", (f"/n?token={TOKEN}",), None
    )
    RedactingFilter([TOKEN]).filter(record)
    assert TOKEN not in record.getMessage()

    try:
        raise RuntimeError(f"boom {TOKEN}")
    except RuntimeError:
        exc_record = logging.LogRecord(
            "x", logging.ERROR, __file__, 1, "failed", None, sys.exc_info()
        )
    RedactingFilter([TOKEN]).filter(exc_record)
    assert exc_record.exc_text is not None
    assert TOKEN not in exc_record.exc_text


@respx.mock
async def test_api_error_message_has_no_token() -> None:
    respx.get(f"{BASE}/notes/abc").mock(
        return_value=httpx.Response(404, text=f"Not found: /notes/abc?token={TOKEN}")
    )
    client = JoplinClient(base_url=BASE, token=TOKEN)
    try:
        with pytest.raises(JoplinApiError) as excinfo:
            await client.request_json("GET", "/notes/abc")
    finally:
        await client.aclose()
    message = str(excinfo.value)
    assert TOKEN not in message
    assert "404" in message
    assert "/notes/abc" in message


@respx.mock
async def test_connection_error_has_no_token() -> None:
    respx.get(f"{BASE}/notes/abc").mock(side_effect=httpx.ConnectError(f"refused {TOKEN}"))
    client = JoplinClient(base_url=BASE, token=TOKEN)
    try:
        with pytest.raises(JoplinConnectionError) as excinfo:
            await client.request_json("GET", "/notes/abc")
    finally:
        await client.aclose()
    assert TOKEN not in str(excinfo.value)
    assert excinfo.value.__suppress_context__


@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
@respx.mock
async def test_tool_error_and_logs_have_no_token(
    mode: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("JOPLIN_TOKEN", TOKEN)
    monkeypatch.setenv("MCP_API_KEY", "test-api-key-123456")
    respx.get(f"{BASE}/notes/abc").mock(return_value=httpx.Response(404, text="Not found"))
    respx.get(f"{BASE}/notes/ok").mock(
        return_value=httpx.Response(200, json={"id": "ok", "title": "t", "body": "b"})
    )

    mcp = create_mcp_server(Settings())
    caplog.set_level(logging.DEBUG)
    install_log_redaction([TOKEN])

    async with Client(mcp, mode=mode) as client:
        ok = await client.call_tool("notes_get", {"note_id": "ok"})
        assert not ok.is_error
        failed = await client.call_tool("notes_get", {"note_id": "abc"})

    assert failed.is_error
    text = " ".join(getattr(c, "text", "") for c in failed.content)
    # The Joplin error is surfaced (not an opaque "Error executing tool") ...
    assert "404" in text
    # ... without the token.
    assert TOKEN not in text
    assert TOKEN not in caplog.text


def test_repeat_install_extends_secrets_on_existing_handlers() -> None:
    handler = logging.StreamHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        install_log_redaction(["first-secret-0123456789"])
        install_log_redaction(["second-secret-0123456789"])
        filters = [f for f in handler.filters if isinstance(f, RedactingFilter)]
        assert len(filters) == 1
        record = logging.LogRecord(
            "x",
            logging.INFO,
            __file__,
            1,
            "%s %s",
            ("first-secret-0123456789", "second-secret-0123456789"),
            None,
        )
        filters[0].filter(record)
        assert record.getMessage() == "*** ***"
    finally:
        root.removeHandler(handler)


@respx.mock
async def test_caller_supplied_token_in_path_is_redacted() -> None:
    respx.get(f"{BASE}/notes/x").mock(return_value=httpx.Response(404, text="Not found"))
    client = JoplinClient(base_url=BASE, token=TOKEN)
    try:
        with pytest.raises(JoplinApiError) as excinfo:
            await client.request_json("GET", f"/notes/x?token={TOKEN}")
    finally:
        await client.aclose()
    assert TOKEN not in str(excinfo.value)
