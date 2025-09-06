"""Contract tests for get_notes_in_notebook MCP tool.

These tests verify the MCP tool interface compliance for get_notes_in_notebook.
They must fail initially (RED phase) before implementation.
"""

import pytest

from src.tools.get_notes_in_notebook import get_notes_in_notebook_tool


class TestGetNotesInNotebookContract:
    """Test get_notes_in_notebook tool contract compliance."""

    def test_get_notes_in_notebook_tool_exists(self) -> None:
        """Test that get_notes_in_notebook tool is properly defined."""
        # This will fail until the tool is implemented
        assert hasattr(get_notes_in_notebook_tool, "name")
        assert get_notes_in_notebook_tool.name == "get_notes_in_notebook"
        assert hasattr(get_notes_in_notebook_tool, "description")
        assert "notes" in get_notes_in_notebook_tool.description.lower()
        assert "notebook" in get_notes_in_notebook_tool.description.lower()

    def test_get_notes_in_notebook_input_schema(self) -> None:
        """Test that get_notes_in_notebook has correct input schema."""
        # This will fail until the schema is implemented
        schema = get_notes_in_notebook_tool.inputSchema

        # Required properties
        assert "properties" in schema
        assert "notebook_id" in schema["properties"]
        assert schema["properties"]["notebook_id"]["type"] == "string"
        assert "required" in schema
        assert "notebook_id" in schema["required"]

        # Notebook ID pattern validation
        assert "pattern" in schema["properties"]["notebook_id"]
        assert schema["properties"]["notebook_id"]["pattern"] == "^[a-f0-9]{32}$"

        # Optional properties
        if "limit" in schema["properties"]:
            limit_schema = schema["properties"]["limit"]
            assert limit_schema["type"] == "integer"
            assert "minimum" in limit_schema
            assert "maximum" in limit_schema
            assert limit_schema["minimum"] == 1
            assert limit_schema["maximum"] == 100

        if "offset" in schema["properties"]:
            offset_schema = schema["properties"]["offset"]
            assert offset_schema["type"] == "integer"
            assert "minimum" in offset_schema
            assert offset_schema["minimum"] == 0

    def test_get_notes_in_notebook_output_schema(self) -> None:
        """Test that get_notes_in_notebook has correct output schema."""
        # This will fail until the schema is implemented
        schema = get_notes_in_notebook_tool.outputSchema

        assert "properties" in schema
        required_fields = ["notes", "total_count", "has_more"]

        for field in required_fields:
            assert field in schema["properties"]

        # Notes array schema
        notes_schema = schema["properties"]["notes"]
        assert notes_schema["type"] == "array"
        assert "items" in notes_schema

        # Note item schema
        item_schema = notes_schema["items"]
        note_required_fields = ["id", "title", "created_time", "updated_time"]

        for field in note_required_fields:
            assert field in item_schema["properties"]

        # Other fields
        assert schema["properties"]["total_count"]["type"] == "integer"
        assert schema["properties"]["has_more"]["type"] == "boolean"

    @pytest.mark.asyncio
    async def test_get_notes_in_notebook_handler_signature(self) -> None:
        """Test that get_notes_in_notebook handler has correct async signature."""
        # This will fail until handler is implemented
        handler = get_notes_in_notebook_tool.handler

        # Should be async callable
        import inspect
        assert inspect.iscoroutinefunction(handler)

        # Should accept arguments parameter
        sig = inspect.signature(handler)
        assert "arguments" in sig.parameters

    @pytest.mark.asyncio
    async def test_get_notes_in_notebook_valid_input(self) -> None:
        """Test get_notes_in_notebook with valid input arguments."""
        # This will fail until implementation exists
        arguments = {
            "notebook_id": "a1b2c3d4e5f6789012345678901234567890abcd",
            "limit": 20,
            "offset": 0
        }

        result = await get_notes_in_notebook_tool.handler(arguments)

        # Should return properly structured response
        assert isinstance(result, list)
        assert len(result) == 1

        response = result[0]
        assert response.type == "text"

    @pytest.mark.asyncio
    async def test_get_notes_in_notebook_pagination(self) -> None:
        """Test get_notes_in_notebook with pagination parameters."""
        # This will fail until implementation exists
        arguments = {
            "notebook_id": "a1b2c3d4e5f6789012345678901234567890abcd",
            "limit": 10,
            "offset": 50
        }

        result = await get_notes_in_notebook_tool.handler(arguments)

        # Should return properly structured response
        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_notes_in_notebook_missing_notebook_id(self) -> None:
        """Test get_notes_in_notebook rejects missing notebook_id."""
        # This will fail until validation is implemented
        arguments = {"limit": 10}  # Missing required notebook_id

        with pytest.raises(Exception) as exc_info:
            await get_notes_in_notebook_tool.handler(arguments)

        # Should raise validation error for missing notebook_id
        assert "notebook_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_notes_in_notebook_invalid_limit(self) -> None:
        """Test get_notes_in_notebook rejects invalid limit values."""
        # This will fail until validation is implemented
        arguments = {
            "notebook_id": "a1b2c3d4e5f6789012345678901234567890abcd",
            "limit": 0  # Invalid limit (below minimum)
        }

        with pytest.raises(Exception) as exc_info:
            await get_notes_in_notebook_tool.handler(arguments)

        # Should raise validation error for invalid limit
        error_msg = str(exc_info.value).lower()
        assert "limit" in error_msg or "minimum" in error_msg

    @pytest.mark.asyncio
    async def test_get_notes_in_notebook_invalid_notebook_id(self) -> None:
        """Test get_notes_in_notebook rejects invalid notebook_id format."""
        # This will fail until validation is implemented
        arguments = {"notebook_id": "invalid-format"}

        with pytest.raises(Exception) as exc_info:
            await get_notes_in_notebook_tool.handler(arguments)

        # Should raise validation error for invalid format
        error_msg = str(exc_info.value).lower()
        assert "pattern" in error_msg or "format" in error_msg or "invalid" in error_msg
