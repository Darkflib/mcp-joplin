"""Contract tests for list_notebooks MCP tool.

These tests verify the MCP tool interface compliance for list_notebooks.
They must fail initially (RED phase) before implementation.
"""

import pytest

from src.tools.list_notebooks import list_notebooks_tool


class TestListNotebooksContract:
    """Test list_notebooks tool contract compliance."""

    def test_list_notebooks_tool_exists(self) -> None:
        """Test that list_notebooks tool is properly defined."""
        # This will fail until the tool is implemented
        assert hasattr(list_notebooks_tool, "name")
        assert list_notebooks_tool.name == "list_notebooks"
        assert hasattr(list_notebooks_tool, "description")
        assert "notebooks" in list_notebooks_tool.description.lower()

    def test_list_notebooks_input_schema(self) -> None:
        """Test that list_notebooks has correct input schema."""
        # This will fail until the schema is implemented
        schema = list_notebooks_tool.inputSchema

        assert "properties" in schema

        # Optional properties
        if "parent_id" in schema["properties"]:
            assert schema["properties"]["parent_id"]["type"] == "string"
            assert "pattern" in schema["properties"]["parent_id"]
            assert schema["properties"]["parent_id"]["pattern"] == "^[a-f0-9]{32}$"

        if "recursive" in schema["properties"]:
            assert schema["properties"]["recursive"]["type"] == "boolean"

        # No required fields for this tool
        if "required" in schema:
            assert len(schema["required"]) == 0

    def test_list_notebooks_output_schema(self) -> None:
        """Test that list_notebooks has correct output schema."""
        # This will fail until the schema is implemented
        schema = list_notebooks_tool.outputSchema

        assert "properties" in schema
        assert "notebooks" in schema["properties"]
        assert "required" in schema
        assert "notebooks" in schema["required"]

        # Notebooks array schema
        notebooks_schema = schema["properties"]["notebooks"]
        assert notebooks_schema["type"] == "array"
        assert "items" in notebooks_schema

        # Notebook item schema
        item_schema = notebooks_schema["items"]
        required_fields = ["id", "title", "created_time", "updated_time"]

        for field in required_fields:
            assert field in item_schema["properties"]

        # Optional fields
        optional_fields = ["parent_id", "children"]
        for field in optional_fields:
            if field in item_schema["properties"]:
                if field == "children":
                    assert item_schema["properties"][field]["type"] == "array"

    @pytest.mark.asyncio
    async def test_list_notebooks_handler_signature(self) -> None:
        """Test that list_notebooks handler has correct async signature."""
        # This will fail until handler is implemented
        handler = list_notebooks_tool.handler

        # Should be async callable
        import inspect
        assert inspect.iscoroutinefunction(handler)

        # Should accept arguments parameter
        sig = inspect.signature(handler)
        assert "arguments" in sig.parameters

    @pytest.mark.asyncio
    async def test_list_notebooks_no_arguments(self) -> None:
        """Test list_notebooks with no arguments (list all)."""
        # This will fail until implementation exists
        arguments = {}

        result = await list_notebooks_tool.handler(arguments)

        # Should return properly structured response
        assert isinstance(result, list)
        assert len(result) == 1

        response = result[0]
        assert response.type == "text"

    @pytest.mark.asyncio
    async def test_list_notebooks_with_parent_id(self) -> None:
        """Test list_notebooks with parent_id filter."""
        # This will fail until implementation exists
        arguments = {
            "parent_id": "a1b2c3d4e5f6789012345678901234567890abcd",
            "recursive": False
        }

        result = await list_notebooks_tool.handler(arguments)

        # Should return properly structured response
        assert isinstance(result, list)
        assert len(result) == 1

        response = result[0]
        assert response.type == "text"

    @pytest.mark.asyncio
    async def test_list_notebooks_recursive(self) -> None:
        """Test list_notebooks with recursive option."""
        # This will fail until implementation exists
        arguments = {"recursive": True}

        result = await list_notebooks_tool.handler(arguments)

        # Should return properly structured response
        assert isinstance(result, list)
        assert len(result) == 1

        response = result[0]
        assert response.type == "text"

    @pytest.mark.asyncio
    async def test_list_notebooks_invalid_parent_id(self) -> None:
        """Test list_notebooks rejects invalid parent_id format."""
        # This will fail until validation is implemented
        arguments = {"parent_id": "invalid-format"}

        with pytest.raises(Exception) as exc_info:
            await list_notebooks_tool.handler(arguments)

        # Should raise validation error for invalid format
        error_msg = str(exc_info.value).lower()
        assert "pattern" in error_msg or "format" in error_msg or "invalid" in error_msg
