"""get_notes_in_notebook MCP tool handler."""

import json
import logging
from typing import Any

from mcp import types

from src.models.mcp_tool import MCPTool

logger = logging.getLogger(__name__)


# MCP tool definition schema
GET_NOTES_IN_NOTEBOOK_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "notebook_id": {
            "type": "string",
            "description": "ID of the notebook to query",
            "pattern": "^[a-f0-9]{32}$",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of notes to return",
            "minimum": 1,
            "maximum": 100,
            "default": 20,
        },
        "offset": {
            "type": "integer",
            "description": "Number of notes to skip for pagination",
            "minimum": 0,
            "default": 0,
        },
    },
    "required": ["notebook_id"],
}

GET_NOTES_IN_NOTEBOOK_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "created_time": {"type": "integer"},
                    "updated_time": {"type": "integer"},
                },
                "required": ["id", "title", "created_time", "updated_time"],
            },
        },
        "total_count": {"type": "integer", "minimum": 0},
        "has_more": {"type": "boolean"},
    },
    "required": ["notes", "total_count", "has_more"],
}


async def get_notes_in_notebook_handler(
    arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Handle get_notes_in_notebook MCP tool calls."""
    try:
        logger.info(
            "Processing get_notes_in_notebook request", extra={"arguments": arguments}
        )

        # Validate required arguments
        notebook_id = arguments.get("notebook_id")
        if not notebook_id:
            raise ValueError("Missing required field: notebook_id")

        limit = arguments.get("limit", 20)
        offset = arguments.get("offset", 0)

        # Validate argument types
        if not isinstance(notebook_id, str):
            raise ValueError("Field 'notebook_id' has invalid type, expected string")
        if not isinstance(limit, int):
            raise ValueError("Field 'limit' has invalid type, expected integer")
        if not isinstance(offset, int):
            raise ValueError("Field 'offset' has invalid type, expected integer")

        # Validate constraints
        if len(notebook_id) != 32 or not all(
            c in "0123456789abcdef" for c in notebook_id
        ):
            raise ValueError("Field 'notebook_id' must match pattern ^[a-f0-9]{32}$")

        if limit < 1 or limit > 100:
            raise ValueError("Field 'limit' must be between 1 and 100")

        if offset < 0:
            raise ValueError("Field 'offset' must be >= 0")

        # Get Joplin client (this would be injected in real implementation)
        joplin_client = _get_joplin_client()

        # Get notes in notebook
        notes_data = await joplin_client.get_notes_in_notebook(
            notebook_id=notebook_id, limit=limit, offset=offset
        )

        notes_list = notes_data.get("notes", [])
        total_count = notes_data.get("total_count", len(notes_list))
        has_more = notes_data.get("has_more", False)

        # Format response
        response_data = {
            "notes": notes_list,
            "total_count": total_count,
            "has_more": has_more,
        }

        logger.info(
            "Notes in notebook retrieved successfully",
            extra={
                "notebook_id": notebook_id,
                "notes_count": len(notes_list),
                "has_more": has_more,
            },
        )

        # Return as MCP TextContent
        return [
            types.TextContent(type="text", text=json.dumps(response_data, indent=2))
        ]

    except ValueError as e:
        logger.error(
            "Validation error in get_notes_in_notebook", extra={"error": str(e)}
        )
        raise
    except Exception as e:
        logger.error(
            "Unexpected error in get_notes_in_notebook", extra={"error": str(e)}
        )
        raise Exception(f"Failed to get notes in notebook: {str(e)}") from e


def _get_joplin_client():
    """Get Joplin client instance (placeholder for dependency injection)."""

    # In real implementation, this would be injected via DI container
    class MockJoplinClient:
        async def get_notes_in_notebook(
            self, notebook_id: str, limit: int = 20, offset: int = 0
        ):
            # Mock implementation - real would use actual JoplinClient
            mock_notes = []

            # Generate mock notes based on pagination
            for i in range(limit):
                note_num = offset + i + 1
                mock_notes.append(
                    {
                        "id": f"note{note_num:032d}",  # 32-char hex format
                        "title": f"Note {note_num} in Notebook",
                        "created_time": 1704067200000
                        + (i * 3600000),  # Hourly intervals
                        "updated_time": 1704067200000 + (i * 3600000),
                    }
                )

            # Simulate pagination
            total_count = offset + len(mock_notes)
            has_more = len(mock_notes) == limit  # Assume more if we got full page

            return {
                "notes": mock_notes,
                "total_count": total_count,
                "has_more": has_more,
            }

    return MockJoplinClient()


# Create the MCP tool instance
get_notes_in_notebook_tool = MCPTool(
    name="get_notes_in_notebook",
    description="List all notes within a specific notebook",
    input_schema=GET_NOTES_IN_NOTEBOOK_INPUT_SCHEMA,
    output_schema=GET_NOTES_IN_NOTEBOOK_OUTPUT_SCHEMA,
    handler=get_notes_in_notebook_handler,
)
