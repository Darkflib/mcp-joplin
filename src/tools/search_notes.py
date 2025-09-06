"""search_notes MCP tool handler."""

import json
import logging
from typing import Any

from mcp import types

from src.models.mcp_tool import MCPTool
from src.services.search_service import SearchService

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
        search_results = await search_service.search(
            query=query, limit=limit, notebook_id=notebook_id
        )

        # Format results for MCP response
        results_data = []
        for result in search_results:
            results_data.append(
                {
                    "note_id": result.note_id,
                    "title": result.title,
                    "snippet": result.snippet,
                    "score": result.score,
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


def _get_search_service() -> SearchService:
    """Get search service instance (placeholder for dependency injection)."""

    # In real implementation, this would be injected via DI container
    # For now, return a mock that satisfies the interface
    class MockSearchService:
        async def search(self, query: str, limit: int = 10, notebook_id: str = None):
            # This is a placeholder - real implementation would use actual SearchService
            from src.models.search_result import MatchType, SearchResult

            return [
                SearchResult(
                    note_id="a1b2c3d4e5f6789012345678901234567890abcd",
                    title=f"Mock result for: {query}",
                    snippet=f"This is a mock search result for query '{query}'",
                    score=0.8,
                    match_type=MatchType.TITLE,
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
