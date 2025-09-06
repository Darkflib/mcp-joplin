"""Contract tests for get_note MCP tool.

These tests verify the MCP tool interface compliance for get_note.
They must fail initially (RED phase) before implementation.
"""

import pytest

from src.tools.get_note import get_note_tool


class TestGetNoteContract:
    """Test get_note tool contract compliance."""

    def test_get_note_tool_exists(self) -> None:
        """Test that get_note tool is properly defined."""
        # This will fail until the tool is implemented
        assert hasattr(get_note_tool, "name")
        assert get_note_tool.name == "get_note"
        assert hasattr(get_note_tool, "description")
        assert "retrieve" in get_note_tool.description.lower()

    def test_get_note_input_schema(self) -> None:
        """Test that get_note has correct input schema."""
        # This will fail until the schema is implemented
        schema = get_note_tool.inputSchema

        # Required properties
        assert "properties" in schema
        assert "note_id" in schema["properties"]
        assert schema["properties"]["note_id"]["type"] == "string"
        assert "required" in schema
        assert "note_id" in schema["required"]

        # Note ID pattern validation
        assert "pattern" in schema["properties"]["note_id"]
        assert schema["properties"]["note_id"]["pattern"] == "^[a-f0-9]{32}$"

        # Optional properties
        assert "include_body" in schema["properties"]
        assert schema["properties"]["include_body"]["type"] == "boolean"

    def test_get_note_output_schema(self) -> None:
        """Test that get_note has correct output schema."""
        # This will fail until the schema is implemented
        schema = get_note_tool.outputSchema

        assert "properties" in schema
        required_fields = ["id", "title", "parent_id", "created_time", "updated_time"]

        for field in required_fields:
            assert field in schema["properties"]

        # Optional fields
        assert "body" in schema["properties"]
        assert "tags" in schema["properties"]

        # Tags should be array of strings
        tags_schema = schema["properties"]["tags"]
        assert tags_schema["type"] == "array"
        assert tags_schema["items"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_get_note_handler_signature(self) -> None:
        """Test that get_note handler has correct async signature."""
        # This will fail until handler is implemented
        handler = get_note_tool.handler

        # Should be async callable
        import inspect
        assert inspect.iscoroutinefunction(handler)

        # Should accept arguments parameter
        sig = inspect.signature(handler)
        assert "arguments" in sig.parameters

    @pytest.mark.asyncio
    async def test_get_note_valid_input(self) -> None:
        """Test get_note with valid input arguments."""
        # This will fail until implementation exists
        arguments = {
            "note_id": "a1b2c3d4e5f6789012345678901234567890abcd",
            "include_body": True
        }

        result = await get_note_tool.handler(arguments)

        # Should return properly structured response
        assert isinstance(result, list)
        assert len(result) == 1

        response = result[0]
        assert response.type == "text"

    @pytest.mark.asyncio
    async def test_get_note_missing_note_id(self) -> None:
        """Test get_note rejects missing note_id."""
        # This will fail until validation is implemented
        arguments = {"include_body": True}  # Missing required note_id

        with pytest.raises(Exception) as exc_info:
            await get_note_tool.handler(arguments)

        # Should raise validation error for missing note_id
        assert "note_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_note_invalid_note_id_format(self) -> None:
        """Test get_note rejects invalid note_id format."""
        # This will fail until validation is implemented
        arguments = {"note_id": "invalid-id-format"}

        with pytest.raises(Exception) as exc_info:
            await get_note_tool.handler(arguments)

        # Should raise validation error for invalid format
        error_msg = str(exc_info.value).lower()
        assert "pattern" in error_msg or "format" in error_msg or "invalid" in error_msg
