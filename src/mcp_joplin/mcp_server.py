"""MCPServer definition (tools + resources)."""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypeVar

import anyio
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.resources import FunctionResource, ResourceTemplate
from mcp.types import (
    AudioContent,
    BlobResourceContents,
    ContentBlock,
    EmbeddedResource,
    ImageContent,
    TextContent,
    TextResourceContents,
    ToolAnnotations,
)
from pydantic import Field

from .errors import AttachmentTooLargeError
from .events import ListenerTrackingBus, NoteEventPoller
from .joplin_client import JoplinClient
from .models import (
    Folder,
    FolderNode,
    Note,
    NoteDetachResult,
    NoteEditResult,
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

# --- Input constraints (advertised in the tool schemas, enforced before the call) ---

Page = Annotated[int, Field(ge=1, description="1-based page number.")]
Limit = Annotated[int, Field(ge=1, le=100, description="Items per page (Joplin caps at 100).")]
ExpectedUpdatedTime = Annotated[
    int | None,
    Field(
        description=(
            "Optional optimistic-concurrency check: the note's `updated_time` from when you "
            "last read it. If the note has changed since, the edit is refused instead of "
            "overwriting someone else's change; re-read the note and retry."
        )
    ),
]

# Fields a caller may request per item type. An allow-list keeps typos from becoming
# Joplin 500s and keeps internal/encryption columns out of the model's context.
_COMMON = ("id", "created_time", "updated_time", "user_created_time", "user_updated_time")
NOTE_FIELDS = frozenset(
    (*_COMMON, "parent_id", "title", "body", "is_todo", "todo_due", "todo_completed",
     "source_url", "author", "latitude", "longitude", "altitude", "is_conflict",
     "markup_language")
)  # fmt: skip
FOLDER_FIELDS = frozenset((*_COMMON, "parent_id", "title", "icon", "is_shared"))
TAG_FIELDS = frozenset((*_COMMON, "parent_id", "title"))
RESOURCE_FIELDS = frozenset(
    (*_COMMON, "title", "mime", "filename", "file_extension", "size", "is_shared")
)
_SEARCH_FIELDS = {"note": NOTE_FIELDS, "folder": FOLDER_FIELDS, "tag": TAG_FIELDS}

# Fields fetched whenever a tool returns a Note.
_NOTE_GET_FIELDS = "id,title,body,parent_id,created_time,updated_time"

# --- Tool annotations: hints to clients about what a tool does to the notebook. ---
# Every tool talks only to the local Joplin instance, hence open_world_hint=False.

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)
# Adds something new; calling twice adds it twice.
CREATES = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)
# Changes metadata/links without losing content; repeating it changes nothing more.
UPDATES = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
# Overwrites or removes existing content (repeatable with the same result).
OVERWRITES = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False
)
# Overwrites existing content; repeating it may change more (e.g. replace again).
EDITS = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False
)
DELETES = OVERWRITES

_F = TypeVar("_F", bound=Callable[..., Any])


def _parse_fields(fields: str | None, allowed: frozenset[str]) -> str | None:
    if fields is None:
        return None
    requested = [f.strip() for f in fields.split(",") if f.strip()]
    unknown = sorted(set(requested) - allowed)
    if unknown:
        raise ToolError(
            f"Unknown field(s): {', '.join(unknown)}. Allowed: {', '.join(sorted(allowed))}"
        )
    return ",".join(dict.fromkeys(requested)) or None


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


def _check_not_stale(note_raw: dict[str, Any], expected_updated_time: int | None) -> None:
    """Refuse an edit if the note changed since the caller read it.

    Best-effort: Joplin has no conditional PUT, so a write landing between this
    GET and our PUT can still be overwritten. It catches the common case (the
    note was edited while the model was thinking), not a true race.
    """
    if expected_updated_time is None:
        return
    actual = note_raw.get("updated_time")
    if actual != expected_updated_time:
        raise ToolError(
            f"Note {note_raw.get('id')} has changed since you read it "
            f"(updated_time is {actual}, you expected {expected_updated_time}). "
            "Re-read the note and retry."
        )


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


# --- Binary attachments ---

ResourceId = Annotated[
    str, Field(pattern=r"^[0-9a-fA-F]{32}$", description="Attachment id (32 hex characters).")
]
_FALLBACK_MIME = "application/octet-stream"
_MIME_RE = re.compile(r"^[A-Za-z0-9][\w.+-]*/[A-Za-z0-9][\w.+-]*$")
# Image formats models can actually look at. SVG goes as text; TIFF, HEIC etc. as blobs.
_VIEWABLE_IMAGES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
_TEXTUAL_APPLICATION = frozenset(
    {"application/json", "application/xml", "application/x-yaml", "application/yaml",
     "application/javascript", "image/svg+xml"}
)  # fmt: skip


def _clean_mime(mime: Any) -> str:
    """Joplin's stored MIME type, stripped of parameters; fall back if it's junk."""
    if not isinstance(mime, str):
        return _FALLBACK_MIME
    base = mime.split(";", 1)[0].strip().lower()
    return base if _MIME_RE.match(base) else _FALLBACK_MIME


def _is_textual(mime: str) -> bool:
    return mime.startswith("text/") or mime in _TEXTUAL_APPLICATION or mime.endswith("+json")


def attachment_uri(resource_id: str) -> str:
    return f"joplin-resource://{resource_id}"


@dataclass(frozen=True, slots=True)
class TypedBytes:
    """Bytes plus the MIME type to serve them as (see ``_TypedBytesTemplate``)."""

    data: bytes
    mime_type: str


class _TypedBytesTemplate(ResourceTemplate):
    """A resource template whose reads carry a per-resource MIME type.

    The SDK fixes a template's ``mime_type`` when it is registered; attachments
    differ per id. A template function returning ``TypedBytes`` gets its bytes
    served under that MIME type instead.
    """

    async def create_resource(self, uri: str, params: dict[str, Any], context: Any) -> Any:
        resource = await super().create_resource(uri, params, context)
        if isinstance(resource, FunctionResource):
            value = resource.fn()
            if isinstance(value, TypedBytes):
                data = value.data
                return resource.model_copy(
                    update={"mime_type": value.mime_type, "fn": lambda: data}
                )
        return resource


def _use_typed_bytes_template(mcp: MCPServer[Any], uri_template: str) -> None:
    """Swap a registered template for a ``_TypedBytesTemplate`` with the same fields.

    Registering through ``@mcp.resource`` first keeps the SDK's own checks
    (URI/parameter match, path-safety policy). The swap reaches into SDK
    internals; tests/test_attachments.py pins the MIME type it produces, so an
    SDK change that breaks it fails loudly rather than serving octet-stream.
    """
    templates = mcp._resource_manager._templates
    original = templates[uri_template]
    templates[uri_template] = _TypedBytesTemplate.model_construct(
        **{name: getattr(original, name) for name in type(original).model_fields}
    )


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
            async with anyio.create_task_group() as tg:
                if settings.events_poll_seconds > 0:
                    poller = NoteEventPoller(
                        joplin, bus, interval_seconds=settings.events_poll_seconds
                    )
                    tg.start_soon(poller.run)
                try:
                    yield AppContext(settings=settings, joplin=joplin)
                finally:
                    tg.cancel_scope.cancel()
        finally:
            await joplin.aclose()

    read_only = settings.read_only
    # Note changes from Joplin's /events feed are published here for
    # subscriptions/listen streams; see events.py.
    bus = ListenerTrackingBus()
    mcp = MCPServer(
        "Joplin",
        instructions=(
            "Access Joplin notes via the local Joplin Data API (Web Clipper). "
            + (
                "This server is READ-ONLY: it can list, read and search, but not change notes. "
                if read_only
                else "Prefer notes_append / notes_replace_text over notes_update for edits, and "
                "pass expected_updated_time from your last read so concurrent edits aren't lost. "
            )
            + "Note ids are 32-character hex strings; use search or the list tools to find them. "
            + "Read attachments with resources_read."
        ),
        lifespan=lifespan,
        subscriptions=bus,
    )

    def read_tool() -> Callable[[_F], _F]:
        return mcp.tool(annotations=READ_ONLY)

    def write_tool(annotations: ToolAnnotations) -> Callable[[_F], _F]:
        """Register a tool that changes the notebook, unless the server is read-only.

        In read-only mode write tools are not registered at all, so they are absent
        from tools/list rather than present-but-failing.
        """

        def register(fn: _F) -> _F:
            if read_only:
                return fn
            return mcp.tool(annotations=annotations)(fn)

        return register

    async def get_note(app: AppContext, note_id: str) -> dict[str, Any]:
        return await app.joplin.request_json(
            "GET", f"/notes/{note_id}", params={"fields": _NOTE_GET_FIELDS}
        )

    async def put_note_body(app: AppContext, note_id: str, body: str) -> dict[str, Any]:
        return await app.joplin.request_json("PUT", f"/notes/{note_id}", json_body={"body": body})

    # ------------------------------------------------------------------ resources

    @mcp.resource("joplin-note://{note_id}")
    async def read_note_resource(note_id: str, ctx: JoplinCtx) -> str:
        """Read a note's Markdown body."""
        app = ctx.request_context.lifespan_context
        note = await get_note(app, note_id)
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

    async def fetch_attachment(app: AppContext, resource_id: str) -> tuple[dict[str, Any], bytes]:
        """Metadata, then the file, refusing anything over the configured cap."""
        limit = app.settings.max_attachment_bytes
        meta = await app.joplin.request_json(
            "GET",
            f"/resources/{resource_id}",
            params={"fields": "id,title,mime,filename,size"},
        )
        size = meta.get("size")
        # Joplin's recorded size lets us refuse before downloading anything.
        if isinstance(size, int) and size > limit:
            raise AttachmentTooLargeError(
                path=f"/resources/{resource_id}/file", max_bytes=limit, size=size
            )
        data = await app.joplin.download(f"/resources/{resource_id}/file", max_bytes=limit)
        return meta, data

    @mcp.resource("joplin-resource://{resource_id}", mime_type=_FALLBACK_MIME)
    async def read_attachment_resource(resource_id: str, ctx: JoplinCtx) -> TypedBytes:
        """An attachment's file, served with its own MIME type."""
        app = ctx.request_context.lifespan_context
        meta, data = await fetch_attachment(app, resource_id)
        return TypedBytes(data=data, mime_type=_clean_mime(meta.get("mime")))

    _use_typed_bytes_template(mcp, "joplin-resource://{resource_id}")

    # ---------------------------------------------------------------------- notes

    @read_tool()
    async def notes_get(note_id: str, ctx: JoplinCtx) -> Note:
        """Get a single note (title, Markdown body, folder, timestamps) by id.

        Keep `updated_time` if you intend to edit: pass it as `expected_updated_time`.
        """
        app = ctx.request_context.lifespan_context
        return Note.model_validate(await get_note(app, note_id))

    @read_tool()
    async def notes_list(
        ctx: JoplinCtx,
        parent_id: str | None = None,
        page: Page = 1,
        limit: Limit = 20,
        fields: str = "id,title,parent_id,updated_time",
    ) -> PagedResult:
        """List notes, optionally only those directly inside folder `parent_id`.

        `fields` is a comma-separated subset of: id, parent_id, title, body, is_todo,
        todo_due, todo_completed, source_url, author, created_time, updated_time, ...
        Omit `body` when listing many notes. Follow `next_page` while `has_more` is true.
        """
        app = ctx.request_context.lifespan_context
        params: dict[str, Any] = {}
        if parent_id:
            params["parent_id"] = parent_id
        parsed_fields = _parse_fields(fields, NOTE_FIELDS)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/notes", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    @write_tool(CREATES)
    async def notes_create(
        title: str,
        body: str,
        ctx: JoplinCtx,
        parent_id: str | None = None,
    ) -> Note:
        """Create a new note with a Markdown body, in folder `parent_id` if given."""
        app = ctx.request_context.lifespan_context
        payload: dict[str, Any] = {"title": title, "body": body}
        if parent_id:
            payload["parent_id"] = parent_id
        raw = await app.joplin.request_json("POST", "/notes", json_body=payload)
        return Note.model_validate(raw)

    @write_tool(OVERWRITES)
    async def notes_update(
        note_id: str,
        ctx: JoplinCtx,
        title: str | None = None,
        body: str | None = None,
        parent_id: str | None = None,
        expected_updated_time: ExpectedUpdatedTime = None,
    ) -> Note:
        """Rename a note, move it (`parent_id`), or REPLACE its entire body.

        `body` overwrites the whole note. To add or change part of a note, prefer
        `notes_append` or `notes_replace_text`, which can't drop text you didn't
        intend to touch.
        """
        app = ctx.request_context.lifespan_context
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if parent_id is not None:
            payload["parent_id"] = parent_id
        if not payload:
            raise ToolError("Nothing to update: pass at least one of title, body or parent_id")
        if expected_updated_time is not None:
            _check_not_stale(await get_note(app, note_id), expected_updated_time)
        raw = await app.joplin.request_json("PUT", f"/notes/{note_id}", json_body=payload)
        return Note.model_validate(raw)

    @write_tool(CREATES)
    async def notes_append(
        note_id: str,
        text: str,
        ctx: JoplinCtx,
        separator: str = "\n\n",
        expected_updated_time: ExpectedUpdatedTime = None,
    ) -> Note:
        """Append Markdown `text` to the end of a note, leaving existing text untouched.

        `separator` goes between the existing body and the new text (default: a blank
        line). Trailing line endings on the existing body are trimmed first; anything
        else, including trailing spaces (a Markdown hard line break), is kept.
        """
        if not text:
            raise ToolError("Nothing to append: `text` is empty")
        app = ctx.request_context.lifespan_context
        note_raw = await get_note(app, note_id)
        _check_not_stale(note_raw, expected_updated_time)
        body = (note_raw.get("body") or "").rstrip("\r\n")
        new_body = f"{body}{separator}{text}" if body.strip() else text
        if not new_body.endswith("\n"):
            new_body += "\n"
        return Note.model_validate(await put_note_body(app, note_id, new_body))

    @write_tool(EDITS)
    async def notes_replace_text(
        note_id: str,
        find: str,
        replace: str,
        ctx: JoplinCtx,
        expected_count: Annotated[int, Field(ge=1)] = 1,
        expected_updated_time: ExpectedUpdatedTime = None,
    ) -> NoteEditResult:
        """Replace exact text in a note's body (literal match, case-sensitive).

        The edit is refused unless `find` occurs exactly `expected_count` times
        (default 1), so an ambiguous or stale `find` can't change the wrong place.
        Include enough surrounding text in `find` to make it unique.
        """
        if not find:
            raise ToolError("`find` must not be empty")
        app = ctx.request_context.lifespan_context
        note_raw = await get_note(app, note_id)
        _check_not_stale(note_raw, expected_updated_time)
        body = note_raw.get("body") or ""
        found = body.count(find)
        if found != expected_count:
            raise ToolError(
                f"`find` occurs {found} time(s) in the note, expected {expected_count}. "
                + (
                    "Re-read the note; the text may have changed."
                    if found == 0
                    else "Make `find` longer to pin down one occurrence, or set expected_count."
                )
            )
        updated = await put_note_body(app, note_id, body.replace(find, replace))
        return NoteEditResult.model_validate({**updated, "replacements": found})

    @write_tool(DELETES)
    async def notes_delete(note_id: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Delete a note (Joplin moves it to the trash, where it can be restored)."""
        app = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/notes/{note_id}")
        return {"deleted": True, "id": note_id}

    # -------------------------------------------------------------------- folders

    @read_tool()
    async def folders_list(
        ctx: JoplinCtx,
        page: Page = 1,
        limit: Limit = 50,
        fields: str = "id,title,parent_id",
    ) -> PagedResult:
        """List folders (notebooks), flat. Use `folders_tree` for the hierarchy."""
        app = ctx.request_context.lifespan_context
        params: dict[str, Any] = {}
        parsed_fields = _parse_fields(fields, FOLDER_FIELDS)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/folders", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    @read_tool()
    async def folders_tree(ctx: JoplinCtx) -> list[FolderNode]:
        """Return the complete folder (notebook) hierarchy with ids and titles."""
        app = ctx.request_context.lifespan_context
        folders = await app.joplin.get_all("/folders", params={"fields": "id,title,parent_id"})
        return _build_folder_tree(folders)

    @write_tool(CREATES)
    async def folders_create(
        title: str,
        ctx: JoplinCtx,
        parent_id: str | None = None,
    ) -> Folder:
        """Create a folder (notebook), nested under `parent_id` if given."""
        app = ctx.request_context.lifespan_context
        payload: dict[str, Any] = {"title": title}
        if parent_id:
            payload["parent_id"] = parent_id
        raw = await app.joplin.request_json("POST", "/folders", json_body=payload)
        return Folder.model_validate(raw)

    @write_tool(UPDATES)
    async def folders_update(
        folder_id: str,
        ctx: JoplinCtx,
        title: str | None = None,
        parent_id: str | None = None,
    ) -> Folder:
        """Rename a folder and/or move it under another folder (`parent_id`)."""
        app = ctx.request_context.lifespan_context
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if parent_id is not None:
            payload["parent_id"] = parent_id
        if not payload:
            raise ToolError("At least one of 'title' or 'parent_id' must be provided")
        raw = await app.joplin.request_json("PUT", f"/folders/{folder_id}", json_body=payload)
        return Folder.model_validate(raw)

    @write_tool(DELETES)
    async def folders_delete(folder_id: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Delete a folder (notebook) and the notes in it (Joplin moves them to the trash)."""
        app = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/folders/{folder_id}")
        return {"deleted": True, "id": folder_id}

    # ----------------------------------------------------------------------- tags

    @read_tool()
    async def tags_list(
        ctx: JoplinCtx,
        page: Page = 1,
        limit: Limit = 50,
        fields: str = "id,title",
    ) -> PagedResult:
        """List tags."""
        app = ctx.request_context.lifespan_context
        params: dict[str, Any] = {}
        parsed_fields = _parse_fields(fields, TAG_FIELDS)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/tags", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    @write_tool(CREATES)
    async def tags_create(title: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Create a tag."""
        app = ctx.request_context.lifespan_context
        return await app.joplin.request_json("POST", "/tags", json_body={"title": title})

    @write_tool(DELETES)
    async def tags_delete(tag_id: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Delete a tag (it is removed from every note that has it)."""
        app = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/tags/{tag_id}")
        return {"deleted": True, "id": tag_id}

    @write_tool(UPDATES)
    async def tags_add_note(tag_id: str, note_id: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Attach a tag to a note."""
        app = ctx.request_context.lifespan_context
        # Joplin expects a body with {"id": <note_id>}.
        await app.joplin.request_json("POST", f"/tags/{tag_id}/notes", json_body={"id": note_id})
        return {"tag_id": tag_id, "note_id": note_id, "attached": True}

    @write_tool(OVERWRITES)
    async def tags_remove_note(tag_id: str, note_id: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Remove a tag from a note (the tag itself remains)."""
        app = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/tags/{tag_id}/notes/{note_id}")
        return {"tag_id": tag_id, "note_id": note_id, "attached": False}

    # ------------------------------------------------------ resources (attachments)

    @read_tool()
    async def resources_list(
        ctx: JoplinCtx,
        page: Page = 1,
        limit: Limit = 50,
        fields: str = "id,title,mime,filename,file_extension,size,updated_time",
    ) -> PagedResult:
        """List attachments (resources) across all notes."""
        app = ctx.request_context.lifespan_context
        params: dict[str, Any] = {}
        parsed_fields = _parse_fields(fields, RESOURCE_FIELDS)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/resources", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    @read_tool()
    async def resources_get(resource_id: str, ctx: JoplinCtx) -> Resource:
        """Get an attachment's metadata (title, MIME type, filename, size) by id."""
        app = ctx.request_context.lifespan_context
        raw = await app.joplin.request_json(
            "GET",
            f"/resources/{resource_id}",
            params={
                "fields": "id,title,mime,filename,file_extension,size,created_time,updated_time"
            },
        )
        return Resource.model_validate(raw)

    @read_tool()
    async def resources_read(resource_id: ResourceId, ctx: JoplinCtx) -> list[ContentBlock]:
        """Read an attachment as native content: images you can see (PNG, JPEG, GIF,
        WebP), audio, text files as text, anything else as an embedded file.

        Files over the server's size limit (MCP_MAX_ATTACHMENT_BYTES, default 10 MiB)
        are refused; check `size` with resources_get first if unsure.
        """
        app = ctx.request_context.lifespan_context
        meta, data = await fetch_attachment(app, resource_id)
        mime = _clean_mime(meta.get("mime"))
        name = meta.get("filename") or meta.get("title") or resource_id
        summary = TextContent(type="text", text=f"Attachment {name!r} ({mime}, {len(data)} bytes)")
        uri = attachment_uri(resource_id)
        encoded = base64.b64encode(data).decode("ascii")
        block: ContentBlock
        if mime in _VIEWABLE_IMAGES:
            block = ImageContent(type="image", data=encoded, mime_type=mime)
        elif mime.startswith("audio/"):
            block = AudioContent(type="audio", data=encoded, mime_type=mime)
        else:
            text: str | None = None
            if _is_textual(mime):
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    text = None  # Mislabelled binary: send it as a blob instead.
            contents: TextResourceContents | BlobResourceContents = (
                TextResourceContents(uri=uri, mime_type=mime, text=text)
                if text is not None
                else BlobResourceContents(uri=uri, mime_type=mime, blob=encoded)
            )
            block = EmbeddedResource(type="resource", resource=contents)
        return [summary, block]

    @read_tool()
    async def resources_get_content(resource_id: str, ctx: JoplinCtx) -> ResourceBlob:
        """Get an attachment's file bytes, base64-encoded in JSON. Prefer resources_read,
        which returns images, audio and text natively. Check `size` first: large files
        are expensive to return."""
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

    @write_tool(CREATES)
    async def resources_create(
        filename: str,
        data_base64: str,
        ctx: JoplinCtx,
        mime: str = "application/octet-stream",
        title: str | None = None,
    ) -> Resource:
        """Upload a new attachment from base64-encoded bytes. Link it to a note with
        `notes_attach_resource`."""
        app = ctx.request_context.lifespan_context
        try:
            raw_bytes = base64.b64decode(data_base64, validate=True)
        except binascii.Error as exc:
            raise ToolError("Invalid base64 data in 'data_base64'") from exc

        raw = await app.joplin.create_resource(
            filename=filename,
            data=raw_bytes,
            mime=mime,
            title=title,
        )
        return Resource.model_validate(raw)

    @write_tool(DELETES)
    async def resources_delete(resource_id: str, ctx: JoplinCtx) -> dict[str, Any]:
        """Delete an attachment. Links to it in notes are left behind (broken); use
        `notes_detach_resource` first to remove them."""
        app = ctx.request_context.lifespan_context
        await app.joplin.request_json("DELETE", f"/resources/{resource_id}")
        return {"deleted": True, "id": resource_id}

    @read_tool()
    async def notes_list_resources(
        note_id: str,
        ctx: JoplinCtx,
        page: Page = 1,
        limit: Limit = 50,
        fields: str = "id,title,mime,filename,file_extension,size,updated_time",
    ) -> PagedResult:
        """List the attachments linked from a note."""
        app = ctx.request_context.lifespan_context
        params: dict[str, Any] = {}
        parsed_fields = _parse_fields(fields, RESOURCE_FIELDS)
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged(
            f"/notes/{note_id}/resources", page=page, limit=limit, params=params
        )
        return _paged_result(raw, page=page, limit=limit)

    @write_tool(UPDATES)
    async def notes_attach_resource(
        note_id: str,
        resource_id: str,
        ctx: JoplinCtx,
        alt_text: str | None = None,
        embed: bool = False,
    ) -> Note:
        """Link an attachment from a note by appending a Markdown link (or an image
        embed with `embed=true`). Does nothing if that exact link is already there."""
        app = ctx.request_context.lifespan_context
        note_raw = await get_note(app, note_id)
        body = note_raw.get("body") or ""
        display = _escape_link_label(alt_text or resource_id)
        snippet = f"![{display}](:/{resource_id})" if embed else f"[{display}](:/{resource_id})"
        if snippet in body:
            # Already linked: don't rewrite the note (that would bump updated_time).
            return Note.model_validate(note_raw)
        return Note.model_validate(
            await put_note_body(app, note_id, f"{body.rstrip()}\n\n{snippet}\n")
        )

    @write_tool(OVERWRITES)
    async def notes_detach_resource(
        note_id: str,
        resource_id: str,
        ctx: JoplinCtx,
        expected_updated_time: ExpectedUpdatedTime = None,
    ) -> NoteDetachResult:
        """Remove the links and embeds that reference an attachment from a note.

        Removes Markdown links/images (``[x](:/id)``, ``![x](:/id)``), reference
        definitions (``[ref]: :/id``) and HTML ``<img>``/``<a>`` embeds pointing at the
        resource. Other text on the same line is kept. The resource itself is not
        deleted (use ``resources_delete``). If nothing references it, the note is left
        untouched and ``links_removed`` is 0.
        """
        app = ctx.request_context.lifespan_context
        note_raw = await get_note(app, note_id)
        body = note_raw.get("body") or ""
        updated_body, removed = remove_resource_links(body, resource_id)
        if not removed:
            # Don't write: a no-op PUT would still bump updated_time and re-sync.
            return NoteDetachResult.model_validate({**note_raw, "links_removed": 0})
        _check_not_stale(note_raw, expected_updated_time)
        updated_raw = await put_note_body(app, note_id, updated_body)
        return NoteDetachResult.model_validate({**updated_raw, "links_removed": removed})

    # --------------------------------------------------------------------- search

    @read_tool()
    async def search(
        query: str,
        ctx: JoplinCtx,
        search_type: Literal["note", "folder", "tag"] = "note",
        page: Page = 1,
        limit: Limit = 20,
        fields: str = "id,title,parent_id,updated_time",
    ) -> PagedResult:
        """Search Joplin using its full-text query syntax (default: notes).

        Syntax (combine freely; terms are ANDed unless `any:1`):
        - `word`, `"exact phrase"`, prefix wildcard `wor*`, exclude with `-word`
        - `title:word`, `body:word`, `tag:name` (wildcards ok, e.g. `tag:proj*`)
        - `notebook:Name` (searches that notebook and its sub-notebooks)
        - `created:20240101`, `updated:day-7` (last 7 days), also `month-1`, `year-0`
        - `type:todo` or `type:note`, `iscompleted:0`, `due:day+3`
        - `any:1` to match ANY term instead of all

        For `search_type` "folder" or "tag", `query` matches titles (use `*` wildcards).
        """
        app = ctx.request_context.lifespan_context
        params: dict[str, Any] = {"query": query, "type": search_type}
        parsed_fields = _parse_fields(fields, _SEARCH_FIELDS[search_type])
        if parsed_fields:
            params["fields"] = parsed_fields
        raw = await app.joplin.get_paged("/search", page=page, limit=limit, params=params)
        return _paged_result(raw, page=page, limit=limit)

    return mcp
