"""Tests for create_note tool."""

import os
import pytest
from unittest.mock import patch, AsyncMock

from src.tools.create_note import create_note_handler, _write_operations_enabled


class TestCreateNoteTool:
    """Test create_note MCP tool functionality."""

    @pytest.fixture
    def mock_joplin_client(self):
        """Create a mock Joplin client."""
        client = AsyncMock()
        client.create_note.return_value = {
            "id": "b2c3d4e5f6789012345678901234abcd",
            "title": "New Note",
            "body": "Note content",
            "parent_id": "notebook123456789012345678901234",
            "created_time": "2024-01-01T12:00:00.000Z",
            "updated_time": "2024-01-01T12:00:00.000Z",
        }
        return client

    def test_write_operations_enabled(self):
        """Test write operations check with different environment values."""
        # Test disabled (default)
        with patch.dict(os.environ, {}, clear=True):
            assert not _write_operations_enabled()

        # Test explicitly disabled
        with patch.dict(os.environ, {"JOPLIN_ALLOW_WRITE_OPERATIONS": "false"}):
            assert not _write_operations_enabled()

        # Test enabled variations
        for enabled_value in ["true", "1", "yes", "on", "TRUE", "On"]:
            with patch.dict(os.environ, {"JOPLIN_ALLOW_WRITE_OPERATIONS": enabled_value}):
                assert _write_operations_enabled()

    @pytest.mark.asyncio
    async def test_create_note_disabled_by_default(self):
        """Test that create_note fails when write operations are disabled."""
        arguments = {"title": "New Note"}

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception) as exc_info:
                await create_note_handler(arguments)
            
            assert "Write operations are disabled" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_note_validation_errors(self, mock_joplin_client):
        """Test validation errors for create_note."""
        with patch.dict(os.environ, {"JOPLIN_ALLOW_WRITE_OPERATIONS": "true"}):
            # Missing title
            with pytest.raises(ValueError, match="Missing required field: title"):
                await create_note_handler({})

            # Empty title
            with pytest.raises(ValueError, match="Field 'title' cannot be empty or whitespace only"):
                await create_note_handler({"title": ""})

            # Whitespace-only title
            with pytest.raises(ValueError, match="Field 'title' cannot be empty or whitespace only"):
                await create_note_handler({"title": "   "})

            # Invalid title type
            with pytest.raises(ValueError, match="Field 'title' has invalid type"):
                await create_note_handler({"title": 123})

            # Invalid body type
            with pytest.raises(ValueError, match="Field 'body' has invalid type"):
                await create_note_handler({"title": "Valid Title", "body": 123})

            # Invalid parent_id type
            with pytest.raises(ValueError, match="Field 'parent_id' has invalid type"):
                await create_note_handler({"title": "Valid Title", "parent_id": 123})

            # Invalid parent_id length
            with pytest.raises(ValueError, match="Field 'parent_id' must be 32-character hex string"):
                await create_note_handler({"title": "Valid Title", "parent_id": "short"})

    @pytest.mark.asyncio
    async def test_create_note_success_minimal(self, mock_joplin_client):
        """Test successful note creation with minimal arguments (title only)."""
        arguments = {"title": "New Note"}

        with patch.dict(os.environ, {"JOPLIN_ALLOW_WRITE_OPERATIONS": "true"}):
            with patch('src.tools.create_note._get_joplin_client', return_value=mock_joplin_client):
                result = await create_note_handler(arguments)

                # Check that client was called correctly
                mock_joplin_client.create_note.assert_called_once_with(
                    title="New Note",
                    body="",
                    parent_id=None
                )

                # Check response format
                assert len(result) == 1
                assert result[0].type == "text"
                
                import json
                response_data = json.loads(result[0].text)
                assert response_data["note_id"] == "b2c3d4e5f6789012345678901234abcd"
                assert response_data["title"] == "New Note"
                assert response_data["success"] is True

    @pytest.mark.asyncio
    async def test_create_note_success_with_body(self, mock_joplin_client):
        """Test successful note creation with title and body."""
        arguments = {
            "title": "New Note",
            "body": "This is the **content** of the note with markdown.",
        }

        with patch.dict(os.environ, {"JOPLIN_ALLOW_WRITE_OPERATIONS": "true"}):
            with patch('src.tools.create_note._get_joplin_client', return_value=mock_joplin_client):
                result = await create_note_handler(arguments)

                # Check that client was called correctly
                mock_joplin_client.create_note.assert_called_once_with(
                    title="New Note",
                    body="This is the **content** of the note with markdown.",
                    parent_id=None
                )

                # Check response format
                assert len(result) == 1
                assert result[0].type == "text"
                
                import json
                response_data = json.loads(result[0].text)
                assert response_data["note_id"] == "b2c3d4e5f6789012345678901234abcd"
                assert response_data["title"] == "New Note"
                assert response_data["body"] == "Note content"  # From mock response
                assert response_data["success"] is True

    @pytest.mark.asyncio
    async def test_create_note_success_all_fields(self, mock_joplin_client):
        """Test successful note creation with all fields."""
        arguments = {
            "title": "New Note in Specific Notebook",
            "body": "This note is created in a specific notebook.",
            "parent_id": "notebook123456789012345678901234",
        }

        with patch.dict(os.environ, {"JOPLIN_ALLOW_WRITE_OPERATIONS": "true"}):
            with patch('src.tools.create_note._get_joplin_client', return_value=mock_joplin_client):
                result = await create_note_handler(arguments)

                # Check that client was called correctly
                mock_joplin_client.create_note.assert_called_once_with(
                    title="New Note in Specific Notebook",
                    body="This note is created in a specific notebook.",
                    parent_id="notebook123456789012345678901234"
                )

                # Check response format
                assert len(result) == 1
                assert result[0].type == "text"
                
                import json
                response_data = json.loads(result[0].text)
                assert response_data["note_id"] == "b2c3d4e5f6789012345678901234abcd"
                assert response_data["parent_id"] == "notebook123456789012345678901234"
                assert response_data["success"] is True

    @pytest.mark.asyncio
    async def test_create_note_title_whitespace_trimming(self, mock_joplin_client):
        """Test that title whitespace is properly trimmed."""
        arguments = {"title": "   Trimmed Title   "}

        with patch.dict(os.environ, {"JOPLIN_ALLOW_WRITE_OPERATIONS": "true"}):
            with patch('src.tools.create_note._get_joplin_client', return_value=mock_joplin_client):
                result = await create_note_handler(arguments)

                # Check that client was called with trimmed title
                mock_joplin_client.create_note.assert_called_once_with(
                    title="Trimmed Title",  # Should be trimmed
                    body="",
                    parent_id=None
                )

    @pytest.mark.asyncio
    async def test_create_note_client_error(self, mock_joplin_client):
        """Test handling of client errors during note creation."""
        arguments = {"title": "New Note"}

        # Mock client to raise an exception
        mock_joplin_client.create_note.side_effect = Exception("Connection failed")

        with patch.dict(os.environ, {"JOPLIN_ALLOW_WRITE_OPERATIONS": "true"}):
            with patch('src.tools.create_note._get_joplin_client', return_value=mock_joplin_client):
                with pytest.raises(Exception, match="Note creation failed: Connection failed"):
                    await create_note_handler(arguments)