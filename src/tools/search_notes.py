"""search_notes MCP tool handler."""

import json
import logging
from typing import Any

from mcp import types

from src.models.mcp_tool import MCPTool

logger = logging.getLogger(__name__)


# MCP tool definition schema
SEARCH_NOTES_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search query to match against note titles and content",
            "minLength": 1,
            "maxLength": 200,
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of results to return",
            "minimum": 1,
            "maximum": 50,
            "default": 10,
        },
        "notebook_id": {
            "type": "string",
            "description": "Optional: limit search to specific notebook",
            "pattern": "^[a-f0-9]{32}$",
        },
    },
    "required": ["query"],
}

SEARCH_NOTES_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string"},
                    "title": {"type": "string"},
                    "snippet": {"type": "string"},
                    "score": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["note_id", "title", "snippet", "score"],
            },
        },
        "total_count": {"type": "integer", "minimum": 0},
    },
    "required": ["results", "total_count"],
}


async def search_notes_handler(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handle search_notes MCP tool calls."""
    try:
        logger.info("Processing search_notes request", extra={"arguments": arguments})

        # Validate required arguments
        query = arguments.get("query")
        if not query:
            raise ValueError("Missing required field: query")

        limit = arguments.get("limit", 10)
        notebook_id = arguments.get("notebook_id")

        # Validate argument types
        if not isinstance(query, str):
            raise ValueError("Field 'query' has invalid type, expected string")
        if not isinstance(limit, int):
            raise ValueError("Field 'limit' has invalid type, expected integer")
        if notebook_id is not None and not isinstance(notebook_id, str):
            raise ValueError("Field 'notebook_id' has invalid type, expected string")

        # Validate patterns
        if notebook_id and len(notebook_id) != 32:
            raise ValueError("Field 'notebook_id' must be 32-character hex string")

        # Get search service (this would be injected in real implementation)
        search_service = _get_search_service()

        # Perform search
        search_results = await search_service.search_notes(
            query=query, limit=limit, notebook_id=notebook_id
        )

        # Handle both real SearchService (returns SearchResult object) and mock (returns list)
        if hasattr(search_results, "items"):
            # Real SearchService returns SearchResult object
            result_items = search_results.items
        else:
            # Mock returns list directly
            result_items = search_results

        # Format results for MCP response
        results_data = []
        for result in result_items:
            results_data.append(
                {
                    "note_id": result.note_id,
                    "title": result.title,
                    "snippet": result.snippet,
                    "score": result.relevance_score,
                }
            )

        response_data = {"results": results_data, "total_count": len(results_data)}

        logger.info(
            "Search completed successfully",
            extra={"query": query, "results_count": len(results_data)},
        )

        # Return as MCP TextContent
        return [
            types.TextContent(type="text", text=json.dumps(response_data, indent=2))
        ]

    except ValueError as e:
        logger.error("Validation error in search_notes", extra={"error": str(e)})
        raise
    except Exception as e:
        logger.error("Unexpected error in search_notes", extra={"error": str(e)})
        raise Exception(f"Search failed: {str(e)}") from e


def _get_search_service() -> Any:
    """Get search service instance (placeholder for dependency injection)."""
    # Try to get real search service from server globals first
    try:
        from src.server import _global_search_service

        if _global_search_service is not None:
            return _global_search_service
    except (ImportError, AttributeError):
        pass

    # Fall back to mock if real service not available
    class MockSearchService:
        async def search_notes(
            self, query: str, limit: int = 10, notebook_id: str | None = None
        ) -> Any:
            # This is a placeholder - real implementation would use actual SearchService
            from src.models.search_result import SearchResultItem

            # Return a simple list of search result items for now
            return [
                SearchResultItem(
                    note_id="a1b2c3d4e5f6789012345678901234ab",  # Fixed to be exactly 32 chars
                    title=f"Mock result for: {query}",
                    snippet=f"This is a mock search result for query '{query}'",
                    relevance_score=0.8,
                )
            ]

    return MockSearchService()


# Create the MCP tool instance
search_notes_tool = MCPTool(
    name="search_notes",
    description="Search for notes in Joplin by title, content, or tags",
    input_schema=SEARCH_NOTES_INPUT_SCHEMA,
    output_schema=SEARCH_NOTES_OUTPUT_SCHEMA,
    handler=search_notes_handler,
)
