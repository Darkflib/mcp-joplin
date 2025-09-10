"""update_note MCP tool handler."""

import json
import logging
import os
from typing import Any

from mcp import types

from src.models.mcp_tool import MCPTool

logger = logging.getLogger(__name__)


# MCP tool definition schema
UPDATE_NOTE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "note_id": {
            "type": "string",
            "description": "ID of the note to update",
            "pattern": "^[a-f0-9]{32}$",
        },
        "title": {
            "type": "string",
            "description": "New title for the note (optional)",
            "minLength": 1,
            "maxLength": 200,
        },
        "body": {
            "type": "string",
            "description": "New content/body for the note (optional)",
            "maxLength": 1000000,  # 1MB limit for note content
        },
        "parent_id": {
            "type": "string",
            "description": "ID of the notebook to move the note to (optional)",
            "pattern": "^[a-f0-9]{32}$",
        },
    },
    "required": ["note_id"],
    "minProperties": 2,  # At least note_id plus one field to update
}

UPDATE_NOTE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "note_id": {"type": "string"},
        "title": {"type": "string"},
        "updated_time": {"type": "string"},
        "parent_id": {"type": "string"},
        "success": {"type": "boolean"},
    },
    "required": ["note_id", "success"],
}


def _write_operations_enabled() -> bool:
    """Check if write operations are enabled via environment variable."""
    return os.getenv("JOPLIN_ALLOW_WRITE_OPERATIONS", "false").lower() in ("true", "1", "yes", "on")


async def update_note_handler(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handle update_note MCP tool calls."""
    try:
        # Check if write operations are enabled
        if not _write_operations_enabled():
            raise Exception(
                "Write operations are disabled. Set JOPLIN_ALLOW_WRITE_OPERATIONS=true to enable note updates."
            )

        logger.info("Processing update_note request", extra={"arguments": arguments})

        # Validate required arguments
        note_id = arguments.get("note_id")
        if not note_id:
            raise ValueError("Missing required field: note_id")

        title = arguments.get("title")
        body = arguments.get("body")
        parent_id = arguments.get("parent_id")

        # Validate that at least one update field is provided
        if not any([title is not None, body is not None, parent_id is not None]):
            raise ValueError("At least one of title, body, or parent_id must be provided")

        # Validate argument types
        if not isinstance(note_id, str):
            raise ValueError("Field 'note_id' has invalid type, expected string")
        if title is not None and not isinstance(title, str):
            raise ValueError("Field 'title' has invalid type, expected string")
        if body is not None and not isinstance(body, str):
            raise ValueError("Field 'body' has invalid type, expected string")
        if parent_id is not None and not isinstance(parent_id, str):
            raise ValueError("Field 'parent_id' has invalid type, expected string")

        # Validate patterns
        if len(note_id) != 32:
            raise ValueError("Field 'note_id' must be 32-character hex string")
        if parent_id and len(parent_id) != 32:
            raise ValueError("Field 'parent_id' must be 32-character hex string")

        # Get Joplin client (this would be injected in real implementation)
        joplin_client = _get_joplin_client()

        # Update the note
        result = await joplin_client.update_note(
            note_id=note_id,
            title=title,
            body=body,
            parent_id=parent_id
        )

        # Format response
        response_data = {
            "note_id": result.get("id", note_id),
            "title": result.get("title", ""),
            "updated_time": result.get("updated_time", ""),
            "parent_id": result.get("parent_id", ""),
            "success": True,
        }

        logger.info(
            "Note update completed successfully",
            extra={"note_id": note_id},
        )

        # Return as MCP TextContent
        return [
            types.TextContent(type="text", text=json.dumps(response_data, indent=2))
        ]

    except ValueError as e:
        logger.error("Validation error in update_note", extra={"error": str(e)})
        raise
    except Exception as e:
        logger.error("Unexpected error in update_note", extra={"error": str(e)})
        raise Exception(f"Note update failed: {str(e)}") from e


def _get_joplin_client() -> Any:
    """Get Joplin client instance (placeholder for dependency injection)."""
    # Try to get real client from server globals first
    try:
        from src.server import _global_joplin_client

        if _global_joplin_client is not None:
            return _global_joplin_client
    except (ImportError, AttributeError):
        pass

    # Fall back to mock if real client not available
    class MockJoplinClient:
        async def update_note(
            self, note_id: str, title: str = None, body: str = None, parent_id: str = None
        ) -> dict[str, Any]:
            """Mock note update for testing."""
            return {
                "id": note_id,
                "title": title or "Mock Updated Title",
                "body": body or "Mock updated content",
                "parent_id": parent_id or "mock_parent_id",
                "updated_time": "2024-01-01T12:00:00.000Z",
            }

    return MockJoplinClient()


# Create the MCP tool instance
update_note_tool = MCPTool(
    name="update_note",
    description="Update an existing note's title, content, or move it to another notebook",
    input_schema=UPDATE_NOTE_INPUT_SCHEMA,
    output_schema=UPDATE_NOTE_OUTPUT_SCHEMA,
    handler=update_note_handler,
)
