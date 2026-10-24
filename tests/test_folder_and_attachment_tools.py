"""Tool-level regressions: folder pagination, detach/attach behaviour."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from mcp import Client

from mcp_joplin_streamable_sse.errors import CollectionTooLargeError, JoplinApiError
from mcp_joplin_streamable_sse.joplin_client import JoplinClient
from mcp_joplin_streamable_sse.mcp_server import create_mcp_server
from mcp_joplin_streamable_sse.settings import Settings

JOPLIN = "http://127.0.0.1:41184"
RID = "0123456789abcdef0123456789abcdef"
MODES = ["legacy", "2026-07-28"]


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("JOPLIN_TOKEN", "joplin-token-0123456789")
    monkeypatch.setenv("MCP_API_KEY", "test-api-key-123456")
    return Settings(_env_file=None)


def paged_folders(total: int) -> respx.Route:
    """Mock /folders as Joplin does: pages of `limit`, with has_more."""
    folders = [
        # One root; everything else hangs off it (or off the previous folder).
        {"id": f"f{i:04d}", "title": f"Folder {i:04d}", "parent_id": "" if i == 0 else "f0000"}
        for i in range(total)
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        limit = int(request.url.params["limit"])
        chunk = folders[(page - 1) * limit : page * limit]
        return httpx.Response(200, json={"items": chunk, "has_more": page * limit < len(folders)})

    return respx.get(f"{JOPLIN}/folders").mock(side_effect=handler)


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_folders_tree_includes_folders_beyond_first_page(
    settings: Settings, mode: str
) -> None:
    route = paged_folders(250)
    async with Client(create_mcp_server(settings), mode=mode) as client:
        result = await client.call_tool("folders_tree", {})
    assert not result.is_error
    assert route.call_count == 3
    tree: Any = result.structured_content
    roots = tree["result"] if isinstance(tree, dict) else tree
    assert len(roots) == 1
    assert len(roots[0]["children"]) == 249  # previously capped at 99


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_folder_tree_resource_includes_folders_beyond_first_page(
    settings: Settings, mode: str
) -> None:
    paged_folders(150)
    async with Client(create_mcp_server(settings), mode=mode) as client:
        result = await client.read_resource("joplin-folders://tree")
    tree = json.loads(result.contents[0].text)  # type: ignore[union-attr]
    assert len(tree[0]["children"]) == 149


@respx.mock
async def test_get_all_refuses_runaway_collections() -> None:
    # A server that always claims there is more must not loop forever.
    respx.get(f"{JOPLIN}/folders").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "x"}] * 100, "has_more": True})
    )
    client = JoplinClient(base_url=JOPLIN, token="joplin-token-0123456789")
    try:
        with pytest.raises(CollectionTooLargeError, match="more than 250 items"):
            await client.get_all("/folders", max_items=250)
    finally:
        await client.aclose()


@respx.mock
async def test_get_all_stops_on_empty_page_claiming_more() -> None:
    # Review finding: an empty page never hits the item cap, so it would loop.
    route = respx.get(f"{JOPLIN}/folders").mock(
        return_value=httpx.Response(200, json={"items": [], "has_more": True})
    )
    client = JoplinClient(base_url=JOPLIN, token="joplin-token-0123456789")
    try:
        with pytest.raises(JoplinApiError, match="empty but reported has_more"):
            await client.get_all("/folders")
    finally:
        await client.aclose()
    assert route.call_count == 1


def note(body: str) -> dict[str, Any]:
    return {"id": "n1", "title": "T", "body": body, "parent_id": "p", "updated_time": 1}


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_detach_keeps_surrounding_prose(settings: Settings, mode: str) -> None:
    original = f"Numbers are in ![chart](:/{RID}) and look strong.\n\nMore text.\n"
    respx.get(f"{JOPLIN}/notes/n1").mock(return_value=httpx.Response(200, json=note(original)))
    put = respx.put(f"{JOPLIN}/notes/n1").mock(
        side_effect=lambda req: httpx.Response(200, json=note(json.loads(req.content)["body"]))
    )
    async with Client(create_mcp_server(settings), mode=mode) as client:
        result = await client.call_tool(
            "notes_detach_resource", {"note_id": "n1", "resource_id": RID}
        )
    assert not result.is_error
    sent = json.loads(put.calls.last.request.content)["body"]
    assert sent == "Numbers are in and look strong.\n\nMore text.\n"
    assert result.structured_content is not None
    assert result.structured_content["links_removed"] == 1


@pytest.mark.parametrize("mode", MODES)
@respx.mock
async def test_detach_without_reference_does_not_write(settings: Settings, mode: str) -> None:
    respx.get(f"{JOPLIN}/notes/n1").mock(
        return_value=httpx.Response(200, json=note("No attachments here.  \n\n"))
    )
    put = respx.put(f"{JOPLIN}/notes/n1").mock(return_value=httpx.Response(500))
    async with Client(create_mcp_server(settings), mode=mode) as client:
        result = await client.call_tool(
            "notes_detach_resource", {"note_id": "n1", "resource_id": RID}
        )
    assert not result.is_error
    assert put.call_count == 0  # previously always PUT (and stripped trailing whitespace)
    assert result.structured_content is not None
    assert result.structured_content["links_removed"] == 0


@respx.mock
async def test_attach_escapes_label_so_detach_can_remove_it(settings: Settings) -> None:
    state = {"body": "Intro\n"}
    respx.get(f"{JOPLIN}/notes/n1").mock(
        side_effect=lambda req: httpx.Response(200, json=note(state["body"]))
    )

    def save(req: httpx.Request) -> httpx.Response:
        state["body"] = json.loads(req.content)["body"]
        return httpx.Response(200, json=note(state["body"]))

    respx.put(f"{JOPLIN}/notes/n1").mock(side_effect=save)
    async with Client(create_mcp_server(settings)) as client:
        await client.call_tool(
            "notes_attach_resource",
            {"note_id": "n1", "resource_id": RID, "alt_text": "Q3 [final]\nreport", "embed": True},
        )
        assert state["body"] == f"Intro\n\n![Q3 \\[final\\] report](:/{RID})\n"
        result = await client.call_tool(
            "notes_detach_resource", {"note_id": "n1", "resource_id": RID}
        )
    assert result.structured_content is not None
    assert result.structured_content["links_removed"] == 1
    assert state["body"] == "Intro\n"
