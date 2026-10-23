"""FastMCP server definition (tools + resources)."""

from __future__ import annotations

import base64
import binascii
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from .joplin_client import JoplinClient
from .models import Folder, FolderNode, Note, PagedResult, Resource, ResourceBlob
from .redaction import install_log_redaction
from .settings import Settings


@dataclass(slots=True)
class AppContext:
    settings: Settings
    joplin: JoplinClient


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


def _build_folder_tree(folders: list[dict[str, Any]]) -> list[FolderNode]:
    by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for f in folders:
        by_parent.setdefault(f.get("parent_id"), []).append(f)

    def build(parent_id: str | None) -> list[FolderNode]:
        children = []
        for f in sorted(by_parent.get(parent_id, []), key=lambda x: x.get("title") or ""):
            node = FolderNode(
                id=str(f.get("id")), title=f.get("title"), children=build(f.get("id"))
            )
            children.append(node)
        return children

    return build(None)


def create_mcp_server(settings: Settings) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[AppContext]:
        # Runs on every transport, after FastMCP/uvicorn have set up log handlers.
        # Idempotent, so per-session lifespans (v1 stateless HTTP) are fine.
        install_log_redaction([settings.joplin_token, settings.mcp_api_key])
        joplin = JoplinClient(
            base_url=str(settings.joplin_base_url),
            token=settings.joplin_token,
            timeout_seconds=settings.http_timeout_seconds,
        )
        try:
            yield AppContext(settings=settings, joplin=joplin)
        finally:
            await joplin.aclose()

    mcp = FastMCP(
        "Joplin",
        instructions=(
            "Access and manage Joplin notes via the local Joplin Data API (Web Clipper). "
            "Use tools for CRUD operations and resources to load note content."
        ),
        lifespan=lifespan,
        # Configure Streamable HTTP behavior (FastMCP.streamable_http_app() no longer accepts these
        # as parameters in newer mcp versions).
        stateless_http=True,
        json_response=True,
    )

    @mcp.resource("joplin-note://{note_id}")
    async def read_note_resource(note_id: str, ctx: Context) -> str:
        """Read a note's Markdown body."""
        app: AppContext = ctx.request_context.lifespan_context
        note = await app.joplin.request_json(
            "GET",
            f"/notes/{note_id}",
            params={"fields": "id,title,body,updated_time,created_time,parent_id"},
        )
        title = note.get("title") or "(untitled)"
        body = note.get("body") or ""
        return f"# {title}\n\n{body}"

    @mcp.resource("joplin-folders://tree")
    async def read_folders_tree_resource(ctx: Context) -> list[FolderNode]:
        """Return the full folder tree."""
        app: AppContext = ctx.request_context.lifespan_context
        raw = await app.joplin.get_paged(
            "/folders", page=1, limit=100, params={"fields": "id,title,parent_id"}
        )
        # Joplin paginates; for folders we fetch up to 100 in one go (good enough for v1).
        folders = list(raw.get("items") or [])
        return _build_folder_tree(folders)

    @mcp.tool()
    async def notes_get(note_id: str, ctx: Context) -> Note:
        """Get a single note by id."""
        app: AppContext = ctx.request_context.lifespan_context
        raw = await app.joplin.request_json(
            "GET",
            f"/notes/{note_id}",
            params={"fields": "id,title,body,parent_id,created_time,updated_time"},
        )
        return Note.model_validate(raw)

    @mcp.tool()
    async def notes_list(
        ctx: Context,
        parent_id: str | None = None,
        page: int = 1,
        limit: int = 20,
        fields: str = "id,title,parent_id,updated_time",
    ) -> PagedResult:
        """List notes (optionally within a folder)."""
        app: AppContext = ctx.request_context.lifespan_context

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
        ctx: Context,
        parent_id: str | None = None,
    ) -> Note:
        """Create a new note."""
        app: AppContext = ctx.request_context.lifespan_context
        payload: dict[str, Any] = {"title": title, "body": body}
        if parent_id:
            payload["parent_id"] = parent_id
        raw = await app.joplin.request_json("POST", "/notes", json_body=payload)
        return Note.model_validate(raw)

    @mcp.tool()
    async def notes_update(
        note_id: str,
        ctx: Context,
        title: str | None = None,
        body: str | None = None,
        parent_id: str | None = None,
    ) -> Note:
        """Update fields of an existing note."""
        app: AppContext = ctx.request_context.lifespan_context
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
    async def notes_delete(note_id: str, ctx: Context) -> dict[str, Any]:
        """Delete a note."""
        app: AppContext = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/notes/{note_id}")
        return {"deleted": True, "id": note_id}

    @mcp.tool()
    async def folders_list(
        ctx: Context,
        page: int = 1,
        limit: int = 50,
        fields: str = "id,title,parent_id",
    ) -> PagedResult:
        """List folders (notebooks)."""
        app: AppContext = ctx.request_context.lifespan_context
        params: dict[str, Any] = {}
        parsed_fields = _parse_fields(fields)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/folders", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    @mcp.tool()
    async def folders_create(
        title: str,
        ctx: Context,
        parent_id: str | None = None,
    ) -> Folder:
        """Create a new folder (notebook)."""
        app: AppContext = ctx.request_context.lifespan_context
        payload: dict[str, Any] = {"title": title}
        if parent_id:
            payload["parent_id"] = parent_id
        raw = await app.joplin.request_json("POST", "/folders", json_body=payload)
        return Folder.model_validate(raw)

    @mcp.tool()
    async def folders_update(
        folder_id: str,
        ctx: Context,
        title: str | None = None,
        parent_id: str | None = None,
    ) -> Folder:
        """Update a folder (rename and/or move by changing parent_id)."""
        app: AppContext = ctx.request_context.lifespan_context
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
    async def folders_delete(folder_id: str, ctx: Context) -> dict[str, Any]:
        """Delete a folder (notebook)."""
        app: AppContext = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/folders/{folder_id}")
        return {"deleted": True, "id": folder_id}

    @mcp.tool()
    async def folders_tree(ctx: Context) -> list[FolderNode]:
        """Return the folder tree."""
        app: AppContext = ctx.request_context.lifespan_context
        raw = await app.joplin.get_paged(
            "/folders", page=1, limit=100, params={"fields": "id,title,parent_id"}
        )
        return _build_folder_tree(list(raw.get("items") or []))

    @mcp.tool()
    async def tags_list(
        ctx: Context,
        page: int = 1,
        limit: int = 50,
        fields: str = "id,title",
    ) -> PagedResult:
        """List tags."""
        app: AppContext = ctx.request_context.lifespan_context
        params: dict[str, Any] = {}
        parsed_fields = _parse_fields(fields)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/tags", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    @mcp.tool()
    async def tags_create(title: str, ctx: Context) -> dict[str, Any]:
        """Create a tag."""
        app: AppContext = ctx.request_context.lifespan_context
        return await app.joplin.request_json("POST", "/tags", json_body={"title": title})

    @mcp.tool()
    async def tags_delete(tag_id: str, ctx: Context) -> dict[str, Any]:
        """Delete a tag."""
        app: AppContext = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/tags/{tag_id}")
        return {"deleted": True, "id": tag_id}

    @mcp.tool()
    async def tags_add_note(tag_id: str, note_id: str, ctx: Context) -> dict[str, Any]:
        """Attach a tag to a note."""
        app: AppContext = ctx.request_context.lifespan_context
        # Joplin expects a body with {"id": <note_id>}.
        await app.joplin.request_json("POST", f"/tags/{tag_id}/notes", json_body={"id": note_id})
        return {"tag_id": tag_id, "note_id": note_id, "attached": True}

    @mcp.tool()
    async def tags_remove_note(tag_id: str, note_id: str, ctx: Context) -> dict[str, Any]:
        """Remove a tag from a note."""
        app: AppContext = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/tags/{tag_id}/notes/{note_id}")
        return {"tag_id": tag_id, "note_id": note_id, "attached": False}

    @mcp.tool()
    async def resources_list(
        ctx: Context,
        page: int = 1,
        limit: int = 50,
        fields: str = "id,title,mime,filename,file_extension,size,updated_time",
    ) -> PagedResult:
        """List attachments (resources)."""
        app: AppContext = ctx.request_context.lifespan_context
        params: dict[str, Any] = {}
        parsed_fields = _parse_fields(fields)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/resources", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    @mcp.tool()
    async def resources_get(resource_id: str, ctx: Context) -> Resource:
        """Get a single attachment metadata by id."""
        app: AppContext = ctx.request_context.lifespan_context
        raw = await app.joplin.request_json(
            "GET",
            f"/resources/{resource_id}",
            params={
                "fields": "id,title,mime,filename,file_extension,size,created_time,updated_time"
            },
        )
        return Resource.model_validate(raw)

    @mcp.tool()
    async def resources_get_content(resource_id: str, ctx: Context) -> ResourceBlob:
        """Get attachment file bytes encoded as base64."""
        app: AppContext = ctx.request_context.lifespan_context
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
        ctx: Context,
        mime: str = "application/octet-stream",
        title: str | None = None,
    ) -> Resource:
        """Create a new attachment (resource) from base64-encoded file bytes."""
        app: AppContext = ctx.request_context.lifespan_context
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
    async def resources_delete(resource_id: str, ctx: Context) -> dict[str, Any]:
        """Delete an attachment (resource)."""
        app: AppContext = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/resources/{resource_id}")
        return {"deleted": True, "id": resource_id}

    @mcp.tool()
    async def notes_list_resources(
        note_id: str,
        ctx: Context,
        page: int = 1,
        limit: int = 50,
        fields: str = "id,title,mime,filename,file_extension,size,updated_time",
    ) -> PagedResult:
        """List attachments linked to a note."""
        app: AppContext = ctx.request_context.lifespan_context
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
        ctx: Context,
        alt_text: str | None = None,
        embed: bool = False,
    ) -> Note:
        """Attach a resource to a note by appending a Markdown resource link."""
        app: AppContext = ctx.request_context.lifespan_context
        note_raw = await app.joplin.request_json(
            "GET",
            f"/notes/{note_id}",
            params={"fields": "id,title,body,parent_id,created_time,updated_time"},
        )
        body = note_raw.get("body") or ""
        display = alt_text or resource_id
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
        ctx: Context,
    ) -> Note:
        """Detach a resource from a note by removing Markdown resource links that reference it."""
        app: AppContext = ctx.request_context.lifespan_context
        note_raw = await app.joplin.request_json(
            "GET",
            f"/notes/{note_id}",
            params={"fields": "id,title,body,parent_id,created_time,updated_time"},
        )
        body = note_raw.get("body") or ""
        filtered_lines: list[str] = []
        needle = f"(:/{resource_id})"
        for line in body.splitlines():
            if needle in line:
                continue
            filtered_lines.append(line)
        updated_body = "\n".join(filtered_lines).rstrip() + "\n"

        updated_raw = await app.joplin.request_json(
            "PUT",
            f"/notes/{note_id}",
            json_body={"body": updated_body},
        )
        return Note.model_validate(updated_raw)

    @mcp.tool()
    async def search(
        query: str,
        ctx: Context,
        search_type: str = "note",
        page: int = 1,
        limit: int = 20,
        fields: str = "id,title,parent_id,updated_time",
    ) -> PagedResult:
        """Search Joplin items (default type: note)."""
        app: AppContext = ctx.request_context.lifespan_context
        params: dict[str, Any] = {"query": query, "type": search_type}
        parsed_fields = _parse_fields(fields)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/search", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    return mcp
