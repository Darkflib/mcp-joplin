"""list_notebooks MCP tool handler."""

import json
import logging
from typing import Any

from mcp import types

from src.models.mcp_tool import MCPTool

logger = logging.getLogger(__name__)


# MCP tool definition schema
LIST_NOTEBOOKS_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "parent_id": {
            "type": "string",
            "description": "Optional: list notebooks under specific parent",
            "pattern": "^[a-f0-9]{32}$",
        },
        "recursive": {
            "type": "boolean",
            "description": "Include nested notebooks recursively",
            "default": True,
        },
    },
}

LIST_NOTEBOOKS_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "notebooks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "parent_id": {"type": "string"},
                    "created_time": {"type": "integer"},
                    "updated_time": {"type": "integer"},
                    "children": {
                        "type": "array",
                        "description": "Nested notebooks if recursive=true",
                    },
                },
                "required": ["id", "title", "created_time", "updated_time"],
            },
        }
    },
    "required": ["notebooks"],
}


async def list_notebooks_handler(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handle list_notebooks MCP tool calls."""
    try:
        logger.info("Processing list_notebooks request", extra={"arguments": arguments})

        parent_id = arguments.get("parent_id")
        recursive = arguments.get("recursive", True)

        # Validate argument types
        if parent_id is not None and not isinstance(parent_id, str):
            raise ValueError("Field 'parent_id' has invalid type, expected string")
        if not isinstance(recursive, bool):
            raise ValueError("Field 'recursive' has invalid type, expected boolean")

        # Validate parent_id pattern if provided
        if parent_id and (
            len(parent_id) != 32 or not all(c in "0123456789abcdef" for c in parent_id)
        ):
            raise ValueError("Field 'parent_id' must match pattern ^[a-f0-9]{32}$")

        # Get Joplin client (this would be injected in real implementation)
        joplin_client = _get_joplin_client()

        # List notebooks
        notebooks_data = await joplin_client.list_notebooks(
            parent_id=parent_id, recursive=recursive
        )

        notebooks_list = notebooks_data.get("items", [])

        # Build hierarchical structure if recursive
        if recursive:
            notebooks_list = _build_hierarchy(notebooks_list)

        # Format response
        response_data = {"notebooks": notebooks_list}

        logger.info(
            "Notebooks listed successfully",
            extra={
                "parent_id": parent_id,
                "recursive": recursive,
                "count": len(notebooks_list),
            },
        )

        # Return as MCP TextContent
        return [
            types.TextContent(type="text", text=json.dumps(response_data, indent=2))
        ]

    except ValueError as e:
        logger.error("Validation error in list_notebooks", extra={"error": str(e)})
        raise
    except Exception as e:
        logger.error("Unexpected error in list_notebooks", extra={"error": str(e)})
        raise Exception(f"Failed to list notebooks: {str(e)}") from e


def _build_hierarchy(notebooks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build hierarchical notebook structure."""
    # Create lookup by ID
    notebooks_by_id = {nb["id"]: nb.copy() for nb in notebooks}

    # Initialize children arrays
    for notebook in notebooks_by_id.values():
        notebook["children"] = []

    # Build parent-child relationships
    root_notebooks = []

    for notebook in notebooks_by_id.values():
        parent_id = notebook.get("parent_id")

        if parent_id and parent_id in notebooks_by_id:
            # Add to parent's children
            notebooks_by_id[parent_id]["children"].append(notebook)
        else:
            # Root notebook (no parent or parent not in list)
            root_notebooks.append(notebook)

    return root_notebooks


def _get_joplin_client():
    """Get Joplin client instance (placeholder for dependency injection)."""

    # In real implementation, this would be injected via DI container
    class MockJoplinClient:
        async def list_notebooks(self, parent_id: str = None, recursive: bool = True):
            # Mock implementation - real would use actual JoplinClient
            mock_notebooks = [
                {
                    "id": "root1234567890abcdef1234567890abcdef",
                    "title": "Personal",
                    "parent_id": None,
                    "created_time": 1704067200000,
                    "updated_time": 1704067200000,
                },
                {
                    "id": "root5678901234abcdef5678901234abcdef",
                    "title": "Work",
                    "parent_id": None,
                    "created_time": 1704067200000,
                    "updated_time": 1704067200000,
                },
                {
                    "id": "child123456789abcdef123456789abcdef",
                    "title": "Projects",
                    "parent_id": "root5678901234abcdef5678901234abcdef",
                    "created_time": 1704070800000,
                    "updated_time": 1704070800000,
                },
            ]

            # Filter by parent_id if specified
            if parent_id is not None:
                mock_notebooks = [
                    nb for nb in mock_notebooks if nb.get("parent_id") == parent_id
                ]

            return {"items": mock_notebooks}

    return MockJoplinClient()


# Create the MCP tool instance
list_notebooks_tool = MCPTool(
    name="list_notebooks",
    description="Get all notebooks with their hierarchical structure",
    input_schema=LIST_NOTEBOOKS_INPUT_SCHEMA,
    output_schema=LIST_NOTEBOOKS_OUTPUT_SCHEMA,
    handler=list_notebooks_handler,
)
