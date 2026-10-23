"""Domain errors."""

from __future__ import annotations

from dataclasses import dataclass

# Joplin error bodies can be long (stack traces); keep what reaches the model short.
_MAX_DETAIL_CHARS = 300


@dataclass(frozen=True, slots=True)
class JoplinApiError(RuntimeError):
    """Raised when the Joplin Data API returns a non-success response.

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
class JoplinConnectionError(RuntimeError):
    """Raised when the Joplin Data API can't be reached at all (refused, timeout, ...)."""

    method: str
    path: str
    reason: str

    def __str__(self) -> str:
        return (
            f"Could not reach the Joplin Data API for {self.method} {self.path} ({self.reason}). "
            "Is Joplin running with the Web Clipper service enabled?"
        )
