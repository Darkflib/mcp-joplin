"""How the real Joplin Data API answers, as opposed to how one might expect it to.

Each case was checked against Joplin's source (packages/lib/services/rest/).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from mcp import Client

from mcp_joplin.mcp_server import create_mcp_server
from mcp_joplin.settings import Settings

JOPLIN = "http://127.0.0.1:41184"
MODES = ["legacy", "2026-07-28"]


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("JOPLIN_TOKEN", "joplin-token-0123456789")
    monkeypatch.setenv("MCP_API_KEY", "test-api-key-123456")
    monkeypatch.setenv("MCP_EVENTS_POLL_SECONDS", "0")
    return Settings(_env_file=None)


# A successful DELETE returns HTTP 200 with an empty body (defaultAction.ts and
# the notes/folders routes `return;`, which ClipperServer writes as '').
DELETES: list[tuple[str, dict[str, Any], str]] = [
    ("notes_delete", {"note_id": "n1"}, "/notes/n1"),
    ("folders_delete", {"folder_id": "f1"}, "/folders/f1"),
    ("tags_delete", {"tag_id": "t1"}, "/tags/t1"),
    ("tags_remove_note", {"tag_id": "t1", "note_id": "n1"}, "/tags/t1/notes/n1"),
    ("resources_delete", {"resource_id": "r1"}, "/resources/r1"),
]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize(("tool", "args", "path"), DELETES)
@respx.mock
async def test_delete_with_empty_success_body_is_not_an_error(
    settings: Settings, mode: str, tool: str, args: dict[str, Any], path: str
) -> None:
    route = respx.delete(f"{JOPLIN}{path}").mock(return_value=httpx.Response(200, text=""))
    async with Client(create_mcp_server(settings), mode=mode) as client:
        result = await client.call_tool(tool, args)
    assert route.call_count == 1
    assert not result.is_error, result.content


@respx.mock
async def test_delete_failure_is_still_reported(settings: Settings) -> None:
    respx.delete(f"{JOPLIN}/notes/missing").mock(return_value=httpx.Response(404, text="Not found"))
    async with Client(create_mcp_server(settings)) as client:
        result = await client.call_tool("notes_delete", {"note_id": "missing"})
    assert result.is_error


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_notes_list_filters_by_folder_via_folder_route(settings: Settings, mode: str) -> None:
    # /notes ignores a parent_id query parameter; /folders/:id/notes filters.
    unfiltered = respx.get(f"{JOPLIN}/notes").mock(return_value=httpx.Response(500))
    folder = respx.get(f"{JOPLIN}/folders/f1/notes").mock(
        return_value=httpx.Response(
            200, json={"items": [{"id": "n1", "parent_id": "f1"}], "has_more": True}
        )
    )
    async with Client(create_mcp_server(settings), mode=mode) as client:
        result = await client.call_tool(
            "notes_list", {"parent_id": "f1", "page": 2, "limit": 5, "fields": "id,parent_id"}
        )
    assert not result.is_error
    assert unfiltered.call_count == 0
    params = folder.calls.last.request.url.params
    assert (params["page"], params["limit"], params["fields"]) == ("2", "5", "id,parent_id")
    assert "parent_id" not in params
    assert result.structured_content is not None
    assert result.structured_content["next_page"] == 3


@respx.mock
async def test_notes_list_without_folder_lists_all(settings: Settings) -> None:
    route = respx.get(f"{JOPLIN}/notes").mock(
        return_value=httpx.Response(200, json={"items": [], "has_more": False})
    )
    async with Client(create_mcp_server(settings)) as client:
        result = await client.call_tool("notes_list", {})
    assert not result.is_error
    assert route.call_count == 1
