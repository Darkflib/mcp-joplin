"""MCP_CONFIRM_DELETES: asking the user before a delete (elicitation)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from mcp import Client, types
from mcp.client.streamable_http import streamable_http_client

from mcp_joplin.asgi import create_app
from mcp_joplin.mcp_server import create_mcp_server
from mcp_joplin.settings import Settings

JOPLIN = "http://127.0.0.1:41184"
RID = "0123456789abcdef0123456789abcdef"
MODES = ["legacy", "2026-07-28"]

# tool, args, item path, title field(s) returned by the lookup, words the prompt must contain
DELETES: list[tuple[str, dict[str, Any], str, dict[str, Any], str]] = [
    ("notes_delete", {"note_id": "n1"}, "/notes/n1", {"title": "Q3 plan"}, "note “Q3 plan”"),
    (
        "folders_delete",
        {"folder_id": "f1"},
        "/folders/f1",
        {"title": "Work"},
        "notebook “Work” and every note",
    ),
    ("tags_delete", {"tag_id": "t1"}, "/tags/t1", {"title": "urgent"}, "tag “urgent”"),
    (
        "resources_delete",
        {"resource_id": RID},
        f"/resources/{RID}",
        {"title": "x", "filename": "chart.png"},
        "attachment “chart.png”",
    ),
]


def make_settings(monkeypatch: pytest.MonkeyPatch, mode: str | None) -> Settings:
    monkeypatch.setenv("JOPLIN_TOKEN", "joplin-token-0123456789")
    monkeypatch.setenv("MCP_API_KEY", "test-api-key-123456")
    monkeypatch.setenv("MCP_EVENTS_POLL_SECONDS", "0")
    # mode=None must mean the default, whatever the developer's shell exports.
    monkeypatch.delenv("MCP_CONFIRM_DELETES", raising=False)
    if mode is not None:
        monkeypatch.setenv("MCP_CONFIRM_DELETES", mode)
    return Settings(_env_file=None)


class Answer:
    """An elicitation callback that records what it was asked."""

    def __init__(self, action: str, content: dict[str, Any] | None = None) -> None:
        self.action = action
        self.content = content
        self.asked: list[str] = []

    async def __call__(self, context: Any, params: types.ElicitRequestParams) -> types.ElicitResult:
        self.asked.append(params.message)
        return types.ElicitResult(action=self.action, content=self.content)


def mock_item(path: str, item: dict[str, Any]) -> tuple[respx.Route, respx.Route]:
    lookup = respx.get(f"{JOPLIN}{path}").mock(return_value=httpx.Response(200, json=item))
    delete = respx.delete(f"{JOPLIN}{path}").mock(return_value=httpx.Response(200, text=""))
    return lookup, delete


def text_of(result: Any) -> str:
    return " ".join(getattr(c, "text", "") for c in result.content)


async def test_confirmation_is_not_a_model_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    async with Client(create_mcp_server(make_settings(monkeypatch, "ask"))) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    for tool, *_ in DELETES:
        assert "confirmation" not in tools[tool].input_schema.get("properties", {}), tool


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_off_by_default_deletes_without_asking(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    lookup, delete = mock_item("/notes/n1", {"title": "T"})
    answer = Answer("decline")
    server = create_mcp_server(make_settings(monkeypatch, None))
    async with Client(server, mode=mode, elicitation_callback=answer) as client:
        result = await client.call_tool("notes_delete", {"note_id": "n1"})
    assert not result.is_error
    assert answer.asked == []
    assert lookup.call_count == 0  # no extra Joplin traffic when off
    assert delete.call_count == 1


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize(("tool", "args", "path", "item", "words"), DELETES)
@respx.mock
async def test_ask_and_accept_deletes(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    tool: str,
    args: dict[str, Any],
    path: str,
    item: dict[str, Any],
    words: str,
) -> None:
    _, delete = mock_item(path, item)
    answer = Answer("accept", {"confirm": True})
    server = create_mcp_server(make_settings(monkeypatch, "ask"))
    async with Client(server, mode=mode, elicitation_callback=answer) as client:
        result = await client.call_tool(tool, args)
    assert not result.is_error, text_of(result)
    assert len(answer.asked) == 1
    assert words in answer.asked[0]
    assert delete.call_count == 1


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize(
    ("action", "content"),
    [
        ("decline", None),
        ("cancel", None),
        ("accept", {"confirm": False}),
        # Accepted without the field: the box defaults to unticked, so no delete.
        ("accept", {}),
    ],
)
@respx.mock
async def test_ask_and_refuse_keeps_the_item(
    monkeypatch: pytest.MonkeyPatch, mode: str, action: str, content: dict[str, Any] | None
) -> None:
    _, delete = mock_item("/notes/n1", {"title": "Q3 plan"})
    answer = Answer(action, content)
    server = create_mcp_server(make_settings(monkeypatch, "ask"))
    async with Client(server, mode=mode, elicitation_callback=answer) as client:
        result = await client.call_tool("notes_delete", {"note_id": "n1"})
    assert result.is_error
    assert "Not deleted" in text_of(result)
    assert delete.call_count == 0


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_ask_without_client_support_deletes_as_before(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    lookup, delete = mock_item("/notes/n1", {"title": "T"})
    server = create_mcp_server(make_settings(monkeypatch, "ask"))
    async with Client(server, mode=mode) as client:  # no elicitation callback
        result = await client.call_tool("notes_delete", {"note_id": "n1"})
    assert not result.is_error, text_of(result)
    assert lookup.call_count == 0
    assert delete.call_count == 1


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_require_without_client_support_refuses(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    _, delete = mock_item("/notes/n1", {"title": "T"})
    server = create_mcp_server(make_settings(monkeypatch, "require"))
    async with Client(server, mode=mode) as client:
        result = await client.call_tool("notes_delete", {"note_id": "n1"})
    assert result.is_error
    assert "MCP_CONFIRM_DELETES=require" in text_of(result)
    assert delete.call_count == 0


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_require_with_client_support_asks(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    _, delete = mock_item("/notes/n1", {"title": "T"})
    answer = Answer("accept", {"confirm": True})
    server = create_mcp_server(make_settings(monkeypatch, "require"))
    async with Client(server, mode=mode, elicitation_callback=answer) as client:
        result = await client.call_tool("notes_delete", {"note_id": "n1"})
    assert not result.is_error, text_of(result)
    assert len(answer.asked) == 1
    assert delete.call_count == 1


@respx.mock
async def test_missing_item_is_reported_before_asking(monkeypatch: pytest.MonkeyPatch) -> None:
    respx.get(f"{JOPLIN}/notes/gone").mock(return_value=httpx.Response(404, text="Not found"))
    delete = respx.delete(f"{JOPLIN}/notes/gone").mock(return_value=httpx.Response(200))
    answer = Answer("accept", {"confirm": True})
    server = create_mcp_server(make_settings(monkeypatch, "ask"))
    async with Client(server, mode="2026-07-28", elicitation_callback=answer) as client:
        result = await client.call_tool("notes_delete", {"note_id": "gone"})
    assert result.is_error
    assert "404" in text_of(result)
    assert answer.asked == []
    assert delete.call_count == 0


def test_rejects_unknown_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError):
        make_settings(monkeypatch, "yes")


# ---------------------------------------------------------------- real HTTP app


SERVER = "http://127.0.0.1:5005"
API_KEY = "test-api-key-123456"


@pytest.mark.parametrize(
    ("mode", "expect_asked"),
    [
        # 2026-07-28 asks via the InputRequiredResult round trip: works statelessly.
        ("2026-07-28", True),
        # Earlier versions would need a server-to-client request mid-call, which a
        # stateless JSON HTTP request can't carry: no prompt, delete as before.
        ("legacy", False),
    ],
)
@respx.mock
async def test_over_stateless_http(
    monkeypatch: pytest.MonkeyPatch, mode: str, expect_asked: bool
) -> None:
    import httpx2

    _, delete = mock_item("/notes/n1", {"title": "Q3 plan"})
    app = create_app(make_settings(monkeypatch, "ask"))
    answer = Answer("accept", {"confirm": True})
    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url=SERVER,
            headers={"X-API-Key": API_KEY},
        ) as hc:
            transport = streamable_http_client(f"{SERVER}/mcp", http_client=hc)
            async with Client(transport, mode=mode, elicitation_callback=answer) as client:
                result = await client.call_tool("notes_delete", {"note_id": "n1"})
    assert not result.is_error, text_of(result)
    assert (len(answer.asked) == 1) is expect_asked
    assert delete.call_count == 1


@pytest.mark.parametrize(
    ("elicitation", "expected"),
    [
        (None, False),
        (types.ElicitationCapability(), True),  # bare {}: pre-modes clients mean form
        (types.ElicitationCapability(form=types.FormElicitationCapability()), True),
        (
            types.ElicitationCapability(
                form=types.FormElicitationCapability(), url=types.UrlElicitationCapability()
            ),
            True,
        ),
        # URL-only clients can't show the confirmation form; the SDK would refuse it.
        (types.ElicitationCapability(url=types.UrlElicitationCapability()), False),
    ],
)
def test_can_ask_needs_form_support(
    elicitation: types.ElicitationCapability | None, expected: bool
) -> None:
    from types import SimpleNamespace

    from mcp_joplin.confirm import _can_ask

    ctx = SimpleNamespace(
        client_capabilities=types.ClientCapabilities(elicitation=elicitation),
        protocol_version="2026-07-28",
        session=SimpleNamespace(can_send_request=False),
    )
    assert _can_ask(ctx) is expected  # type: ignore[arg-type]


async def test_prompt_box_starts_unticked(monkeypatch: pytest.MonkeyPatch) -> None:
    # The form a client renders must not pre-tick Delete.
    seen: list[types.ElicitRequestParams] = []

    async def capture(context: Any, params: types.ElicitRequestParams) -> types.ElicitResult:
        seen.append(params)
        return types.ElicitResult(action="decline")

    with respx.mock:
        mock_item("/notes/n1", {"title": "T"})
        server = create_mcp_server(make_settings(monkeypatch, "ask"))
        async with Client(server, mode="2026-07-28", elicitation_callback=capture) as client:
            await client.call_tool("notes_delete", {"note_id": "n1"})
    schema = seen[0].requested_schema  # type: ignore[union-attr]
    assert schema["properties"]["confirm"]["default"] is False
