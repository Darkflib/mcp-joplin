"""Ask the user before a delete (MCP_CONFIRM_DELETES).

Each delete tool takes a parameter filled by a resolver here instead of by the
model. The resolver either returns a plain `DeleteConfirmation` (no question
asked) or an `Elicit(...)` marker, and the SDK asks the user over whichever
channel the protocol has: an `InputRequiredResult` round trip on 2026-07-28, or a
mid-call `elicitation/create` request on earlier versions where the transport can
carry one.

Modes:
- off (default): never ask; deletes behave as before.
- ask: ask when the client can show a prompt; otherwise delete as before.
- require: ask, and refuse to delete when the client can't be asked.

Resolvers live at module level, and their annotations use only names importable
here: the SDK resolves them with `typing.get_type_hints`, so a TYPE_CHECKING-only
name (such as AppContext) would make the `ctx` parameter unclassifiable.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from mcp.server.mcpserver import Context, Elicit, Resolve
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.resolve import AcceptedElicitation, ElicitationResult
from mcp_types.version import is_version_at_least
from pydantic import BaseModel, Field

# First protocol revision that carries elicitation in the tools/call round trip.
_INPUT_REQUIRED_VERSION = "2026-07-28"


class DeleteConfirmation(BaseModel):
    """The form the user sees. Accepting with the box ticked confirms."""

    confirm: bool = Field(default=True, title="Delete", description="Untick to keep it.")


def _can_ask(ctx: Context[Any, Any]) -> bool:
    """Whether this client can show the user a prompt on this request."""
    capabilities = ctx.client_capabilities
    if capabilities is None or capabilities.elicitation is None:
        return False
    version = ctx.protocol_version
    if version is not None and is_version_at_least(version, _INPUT_REQUIRED_VERSION):
        return True
    # Earlier protocols need a server-to-client request mid-call, which a stateless
    # HTTP request can't carry (stdio can).
    return bool(ctx.session.can_send_request)


async def _confirm(
    ctx: Context[Any, Any],
    *,
    what: str,
    item_id: str,
    path: str,
    fields: str,
    describe: Callable[[dict[str, Any]], str],
) -> DeleteConfirmation | Elicit[DeleteConfirmation]:
    app = ctx.request_context.lifespan_context
    mode = app.settings.confirm_deletes
    if mode == "off":
        return DeleteConfirmation()
    if not _can_ask(ctx):
        if mode == "require":
            raise ToolError(
                f"Not deleted: this server requires the user to confirm deletes "
                f"(MCP_CONFIRM_DELETES=require), and this client can't ask them. "
                f"The {what} {item_id} was left as it is."
            )
        return DeleteConfirmation()
    # Name the item in the question; a 404 here surfaces as the usual Joplin error.
    item = await app.joplin.request_json("GET", path, params={"fields": fields})
    return Elicit(describe(item), DeleteConfirmation)


def _name(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return f"“{' '.join(value.split())}”"
    return "(untitled)"


async def confirm_note_delete(
    note_id: str, ctx: Context[Any, Any]
) -> DeleteConfirmation | Elicit[DeleteConfirmation]:
    return await _confirm(
        ctx,
        what="note",
        item_id=note_id,
        path=f"/notes/{note_id}",
        fields="id,title",
        describe=lambda n: (
            f"Delete the note {_name(n, 'title')}? "
            "Joplin moves it to the trash, where it can be restored."
        ),
    )


async def confirm_folder_delete(
    folder_id: str, ctx: Context[Any, Any]
) -> DeleteConfirmation | Elicit[DeleteConfirmation]:
    return await _confirm(
        ctx,
        what="notebook",
        item_id=folder_id,
        path=f"/folders/{folder_id}",
        fields="id,title",
        describe=lambda f: (
            f"Delete the notebook {_name(f, 'title')} and every note in it? "
            "Joplin moves them to the trash, where they can be restored."
        ),
    )


async def confirm_tag_delete(
    tag_id: str, ctx: Context[Any, Any]
) -> DeleteConfirmation | Elicit[DeleteConfirmation]:
    return await _confirm(
        ctx,
        what="tag",
        item_id=tag_id,
        path=f"/tags/{tag_id}",
        fields="id,title",
        describe=lambda t: (
            f"Delete the tag {_name(t, 'title')}? "
            "It is removed from every note that has it; the notes themselves are kept."
        ),
    )


async def confirm_resource_delete(
    resource_id: str, ctx: Context[Any, Any]
) -> DeleteConfirmation | Elicit[DeleteConfirmation]:
    return await _confirm(
        ctx,
        what="attachment",
        item_id=resource_id,
        path=f"/resources/{resource_id}",
        fields="id,title,filename",
        describe=lambda r: (
            f"Delete the attachment {_name(r, 'filename', 'title')}? "
            "Notes that link to it will show a broken link."
        ),
    )


Confirmation = ElicitationResult[DeleteConfirmation]
NoteDeleteConfirmation = Annotated[Confirmation, Resolve(confirm_note_delete)]
FolderDeleteConfirmation = Annotated[Confirmation, Resolve(confirm_folder_delete)]
TagDeleteConfirmation = Annotated[Confirmation, Resolve(confirm_tag_delete)]
ResourceDeleteConfirmation = Annotated[Confirmation, Resolve(confirm_resource_delete)]


def require_confirmed(confirmation: Confirmation, what: str, item_id: str) -> None:
    """Raise unless the user confirmed (or no confirmation was needed)."""
    if isinstance(confirmation, AcceptedElicitation) and confirmation.data.confirm:
        return
    raise ToolError(
        f"Not deleted: the user declined to delete the {what} {item_id}. "
        "Leave it unless they ask again."
    )
