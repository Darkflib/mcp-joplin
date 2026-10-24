"""MCPServer definition (tools + resources)."""

from __future__ import annotations

import base64
import binascii
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from .joplin_client import JoplinClient
from .models import (
    Folder,
    FolderNode,
    Note,
    NoteDetachResult,
    PagedResult,
    Resource,
    ResourceBlob,
)
from .redaction import install_log_redaction
from .resource_links import remove_resource_links
from .settings import Settings


@dataclass(slots=True)
class AppContext:
    settings: Settings
    joplin: JoplinClient


# Typed tool context: makes ctx.request_context.lifespan_context an AppContext.
JoplinCtx = Context[AppContext, Any]


def _parse_fields(fields: str | None) -> str | None:
    if fields is None:
        return None
    cleaned = ",".join([f.strip() for f in fields.split(",") if f.strip()])
    return cleaned or None


def _paged_result(raw: dict[str, Any], *, page: int, limit: int) -> PagedResult:
    items = list(raw.get("items") or [])
    has_more = bool(raw.get("has_more"))
    return PagedResult(
        items=items,
        page=page,
        limit=limit,
        has_more=has_more,
        next_page=(page + 1 if has_more else None),
    )


def _escape_link_label(label: str) -> str:
    """Make arbitrary text safe as a Markdown link label (and removable by detach)."""
    flat = " ".join(label.split())  # no newlines inside a link label
    return flat.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _build_folder_tree(
    folders: list[dict[str, Any]], root_id: str | None = None
) -> list[FolderNode]:
    by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for f in folders:
        # Joplin reports top-level folders with parent_id "" (not null).
        by_parent.setdefault(f.get("parent_id") or None, []).append(f)

    def build(parent_id: str | None) -> list[FolderNode]:
        children = []
        for f in sorted(by_parent.get(parent_id, []), key=lambda x: x.get("title") or ""):
            node = FolderNode(
                id=str(f.get("id")), title=f.get("title"), children=build(f.get("id"))
            )
            children.append(node)
        return children

    return build(root_id)


def create_mcp_server(settings: Settings) -> MCPServer[AppContext]:
    @asynccontextmanager
    async def lifespan(_: MCPServer[AppContext]) -> AsyncIterator[AppContext]:
        # Runs once per process on every transport (under streamable HTTP, at
        # session-manager startup), after MCPServer/uvicorn set up log handlers.
        install_log_redaction(settings.secrets())
        joplin = JoplinClient(
            base_url=str(settings.joplin_base_url),
            token=settings.joplin_token,
            timeout_seconds=settings.http_timeout_seconds,
        )
        try:
            yield AppContext(settings=settings, joplin=joplin)
        finally:
            await joplin.aclose()

    mcp = MCPServer(
        "Joplin",
        instructions=(
            "Access and manage Joplin notes via the local Joplin Data API (Web Clipper). "
            "Use tools for CRUD operations and resources to load note content."
        ),
        lifespan=lifespan,
    )

    @mcp.resource("joplin-note://{note_id}")
    async def read_note_resource(note_id: str, ctx: JoplinCtx) -> str:
        """Read a note's Markdown body."""
        app = ctx.request_context.lifespan_context
        note = await app.joplin.request_json(
            "GET",
            f"/notes/{note_id}",
            params={"fields": "id,title,body,updated_time,created_time,parent_id"},
        )
        title = note.get("title") or "(untitled)"
        body = note.get("body") or ""
        return f"# {title}\n\n{body}"

    # MCP 2.x only injects Context into templated resources, hence the optional
    # query variable. Plain "joplin-folders://tree" still matches.
    @mcp.resource("joplin-folders://tree{?root_id}")
    async def read_folders_tree_resource(
        ctx: JoplinCtx, root_id: str | None = None
    ) -> list[FolderNode]:
        """Return the folder tree, or the subtree below ``root_id`` if given."""
        app = ctx.request_context.lifespan_context
        folders = await app.joplin.get_all("/folders", params={"fields": "id,title,parent_id"})
        return _build_folder_tree(folders, root_id or None)

    @mcp.tool()
    async def notes_get(note_id: str, ctx: JoplinCtx) -> Note:
        """Get a single note by id."""
        app = ctx.request_context.lifespan_context
        raw = await app.joplin.request_json(
            "GET",
            f"/notes/{note_id}",
            params={"fields": "id,title,body,parent_id,created_time,updated_time"},
        )
        return Note.model_validate(raw)

    @mcp.tool()
    async def notes_list(
        ctx: JoplinCtx,
        parent_id: str | None = None,
        page: int = 1,
        limit: int = 20,
        fields: str = "id,title,parent_id,updated_time",
    ) -> PagedResult:
        """List notes (optionally within a folder)."""
        app = ctx.request_context.lifespan_context

        params: dict[str, Any] = {}
        if parent_id:
            params["parent_id"] = parent_id
        parsed_fields = _parse_fields(fields)
        if parsed_fields:
            params["fields"] = parsed_fields

        raw = await app.joplin.get_paged("/notes", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    @mcp.tool()
    async def notes_create(
        title: str,
        body: str,
        ctx: JoplinCtx,
        parent_id: str | None = None,
    ) -> Note:
        """Create a new note."""
        app = ctx.request_context.lifespan_context
        payload: dict[str, Any] = {"title": title, "body": body}
        if parent_id:
            payload["parent_id"] = parent_id
        raw = await app.joplin.request_json("POST", "/notes", json_body=payload)
        return Note.model_validate(raw)

    @mcp.tool()
    async def notes_update(
        note_id: str,
        ctx: JoplinCtx,
        title: str | None = None,
        body: str | None = None,
        parent_id: str | None = None,
    ) -> Note:
        """Update fields of an existing note."""
        app = ctx.request_context.lifespan_context
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if parent_id is not None:
            payload["parent_id"] = parent_id
        raw = await app.joplin.request_json("PUT", f"/notes/{note_id}", json_body=payload)
        return Note.model_validate(raw)

    @mcp.tool()
    async def notes_delete(note_id: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Delete a note."""
        app = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/notes/{note_id}")
        return {"deleted": True, "id": note_id}

    @mcp.tool()
    async def folders_list(
        ctx: JoplinCtx,
        page: int = 1,
        limit: int = 50,
        fields: str = "id,title,parent_id",
    ) -> PagedResult:
        """List folders (notebooks)."""
        app = ctx.request_context.lifespan_context
        params: dict[str, Any] = {}
        parsed_fields = _parse_fields(fields)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/folders", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    @mcp.tool()
    async def folders_create(
        title: str,
        ctx: JoplinCtx,
        parent_id: str | None = None,
    ) -> Folder:
        """Create a new folder (notebook)."""
        app = ctx.request_context.lifespan_context
        payload: dict[str, Any] = {"title": title}
        if parent_id:
            payload["parent_id"] = parent_id
        raw = await app.joplin.request_json("POST", "/folders", json_body=payload)
        return Folder.model_validate(raw)

    @mcp.tool()
    async def folders_update(
        folder_id: str,
        ctx: JoplinCtx,
        title: str | None = None,
        parent_id: str | None = None,
    ) -> Folder:
        """Update a folder (rename and/or move by changing parent_id)."""
        app = ctx.request_context.lifespan_context
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if parent_id is not None:
            payload["parent_id"] = parent_id
        if not payload:
            raise ValueError("At least one of 'title' or 'parent_id' must be provided")
        raw = await app.joplin.request_json("PUT", f"/folders/{folder_id}", json_body=payload)
        return Folder.model_validate(raw)

    @mcp.tool()
    async def folders_delete(folder_id: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Delete a folder (notebook)."""
        app = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/folders/{folder_id}")
        return {"deleted": True, "id": folder_id}

    @mcp.tool()
    async def folders_tree(ctx: JoplinCtx) -> list[FolderNode]:
        """Return the folder tree."""
        app = ctx.request_context.lifespan_context
        folders = await app.joplin.get_all("/folders", params={"fields": "id,title,parent_id"})
        return _build_folder_tree(folders)

    @mcp.tool()
    async def tags_list(
        ctx: JoplinCtx,
        page: int = 1,
        limit: int = 50,
        fields: str = "id,title",
    ) -> PagedResult:
        """List tags."""
        app = ctx.request_context.lifespan_context
        params: dict[str, Any] = {}
        parsed_fields = _parse_fields(fields)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/tags", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    @mcp.tool()
    async def tags_create(title: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Create a tag."""
        app = ctx.request_context.lifespan_context
        return await app.joplin.request_json("POST", "/tags", json_body={"title": title})

    @mcp.tool()
    async def tags_delete(tag_id: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Delete a tag."""
        app = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/tags/{tag_id}")
        return {"deleted": True, "id": tag_id}

    @mcp.tool()
    async def tags_add_note(tag_id: str, note_id: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Attach a tag to a note."""
        app = ctx.request_context.lifespan_context
        # Joplin expects a body with {"id": <note_id>}.
        await app.joplin.request_json("POST", f"/tags/{tag_id}/notes", json_body={"id": note_id})
        return {"tag_id": tag_id, "note_id": note_id, "attached": True}

    @mcp.tool()
    async def tags_remove_note(tag_id: str, note_id: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Remove a tag from a note."""
        app = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/tags/{tag_id}/notes/{note_id}")
        return {"tag_id": tag_id, "note_id": note_id, "attached": False}

    @mcp.tool()
    async def resources_list(
        ctx: JoplinCtx,
        page: int = 1,
        limit: int = 50,
        fields: str = "id,title,mime,filename,file_extension,size,updated_time",
    ) -> PagedResult:
        """List attachments (resources)."""
        app = ctx.request_context.lifespan_context
        params: dict[str, Any] = {}
        parsed_fields = _parse_fields(fields)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/resources", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    @mcp.tool()
    async def resources_get(resource_id: str, ctx: JoplinCtx) -> Resource:
        """Get a single attachment metadata by id."""
        app = ctx.request_context.lifespan_context
        raw = await app.joplin.request_json(
            "GET",
            f"/resources/{resource_id}",
            params={
                "fields": "id,title,mime,filename,file_extension,size,created_time,updated_time"
            },
        )
        return Resource.model_validate(raw)

    @mcp.tool()
    async def resources_get_content(resource_id: str, ctx: JoplinCtx) -> ResourceBlob:
        """Get attachment file bytes encoded as base64."""
        app = ctx.request_context.lifespan_context
        meta_raw = await app.joplin.request_json(
            "GET",
            f"/resources/{resource_id}",
            params={"fields": "id,mime,filename,size"},
        )
        data, _headers = await app.joplin.request_bytes("GET", f"/resources/{resource_id}/file")
        return ResourceBlob(
            id=resource_id,
            mime=meta_raw.get("mime"),
            filename=meta_raw.get("filename"),
            size=len(data),
            data_base64=base64.b64encode(data).decode("ascii"),
        )

    @mcp.tool()
    async def resources_create(
        filename: str,
        data_base64: str,
        ctx: JoplinCtx,
        mime: str = "application/octet-stream",
        title: str | None = None,
    ) -> Resource:
        """Create a new attachment (resource) from base64-encoded file bytes."""
        app = ctx.request_context.lifespan_context
        try:
            raw_bytes = base64.b64decode(data_base64, validate=True)
        except binascii.Error as exc:
            raise ValueError("Invalid base64 data in 'data_base64'") from exc

        raw = await app.joplin.create_resource(
            filename=filename,
            data=raw_bytes,
            mime=mime,
            title=title,
        )
        return Resource.model_validate(raw)

    @mcp.tool()
    async def resources_delete(resource_id: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Delete an attachment (resource)."""
        app = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/resources/{resource_id}")
        return {"deleted": True, "id": resource_id}

    @mcp.tool()
    async def notes_list_resources(
        note_id: str,
        ctx: JoplinCtx,
        page: int = 1,
        limit: int = 50,
        fields: str = "id,title,mime,filename,file_extension,size,updated_time",
    ) -> PagedResult:
        """List attachments linked to a note."""
        app = ctx.request_context.lifespan_context
        params: dict[str, Any] = {}
        parsed_fields = _parse_fields(fields)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged(
            f"/notes/{note_id}/resources", page=page, limit=limit, params=params
        )
        return _paged_result(raw, page=page, limit=limit)

    @mcp.tool()
    async def notes_attach_resource(
        note_id: str,
        resource_id: str,
        ctx: JoplinCtx,
        alt_text: str | None = None,
        embed: bool = False,
    ) -> Note:
        """Attach a resource to a note by appending a Markdown resource link."""
        app = ctx.request_context.lifespan_context
        note_raw = await app.joplin.request_json(
            "GET",
            f"/notes/{note_id}",
            params={"fields": "id,title,body,parent_id,created_time,updated_time"},
        )
        body = note_raw.get("body") or ""
        display = _escape_link_label(alt_text or resource_id)
        snippet = f"![{display}](:/{resource_id})" if embed else f"[{display}](:/{resource_id})"
        if snippet not in body:
            body = f"{body.rstrip()}\n\n{snippet}\n"

        updated_raw = await app.joplin.request_json(
            "PUT",
            f"/notes/{note_id}",
            json_body={"body": body},
        )
        return Note.model_validate(updated_raw)

    @mcp.tool()
    async def notes_detach_resource(
        note_id: str,
        resource_id: str,
        ctx: JoplinCtx,
    ) -> NoteDetachResult:
        """Detach a resource from a note by removing the links and embeds that reference it.

        Removes Markdown links/images (``[x](:/id)``, ``![x](:/id)``), reference
        definitions (``[ref]: :/id``) and HTML ``<img>``/``<a>`` embeds pointing at the
        resource. Other text on the same line is kept. The resource itself is not
        deleted (use ``resources_delete``). If nothing references it, the note is left
        untouched and ``links_removed`` is 0.
        """
        app = ctx.request_context.lifespan_context
        note_raw = await app.joplin.request_json(
            "GET",
            f"/notes/{note_id}",
            params={"fields": "id,title,body,parent_id,created_time,updated_time"},
        )
        body = note_raw.get("body") or ""
        updated_body, removed = remove_resource_links(body, resource_id)
        if not removed:
            # Don't write: a no-op PUT would still bump updated_time and re-sync.
            return NoteDetachResult.model_validate({**note_raw, "links_removed": 0})

        updated_raw = await app.joplin.request_json(
            "PUT",
            f"/notes/{note_id}",
            json_body={"body": updated_body},
        )
        return NoteDetachResult.model_validate({**updated_raw, "links_removed": removed})

    @mcp.tool()
    async def search(
        query: str,
        ctx: JoplinCtx,
        search_type: str = "note",
        page: int = 1,
        limit: int = 20,
        fields: str = "id,title,parent_id,updated_time",
    ) -> PagedResult:
        """Search Joplin items (default type: note)."""
        app = ctx.request_context.lifespan_context
        params: dict[str, Any] = {"query": query, "type": search_type}
        parsed_fields = _parse_fields(fields)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/search", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    return mcp
