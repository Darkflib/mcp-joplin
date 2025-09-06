"""Contract tests for search_notes MCP tool.

These tests verify the MCP tool interface compliance for search_notes.
They must fail initially (RED phase) before implementation.
"""

import pytest

from src.tools.search_notes import search_notes_tool


class TestSearchNotesContract:
    """Test search_notes tool contract compliance."""

    def test_search_notes_tool_exists(self) -> None:
        """Test that search_notes tool is properly defined."""
        # This will fail until the tool is implemented
        assert hasattr(search_notes_tool, "name")
        assert search_notes_tool.name == "search_notes"
        assert hasattr(search_notes_tool, "description")
        assert "search" in search_notes_tool.description.lower()

    def test_search_notes_input_schema(self) -> None:
        """Test that search_notes has correct input schema."""
        # This will fail until the schema is implemented
        schema = search_notes_tool.inputSchema

        # Required properties
        assert "properties" in schema
        assert "query" in schema["properties"]
        assert schema["properties"]["query"]["type"] == "string"
        assert "required" in schema
        assert "query" in schema["required"]

        # Optional properties
        assert "limit" in schema["properties"]
        assert schema["properties"]["limit"]["type"] == "integer"
        assert "notebook_id" in schema["properties"]

    def test_search_notes_output_schema(self) -> None:
        """Test that search_notes has correct output schema."""
        # This will fail until the schema is implemented
        schema = search_notes_tool.outputSchema

        assert "properties" in schema
        assert "results" in schema["properties"]
        assert "total_count" in schema["properties"]

        # Results array schema
        results_schema = schema["properties"]["results"]
        assert results_schema["type"] == "array"
        assert "items" in results_schema

        # Result item schema
        item_schema = results_schema["items"]
        required_fields = ["note_id", "title", "snippet", "score"]
        for field in required_fields:
            assert field in item_schema["properties"]

    @pytest.mark.asyncio
    async def test_search_notes_handler_signature(self) -> None:
        """Test that search_notes handler has correct async signature."""
        # This will fail until handler is implemented
        handler = search_notes_tool.handler

        # Should be async callable
        import inspect
        assert inspect.iscoroutinefunction(handler)

        # Should accept arguments parameter
        sig = inspect.signature(handler)
        assert "arguments" in sig.parameters

    @pytest.mark.asyncio
    async def test_search_notes_valid_input(self) -> None:
        """Test search_notes with valid input arguments."""
        # This will fail until implementation exists
        arguments = {"query": "test search", "limit": 5}

        result = await search_notes_tool.handler(arguments)

        # Should return properly structured response
        assert isinstance(result, list)
        assert len(result) == 1  # MCP tools return list of results

        response = result[0]
        assert response.type == "text"
        assert "results" in response.text or hasattr(response, "content")

    @pytest.mark.asyncio
    async def test_search_notes_missing_required_field(self) -> None:
        """Test search_notes rejects missing required fields."""
        # This will fail until validation is implemented
        arguments = {"limit": 10}  # Missing required 'query'

        with pytest.raises(Exception) as exc_info:
            await search_notes_tool.handler(arguments)

        # Should raise validation error for missing query
        assert "query" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_notes_invalid_types(self) -> None:
        """Test search_notes rejects invalid argument types."""
        # This will fail until validation is implemented
        arguments = {"query": 123, "limit": "invalid"}  # Wrong types

        with pytest.raises(Exception) as exc_info:
            await search_notes_tool.handler(arguments)

        # Should raise type validation error
        error_msg = str(exc_info.value).lower()
        assert "type" in error_msg or "invalid" in error_msg
