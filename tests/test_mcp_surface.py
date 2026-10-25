"""The MCP surface survives the 2.x port unchanged, on both protocol eras."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from mcp import Client

from mcp_joplin_streamable_sse.mcp_server import create_mcp_server
from mcp_joplin_streamable_sse.settings import Settings

JOPLIN = "http://127.0.0.1:41184"
MODES = ["legacy", "2026-07-28"]

# Tool names as documented in README/AGENTS.md (all pre-port tools must remain).
EXPECTED_TOOLS = {
    "notes_get",
    "notes_list",
    "notes_create",
    "notes_update",
    "notes_delete",
    "folders_list",
    "folders_tree",
    "folders_create",
    "folders_update",
    "folders_delete",
    "tags_list",
    "tags_create",
    "tags_delete",
    "tags_add_note",
    "tags_remove_note",
    "resources_list",
    "resources_get",
    "resources_get_content",
    "resources_create",
    "resources_delete",
    "notes_list_resources",
    "notes_attach_resource",
    "notes_detach_resource",
    "search",
    # Added with the safer-editing tools.
    "notes_append",
    "notes_replace_text",
    # Added with binary attachments.
    "resources_read",
}

FOLDERS = {
    "items": [
        {"id": "a", "title": "Alpha", "parent_id": ""},
        {"id": "b", "title": "Beta", "parent_id": "a"},
        {"id": "c", "title": "Gamma", "parent_id": "b"},
    ],
    "has_more": False,
}


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("JOPLIN_TOKEN", "joplin-token-0123456789")
    monkeypatch.setenv("MCP_API_KEY", "test-api-key-123456")
    return Settings()


@pytest.mark.parametrize("mode", MODES)
async def test_tool_names_unchanged(settings: Settings, mode: str) -> None:
    async with Client(create_mcp_server(settings), mode=mode) as client:
        tools = await client.list_tools()
    assert {t.name for t in tools.tools} == EXPECTED_TOOLS


@pytest.mark.parametrize("mode", MODES)
async def test_resource_templates_listed(settings: Settings, mode: str) -> None:
    async with Client(create_mcp_server(settings), mode=mode) as client:
        templates = await client.list_resource_templates()
    uris = {t.uri_template for t in templates.resource_templates}
    assert uris == {
        "joplin-note://{note_id}",
        "joplin-folders://tree{?root_id}",
        "joplin-resource://{resource_id}",
    }


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_folder_tree_resource_plain_and_subtree(settings: Settings, mode: str) -> None:
    respx.get(f"{JOPLIN}/folders").mock(return_value=httpx.Response(200, json=FOLDERS))
    async with Client(create_mcp_server(settings), mode=mode) as client:
        # The pre-port URI still resolves.
        full = await client.read_resource("joplin-folders://tree")
        sub = await client.read_resource("joplin-folders://tree?root_id=b")

    full_tree = json.loads(full.contents[0].text)  # type: ignore[union-attr]
    assert [n["id"] for n in full_tree] == ["a"]
    assert full_tree[0]["children"][0]["id"] == "b"

    sub_tree = json.loads(sub.contents[0].text)  # type: ignore[union-attr]
    assert [n["id"] for n in sub_tree] == ["c"]


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_note_resource(settings: Settings, mode: str) -> None:
    respx.get(f"{JOPLIN}/notes/n1").mock(
        return_value=httpx.Response(200, json={"id": "n1", "title": "Hello", "body": "World"})
    )
    async with Client(create_mcp_server(settings), mode=mode) as client:
        result = await client.read_resource("joplin-note://n1")
    assert result.contents[0].text == "# Hello\n\nWorld"  # type: ignore[union-attr]


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_joplin_404_on_resource_is_reported_not_crashed(
    settings: Settings, mode: str
) -> None:
    respx.get(f"{JOPLIN}/notes/missing").mock(return_value=httpx.Response(404, text="Not found"))
    async with Client(create_mcp_server(settings), mode=mode) as client:
        with pytest.raises(Exception) as excinfo:
            await client.read_resource("joplin-note://missing")
    assert "404" in str(excinfo.value)


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_resources_create_rejects_bad_base64(settings: Settings, mode: str) -> None:
    async with Client(create_mcp_server(settings), mode=mode) as client:
        result = await client.call_tool(
            "resources_create", {"filename": "x.bin", "data_base64": "not base64!!"}
        )
    assert result.is_error
