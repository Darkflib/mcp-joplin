"""Tests for update_note tool."""

import os
import pytest
from unittest.mock import patch, AsyncMock

from src.tools.update_note import update_note_handler, _write_operations_enabled


class TestUpdateNoteTool:
    """Test update_note MCP tool functionality."""

    @pytest.fixture
    def mock_joplin_client(self):
        """Create a mock Joplin client."""
        client = AsyncMock()
        client.update_note.return_value = {
            "id": "a1b2c3d4e5f6789012345678901234ab",
            "title": "Updated Title",
            "body": "Updated content",
            "parent_id": "notebook123456789012345678901234",
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
    async def test_update_note_disabled_by_default(self):
        """Test that update_note fails when write operations are disabled."""
        arguments = {
            "note_id": "a1b2c3d4e5f6789012345678901234ab",
            "title": "New Title",
        }

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception) as exc_info:
                await update_note_handler(arguments)
            
            assert "Write operations are disabled" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_note_validation_errors(self, mock_joplin_client):
        """Test validation errors for update_note."""
        with patch.dict(os.environ, {"JOPLIN_ALLOW_WRITE_OPERATIONS": "true"}):
            # Missing note_id
            with pytest.raises(ValueError, match="Missing required field: note_id"):
                await update_note_handler({})

            # No update fields provided
            with pytest.raises(ValueError, match="At least one of title, body, or parent_id must be provided"):
                await update_note_handler({"note_id": "a1b2c3d4e5f6789012345678901234ab"})

            # Invalid note_id type
            with pytest.raises(ValueError, match="Field 'note_id' has invalid type"):
                await update_note_handler({"note_id": 123, "title": "New Title"})

            # Invalid note_id length
            with pytest.raises(ValueError, match="Field 'note_id' must be 32-character hex string"):
                await update_note_handler({"note_id": "short", "title": "New Title"})

            # Invalid parent_id length
            with pytest.raises(ValueError, match="Field 'parent_id' must be 32-character hex string"):
                await update_note_handler({
                    "note_id": "a1b2c3d4e5f6789012345678901234ab",
                    "parent_id": "short",
                })

    @pytest.mark.asyncio
    async def test_update_note_success_title_only(self, mock_joplin_client):
        """Test successful note title update."""
        arguments = {
            "note_id": "a1b2c3d4e5f6789012345678901234ab",
            "title": "Updated Title",
        }

        with patch.dict(os.environ, {"JOPLIN_ALLOW_WRITE_OPERATIONS": "true"}):
            with patch('src.tools.update_note._get_joplin_client', return_value=mock_joplin_client):
                result = await update_note_handler(arguments)

                # Check that client was called correctly
                mock_joplin_client.update_note.assert_called_once_with(
                    note_id="a1b2c3d4e5f6789012345678901234ab",
                    title="Updated Title",
                    body=None,
                    parent_id=None
                )

                # Check response format
                assert len(result) == 1
                assert result[0].type == "text"
                
                import json
                response_data = json.loads(result[0].text)
                assert response_data["note_id"] == "a1b2c3d4e5f6789012345678901234ab"
                assert response_data["title"] == "Updated Title"
                assert response_data["success"] is True

    @pytest.mark.asyncio
    async def test_update_note_success_all_fields(self, mock_joplin_client):
        """Test successful note update with all fields."""
        arguments = {
            "note_id": "a1b2c3d4e5f6789012345678901234ab",
            "title": "Updated Title",
            "body": "Updated content with markdown **bold** text",
            "parent_id": "notebook123456789012345678901234",
        }

        with patch.dict(os.environ, {"JOPLIN_ALLOW_WRITE_OPERATIONS": "true"}):
            with patch('src.tools.update_note._get_joplin_client', return_value=mock_joplin_client):
                result = await update_note_handler(arguments)

                # Check that client was called correctly
                mock_joplin_client.update_note.assert_called_once_with(
                    note_id="a1b2c3d4e5f6789012345678901234ab",
                    title="Updated Title",
                    body="Updated content with markdown **bold** text",
                    parent_id="notebook123456789012345678901234"
                )

                # Check response format
                assert len(result) == 1
                assert result[0].type == "text"
                
                import json
                response_data = json.loads(result[0].text)
                assert response_data["note_id"] == "a1b2c3d4e5f6789012345678901234ab"
                assert response_data["success"] is True

    @pytest.mark.asyncio
    async def test_update_note_client_error(self, mock_joplin_client):
        """Test handling of client errors during note update."""
        arguments = {
            "note_id": "a1b2c3d4e5f6789012345678901234ab",
            "title": "Updated Title",
        }

        # Mock client to raise an exception
        mock_joplin_client.update_note.side_effect = Exception("Connection failed")

        with patch.dict(os.environ, {"JOPLIN_ALLOW_WRITE_OPERATIONS": "true"}):
            with patch('src.tools.update_note._get_joplin_client', return_value=mock_joplin_client):
                with pytest.raises(Exception, match="Note update failed: Connection failed"):
                    await update_note_handler(arguments)