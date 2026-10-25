"""Domain errors."""

from __future__ import annotations

from dataclasses import dataclass

from mcp.server.mcpserver.exceptions import ResourceError

# Joplin error bodies can be long (stack traces); keep what reaches the model short.
_MAX_DETAIL_CHARS = 300


@dataclass(frozen=True, slots=True)
class JoplinApiError(ResourceError):
    """Raised when the Joplin Data API returns a non-success response.

    Subclasses the SDK's ``ResourceError`` so MCPServer treats it as an
    anticipated failure: tools return ``is_error`` with this message and resource
    reads return it as a protocol error. Any other exception type is reported to
    the client only as an opaque "Error executing tool".

    ``path`` is the request path only. Never store the full request URL here: it
    carries the Joplin token as a query parameter, and this error's message is
    returned to MCP clients and written to logs.
    """

    status_code: int
    method: str
    path: str
    detail: str = ""

    def __str__(self) -> str:
        detail = self.detail.strip()
        if len(detail) > _MAX_DETAIL_CHARS:
            detail = detail[:_MAX_DETAIL_CHARS] + "…"
        suffix = f": {detail}" if detail else ""
        return f"Joplin API error {self.status_code} for {self.method} {self.path}{suffix}"


@dataclass(frozen=True, slots=True)
class JoplinConnectionError(ResourceError):
    """Raised when the Joplin Data API can't be reached at all (refused, timeout, ...).

    A ``ResourceError`` for the same reason as ``JoplinApiError``.
    """

    method: str
    path: str
    reason: str

    def __str__(self) -> str:
        return (
            f"Could not reach the Joplin Data API for {self.method} {self.path} ({self.reason}). "
            "Is Joplin running with the Web Clipper service enabled?"
        )


@dataclass(frozen=True, slots=True)
class CollectionTooLargeError(ResourceError):
    """A collection was too large to load in full (see ``JoplinClient.get_all``)."""

    path: str
    max_items: int

    def __str__(self) -> str:
        return (
            f"{self.path} has more than {self.max_items} items; refusing to load them all at once"
        )


@dataclass(frozen=True, slots=True)
class AttachmentTooLargeError(ResourceError):
    """An attachment exceeded ``MCP_MAX_ATTACHMENT_BYTES`` (see ``JoplinClient.download``)."""

    path: str
    max_bytes: int
    size: int | None = None

    def __str__(self) -> str:
        actual = f" ({self.size} bytes)" if self.size is not None else ""
        return (
            f"{self.path} is larger than the {self.max_bytes}-byte attachment limit{actual}; "
            "raise MCP_MAX_ATTACHMENT_BYTES to allow it"
        )
