"""Tool annotations, read-only mode, safer note editing and input validation."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from mcp import Client

from mcp_joplin_streamable_sse.mcp_server import create_mcp_server
from mcp_joplin_streamable_sse.settings import Settings

JOPLIN = "http://127.0.0.1:41184"
MODES = ["legacy", "2026-07-28"]

READ_TOOLS = {
    "notes_get",
    "notes_list",
    "folders_list",
    "folders_tree",
    "tags_list",
    "resources_list",
    "resources_get",
    "resources_get_content",
    "resources_read",
    "notes_list_resources",
    "search",
}
DELETE_TOOLS = {"notes_delete", "folders_delete", "tags_delete", "resources_delete"}


def make_settings(monkeypatch: pytest.MonkeyPatch, *, read_only: bool = False) -> Settings:
    monkeypatch.setenv("JOPLIN_TOKEN", "joplin-token-0123456789")
    monkeypatch.setenv("MCP_API_KEY", "test-api-key-123456")
    monkeypatch.setenv("MCP_READ_ONLY", "true" if read_only else "false")
    return Settings(_env_file=None)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    return make_settings(monkeypatch)


def note(body: str, updated_time: int = 100) -> dict[str, Any]:
    return {"id": "n1", "title": "T", "body": body, "parent_id": "p", "updated_time": updated_time}


class FakeNote:
    """A single Joplin note behind GET/PUT /notes/n1; records what was written."""

    def __init__(self, body: str, updated_time: int = 100) -> None:
        self.body = body
        self.updated_time = updated_time
        self.puts: list[dict[str, Any]] = []
        respx.get(f"{JOPLIN}/notes/n1").mock(side_effect=self._get)
        respx.put(f"{JOPLIN}/notes/n1").mock(side_effect=self._put)

    def _get(self, _: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=note(self.body, self.updated_time))

    def _put(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        self.puts.append(payload)
        self.body = payload.get("body", self.body)
        self.updated_time += 1
        return httpx.Response(200, json=note(self.body, self.updated_time))


def text_of(result: Any) -> str:
    return " ".join(getattr(c, "text", "") for c in result.content)


# ---------------------------------------------------------------- annotations


@pytest.mark.parametrize("mode", MODES)
async def test_every_tool_is_annotated_consistently(settings: Settings, mode: str) -> None:
    async with Client(create_mcp_server(settings), mode=mode) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}

    for name, tool in tools.items():
        ann = tool.annotations
        assert ann is not None, name
        assert ann.open_world_hint is False, name
        if name in READ_TOOLS:
            assert ann.read_only_hint is True, name
        else:
            assert ann.read_only_hint is False, name
            assert ann.destructive_hint is not None, name
            assert ann.idempotent_hint is not None, name

    for name in DELETE_TOOLS | {"notes_update", "notes_replace_text", "notes_detach_resource"}:
        assert tools[name].annotations.destructive_hint is True, name  # type: ignore[union-attr]
    for name in ("notes_create", "notes_append", "folders_create", "tags_create"):
        assert tools[name].annotations.destructive_hint is False, name  # type: ignore[union-attr]


# --------------------------------------------------------------- read-only mode


@pytest.mark.parametrize("mode", MODES)
async def test_read_only_mode_registers_only_read_tools(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    server = create_mcp_server(make_settings(monkeypatch, read_only=True))
    async with Client(server, mode=mode) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert names == READ_TOOLS
        # A write tool isn't merely refused; it doesn't exist.
        result = await client.call_tool("notes_delete", {"note_id": "n1"})
    assert result.is_error
    assert "notes_delete" in text_of(result)


async def test_read_only_mode_keeps_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    server = create_mcp_server(make_settings(monkeypatch, read_only=True))
    async with Client(server) as client:
        templates = await client.list_resource_templates()
    assert {t.uri_template for t in templates.resource_templates} == {
        "joplin-note://{note_id}",
        "joplin-folders://tree{?root_id}",
        "joplin-resource://{resource_id}",
    }


# ----------------------------------------------------------------- notes_append


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_append_adds_to_end_without_touching_existing_text(
    settings: Settings, mode: str
) -> None:
    fake = FakeNote("First para.\n\nSecond para.  \n\n\n")
    async with Client(create_mcp_server(settings), mode=mode) as client:
        result = await client.call_tool("notes_append", {"note_id": "n1", "text": "- new item"})
    assert not result.is_error
    # Only the trailing newlines go; the hard line break (two spaces) is kept.
    assert fake.body == "First para.\n\nSecond para.  \n\n- new item\n"


@respx.mock
async def test_append_to_empty_note_has_no_leading_separator(settings: Settings) -> None:
    fake = FakeNote("")
    async with Client(create_mcp_server(settings)) as client:
        await client.call_tool(
            "notes_append", {"note_id": "n1", "text": "hello", "separator": "\n"}
        )
    assert fake.body == "hello\n"


@respx.mock
async def test_append_refuses_stale_edit(settings: Settings) -> None:
    fake = FakeNote("body", updated_time=200)
    async with Client(create_mcp_server(settings)) as client:
        result = await client.call_tool(
            "notes_append", {"note_id": "n1", "text": "x", "expected_updated_time": 150}
        )
    assert result.is_error
    assert "changed since you read it" in text_of(result)
    assert fake.puts == []


# ----------------------------------------------------------- notes_replace_text


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_replace_unique_text(settings: Settings, mode: str) -> None:
    fake = FakeNote("Status: draft\nOwner: me\n")
    async with Client(create_mcp_server(settings), mode=mode) as client:
        result = await client.call_tool(
            "notes_replace_text",
            {"note_id": "n1", "find": "Status: draft", "replace": "Status: final"},
        )
    assert not result.is_error
    assert fake.body == "Status: final\nOwner: me\n"
    assert result.structured_content is not None
    assert result.structured_content["replacements"] == 1


@pytest.mark.parametrize(
    ("body", "find", "message"),
    [
        ("alpha beta", "gamma", "occurs 0 time(s)"),
        ("todo todo", "todo", "occurs 2 time(s)"),
    ],
    ids=["missing", "ambiguous"],
)
@respx.mock
async def test_replace_refuses_missing_or_ambiguous_match(
    settings: Settings, body: str, find: str, message: str
) -> None:
    fake = FakeNote(body)
    async with Client(create_mcp_server(settings)) as client:
        result = await client.call_tool(
            "notes_replace_text", {"note_id": "n1", "find": find, "replace": "X"}
        )
    assert result.is_error
    assert message in text_of(result)
    assert fake.puts == []


@respx.mock
async def test_replace_all_with_expected_count(settings: Settings) -> None:
    fake = FakeNote("todo, todo")
    async with Client(create_mcp_server(settings)) as client:
        result = await client.call_tool(
            "notes_replace_text",
            {"note_id": "n1", "find": "todo", "replace": "done", "expected_count": 2},
        )
    assert not result.is_error
    assert fake.body == "done, done"


@respx.mock
async def test_replace_refuses_stale_edit(settings: Settings) -> None:
    fake = FakeNote("a b", updated_time=5)
    async with Client(create_mcp_server(settings)) as client:
        result = await client.call_tool(
            "notes_replace_text",
            {"note_id": "n1", "find": "a", "replace": "z", "expected_updated_time": 4},
        )
    assert result.is_error
    assert fake.puts == []


# ----------------------------------------------------------------- notes_update


@respx.mock
async def test_update_refuses_stale_edit_and_empty_update(settings: Settings) -> None:
    fake = FakeNote("keep me", updated_time=10)
    async with Client(create_mcp_server(settings)) as client:
        stale = await client.call_tool(
            "notes_update", {"note_id": "n1", "body": "overwrite", "expected_updated_time": 9}
        )
        empty = await client.call_tool("notes_update", {"note_id": "n1"})
        ok = await client.call_tool(
            "notes_update", {"note_id": "n1", "body": "new", "expected_updated_time": 10}
        )
    assert stale.is_error and "changed since you read it" in text_of(stale)
    assert empty.is_error and "Nothing to update" in text_of(empty)
    assert not ok.is_error
    assert fake.puts == [{"body": "new"}]


# ------------------------------------------------------------------ attach no-op


@respx.mock
async def test_attach_does_not_rewrite_when_already_linked(settings: Settings) -> None:
    rid = "0123456789abcdef0123456789abcdef"
    fake = FakeNote(f"x\n\n[{rid}](:/{rid})\n")
    async with Client(create_mcp_server(settings)) as client:
        result = await client.call_tool(
            "notes_attach_resource", {"note_id": "n1", "resource_id": rid}
        )
    assert not result.is_error
    assert fake.puts == []


# ------------------------------------------------------------- input validation


@pytest.mark.parametrize(
    ("tool", "args", "message"),
    [
        ("notes_list", {"fields": "id,titel"}, "Unknown field(s): titel"),
        ("search", {"query": "x", "fields": "id,password"}, "Unknown field(s): password"),
        ("notes_list", {"limit": 500}, "limit"),
        ("notes_list", {"page": 0}, "page"),
        ("search", {"query": "x", "search_type": "resource"}, "search_type"),
    ],
    ids=["typo-field", "unknown-search-field", "limit-too-big", "page-zero", "bad-search-type"],
)
@respx.mock(assert_all_mocked=True)
async def test_bad_input_rejected_before_calling_joplin(
    settings: Settings, tool: str, args: dict[str, Any], message: str
) -> None:
    # Any request to Joplin would fail assert_all_mocked: nothing is mocked.
    async with Client(create_mcp_server(settings)) as client:
        result = await client.call_tool(tool, args)
    assert result.is_error
    assert message in text_of(result)


@respx.mock
async def test_tool_errors_reach_the_model_not_opaque(settings: Settings) -> None:
    # Previously ValueError -> "Error executing tool folders_update".
    async with Client(create_mcp_server(settings)) as client:
        folders = await client.call_tool("folders_update", {"folder_id": "f1"})
        b64 = await client.call_tool(
            "resources_create", {"filename": "a.bin", "data_base64": "%%%"}
        )
    assert "At least one of 'title' or 'parent_id'" in text_of(folders)
    assert "Invalid base64" in text_of(b64)


@respx.mock
async def test_valid_fields_are_deduplicated_and_passed_through(settings: Settings) -> None:
    route = respx.get(f"{JOPLIN}/notes").mock(
        return_value=httpx.Response(200, json={"items": [], "has_more": False})
    )
    async with Client(create_mcp_server(settings)) as client:
        result = await client.call_tool("notes_list", {"fields": "id, title,id"})
    assert not result.is_error
    assert route.calls.last.request.url.params["fields"] == "id,title"


@respx.mock
async def test_append_to_whitespace_only_note_has_no_leading_separator(
    settings: Settings,
) -> None:
    fake = FakeNote("  \n\n")
    async with Client(create_mcp_server(settings)) as client:
        await client.call_tool("notes_append", {"note_id": "n1", "text": "hello"})
    assert fake.body == "hello\n"


@respx.mock
async def test_detach_refuses_stale_edit_only_when_it_would_write(settings: Settings) -> None:
    rid = "0123456789abcdef0123456789abcdef"
    fake = FakeNote(f"keep\n\n![x](:/{rid})\n", updated_time=50)
    async with Client(create_mcp_server(settings)) as client:
        stale = await client.call_tool(
            "notes_detach_resource",
            {"note_id": "n1", "resource_id": rid, "expected_updated_time": 49},
        )
        assert stale.is_error and "changed since you read it" in text_of(stale)
        assert fake.puts == []
        fresh = await client.call_tool(
            "notes_detach_resource",
            {"note_id": "n1", "resource_id": rid, "expected_updated_time": 50},
        )
    assert not fresh.is_error
    assert fake.body == "keep\n"
