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
        async def list_notebooks(
            self, parent_id: str | None = None, recursive: bool = True
        ) -> dict[str, Any]:
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
                filtered_notebooks = []
                for nb in mock_notebooks:
                    if isinstance(nb, dict) and nb.get("parent_id") == parent_id:
                        filtered_notebooks.append(nb)
                mock_notebooks = filtered_notebooks

            return {"items": mock_notebooks}

    return MockJoplinClient()


async def list_notebooks_handler(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handle list_notebooks MCP tool calls."""
    try:
        logger.info("Processing list_notebooks request", extra={"arguments": arguments})

        # Extract arguments with defaults
        parent_id = arguments.get("parent_id")
        recursive = arguments.get("recursive", True)

        # Get Joplin client (in real implementation, this would be injected)
        joplin_client = _get_joplin_client()

        # Call Joplin API to get notebooks
        api_response = await joplin_client.list_notebooks(parent_id, recursive)

        # Transform to internal format
        notebooks = []
        if "items" in api_response:
            for item in api_response["items"]:
                notebook = {
                    "id": item.get("id", ""),
                    "title": item.get("title", "Untitled"),
                    "parent_id": item.get("parent_id"),
                    "created_time": item.get("created_time", 0),
                    "updated_time": item.get("updated_time", 0),
                }
                notebooks.append(notebook)

        # Build hierarchical structure if recursive
        if recursive:
            notebooks = _build_hierarchy(notebooks)

        response_data = {"notebooks": notebooks}

        logger.info(
            "Notebooks listed successfully",
            extra={
                "parent_id": parent_id,
                "recursive": recursive,
                "count": len(notebooks),
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


# Create the MCP tool instance
list_notebooks_tool = MCPTool(
    name="list_notebooks",
    description="Get all notebooks with their hierarchical structure",
    input_schema=LIST_NOTEBOOKS_INPUT_SCHEMA,
    output_schema=LIST_NOTEBOOKS_OUTPUT_SCHEMA,
    handler=list_notebooks_handler,
)
