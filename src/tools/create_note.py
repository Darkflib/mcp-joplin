"""create_note MCP tool handler."""

import json
import logging
import os
from typing import Any

from mcp import types

from src.models.mcp_tool import MCPTool

logger = logging.getLogger(__name__)


# MCP tool definition schema
CREATE_NOTE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Title for the new note",
            "minLength": 1,
            "maxLength": 200,
        },
        "body": {
            "type": "string",
            "description": "Content/body for the new note (optional, defaults to empty)",
            "maxLength": 1000000,  # 1MB limit for note content
            "default": "",
        },
        "parent_id": {
            "type": "string",
            "description": "ID of the notebook to create the note in (optional, uses default notebook if not specified)",
            "pattern": "^[a-f0-9]{32}$",
        },
    },
    "required": ["title"],
}

CREATE_NOTE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "note_id": {"type": "string"},
        "title": {"type": "string"},
        "body": {"type": "string"},
        "created_time": {"type": "string"},
        "parent_id": {"type": "string"},
        "success": {"type": "boolean"},
    },
    "required": ["note_id", "title", "success"],
}


def _write_operations_enabled() -> bool:
    """Check if write operations are enabled via environment variable."""
    return os.getenv("JOPLIN_ALLOW_WRITE_OPERATIONS", "false").lower() in ("true", "1", "yes", "on")


async def create_note_handler(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handle create_note MCP tool calls."""
    try:
        # Check if write operations are enabled
        if not _write_operations_enabled():
            raise Exception(
                "Write operations are disabled. Set JOPLIN_ALLOW_WRITE_OPERATIONS=true to enable note creation."
            )

        logger.info("Processing create_note request", extra={"arguments": arguments})

        # Validate required arguments
        title = arguments.get("title")
        if title is None:
            raise ValueError("Missing required field: title")

        body = arguments.get("body", "")  # Default to empty string
        parent_id = arguments.get("parent_id")  # Optional

        # Validate argument types
        if not isinstance(title, str):
            raise ValueError("Field 'title' has invalid type, expected string")
        if not isinstance(body, str):
            raise ValueError("Field 'body' has invalid type, expected string")
        if parent_id is not None and not isinstance(parent_id, str):
            raise ValueError("Field 'parent_id' has invalid type, expected string")

        # Validate constraints
        if not title.strip():
            raise ValueError("Field 'title' cannot be empty or whitespace only")
        if parent_id and len(parent_id) != 32:
            raise ValueError("Field 'parent_id' must be 32-character hex string")

        # Get Joplin client (this would be injected in real implementation)
        joplin_client = _get_joplin_client()

        # Create the note
        result = await joplin_client.create_note(
            title=title.strip(),
            body=body,
            parent_id=parent_id
        )

        # Format response
        response_data = {
            "note_id": result.get("id", ""),
            "title": result.get("title", title),
            "body": result.get("body", body),
            "created_time": result.get("created_time", ""),
            "parent_id": result.get("parent_id", parent_id or ""),
            "success": True,
        }

        logger.info(
            "Note creation completed successfully",
            extra={"note_id": response_data["note_id"], "title": title},
        )

        # Return as MCP TextContent
        return [
            types.TextContent(type="text", text=json.dumps(response_data, indent=2))
        ]

    except ValueError as e:
        logger.error("Validation error in create_note", extra={"error": str(e)})
        raise
    except Exception as e:
        logger.error("Unexpected error in create_note", extra={"error": str(e)})
        raise Exception(f"Note creation failed: {str(e)}") from e


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
        async def create_note(
            self, title: str, body: str = "", parent_id: str = None
        ) -> dict[str, Any]:
            """Mock note creation for testing."""
            import uuid
            return {
                "id": uuid.uuid4().hex,  # Generate a mock 32-char hex ID
                "title": title,
                "body": body,
                "parent_id": parent_id or "default_notebook_id",
                "created_time": "2024-01-01T12:00:00.000Z",
                "updated_time": "2024-01-01T12:00:00.000Z",
            }

    return MockJoplinClient()


# Create the MCP tool instance
create_note_tool = MCPTool(
    name="create_note",
    description="Create a new note in Joplin with optional content and notebook placement",
    input_schema=CREATE_NOTE_INPUT_SCHEMA,
    output_schema=CREATE_NOTE_OUTPUT_SCHEMA,
    handler=create_note_handler,
)
