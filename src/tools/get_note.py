"""get_note MCP tool handler."""

import json
import logging
from typing import Any

from mcp import types

from src.models.mcp_tool import MCPTool

logger = logging.getLogger(__name__)


# MCP tool definition schema
GET_NOTE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "note_id": {
            "type": "string",
            "description": "Unique identifier of the note to retrieve",
            "pattern": "^[a-f0-9]{32}$",
        },
        "include_body": {
            "type": "boolean",
            "description": "Whether to include full note content",
            "default": True,
        },
    },
    "required": ["note_id"],
}

GET_NOTE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "body": {"type": "string"},
        "parent_id": {"type": "string"},
        "created_time": {"type": "integer"},
        "updated_time": {"type": "integer"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["id", "title", "parent_id", "created_time", "updated_time"],
}


async def get_note_handler(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handle get_note MCP tool calls."""
    try:
        logger.info("Processing get_note request", extra={"arguments": arguments})

        # Validate required arguments
        note_id = arguments.get("note_id")
        if not note_id:
            raise ValueError("Missing required field: note_id")

        include_body = arguments.get("include_body", True)

        # Validate argument types
        if not isinstance(note_id, str):
            raise ValueError("Field 'note_id' has invalid type, expected string")
        if not isinstance(include_body, bool):
            raise ValueError("Field 'include_body' has invalid type, expected boolean")

        # Validate note_id pattern
        if len(note_id) != 32 or not all(c in "0123456789abcdef" for c in note_id):
            raise ValueError("Field 'note_id' must match pattern ^[a-f0-9]{32}$")

        # Get Joplin client (this would be injected in real implementation)
        joplin_client = _get_joplin_client()

        # Retrieve note
        note_data = await joplin_client.get_note(note_id, include_body=include_body)

        # Format response
        response_data = {
            "id": note_data["id"],
            "title": note_data["title"],
            "parent_id": note_data["parent_id"],
            "created_time": note_data["created_time"],
            "updated_time": note_data["updated_time"],
            "tags": note_data.get("tags", []),
        }

        # Include body if requested
        if include_body and "body" in note_data:
            response_data["body"] = note_data["body"]

        logger.info("Note retrieved successfully", extra={"note_id": note_id})

        # Return as MCP TextContent
        return [
            types.TextContent(type="text", text=json.dumps(response_data, indent=2))
        ]

    except ValueError as e:
        logger.error("Validation error in get_note", extra={"error": str(e)})
        raise
    except Exception as e:
        logger.error("Unexpected error in get_note", extra={"error": str(e)})
        # Check if it's a not found error
        if "not found" in str(e).lower() or "404" in str(e):
            raise Exception(f"Note not found: {note_id}") from e
        raise Exception(f"Failed to retrieve note: {str(e)}") from e


def _get_joplin_client():
    """Get Joplin client instance (placeholder for dependency injection)."""

    # In real implementation, this would be injected via DI container
    # For now, return a mock that satisfies the interface
    class MockJoplinClient:
        async def get_note(self, note_id: str, include_body: bool = True):
            # Mock implementation - real would use actual JoplinClient
            if note_id == "nonexistent123456789012345678901234":
                raise Exception("Note not found")

            note_data = {
                "id": note_id,
                "title": "Mock Note Title",
                "parent_id": "mock_notebook_12345678901234567890abcd",
                "created_time": 1704067200000,
                "updated_time": 1704070800000,
                "tags": ["test", "mock"],
            }

            if include_body:
                note_data["body"] = "# Mock Note\n\nThis is mock content for testing."

            return note_data

    return MockJoplinClient()


# Create the MCP tool instance
get_note_tool = MCPTool(
    name="get_note",
    description="Retrieve full content and metadata for a specific note",
    input_schema=GET_NOTE_INPUT_SCHEMA,
    output_schema=GET_NOTE_OUTPUT_SCHEMA,
    handler=get_note_handler,
)
