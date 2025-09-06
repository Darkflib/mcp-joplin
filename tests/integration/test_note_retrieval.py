"""Integration tests for note retrieval functionality.

These tests verify full note retrieval works end-to-end.
They must fail initially (RED phase) before implementation.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.joplin_client import JoplinClient


class TestNoteRetrievalIntegration:
    """Test note retrieval functionality integration scenarios."""

    @pytest.fixture
    def mock_joplin_note(self):
        """Sample Joplin note for testing."""
        return {
            "id": "a1b2c3d4e5f6789012345678901234567890abcd",
            "title": "Project Planning Document",
            "body": "# Project Overview\n\nThis document outlines the project timeline and key deliverables...",
            "parent_id": "notebook123",
            "created_time": 1704067200000,
            "updated_time": 1704070800000,
            "is_conflict": 0,
            "markup_language": 1,
            "tags": "project,planning,important"
        }

    @pytest.mark.asyncio
    async def test_get_note_full_content(self, mock_joplin_note) -> None:
        """Test retrieving full note content and metadata."""
        # This will fail until JoplinClient.get_note is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        note_id = "a1b2c3d4e5f6789012345678901234567890abcd"

        with patch.object(client, 'get_note') as mock_get:
            mock_get.return_value = mock_joplin_note

            note = await client.get_note(note_id, include_body=True)

            # Should return complete note data
            assert note.id == note_id
            assert note.title == "Project Planning Document"
            assert "Project Overview" in note.body
            assert note.parent_id == "notebook123"
            assert note.created_time == 1704067200000
            assert note.updated_time == 1704070800000

    @pytest.mark.asyncio
    async def test_get_note_without_body(self, mock_joplin_note) -> None:
        """Test retrieving note metadata without full body content."""
        # This will fail until selective field retrieval is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        note_id = "a1b2c3d4e5f6789012345678901234567890abcd"

        # Mock response without body field
        metadata_only = {k: v for k, v in mock_joplin_note.items() if k != "body"}

        with patch.object(client, 'get_note') as mock_get:
            mock_get.return_value = metadata_only

            note = await client.get_note(note_id, include_body=False)

            # Should have metadata but no body
            assert note.id == note_id
            assert note.title == "Project Planning Document"
            assert not hasattr(note, 'body') or note.body is None

    @pytest.mark.asyncio
    async def test_get_note_with_tags_parsing(self, mock_joplin_note) -> None:
        """Test note retrieval properly parses tags."""
        # This will fail until tag parsing is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        note_id = "a1b2c3d4e5f6789012345678901234567890abcd"

        with patch.object(client, 'get_note') as mock_get:
            mock_get.return_value = mock_joplin_note

            note = await client.get_note(note_id)

            # Tags should be parsed from comma-separated string to list
            assert hasattr(note, 'tags')
            assert isinstance(note.tags, list)
            assert "project" in note.tags
            assert "planning" in note.tags
            assert "important" in note.tags

    @pytest.mark.asyncio
    async def test_get_note_not_found(self) -> None:
        """Test handling when requested note doesn't exist."""
        # This will fail until 404 error handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        note_id = "nonexistent123456789012345678901234"

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 404
            mock_response.text = "Not Found"
            mock_get.return_value = mock_response

            with pytest.raises(Exception) as exc_info:
                await client.get_note(note_id)

            # Should raise appropriate not found error
            error_msg = str(exc_info.value).lower()
            assert "not found" in error_msg or "404" in error_msg

    @pytest.mark.asyncio
    async def test_get_note_large_content_handling(self) -> None:
        """Test retrieval of very large notes."""
        # This will fail until large content handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        note_id = "a1b2c3d4e5f6789012345678901234567890abcd"

        # Create mock note with large body (>1MB)
        large_body = "# Large Document\n" + "Content line\n" * 50000
        large_note = {
            "id": note_id,
            "title": "Large Document",
            "body": large_body,
            "parent_id": "notebook123",
            "created_time": 1704067200000,
            "updated_time": 1704070800000
        }

        with patch.object(client, 'get_note') as mock_get:
            mock_get.return_value = large_note

            note = await client.get_note(note_id)

            # Should handle large content without timeout/memory issues
            assert len(note.body) > 1000000
            assert note.title == "Large Document"

    @pytest.mark.asyncio
    async def test_get_note_malformed_response_handling(self) -> None:
        """Test handling of malformed API responses."""
        # This will fail until response validation is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        note_id = "a1b2c3d4e5f6789012345678901234567890abcd"

        malformed_responses = [
            None,  # Null response
            {},    # Empty response
            {"id": "different-id"},  # Missing required fields
            {"invalid": "response"}   # Completely wrong format
        ]

        for malformed_data in malformed_responses:
            with patch.object(client, 'get_note') as mock_get:
                mock_get.return_value = malformed_data

                with pytest.raises(Exception) as exc_info:
                    await client.get_note(note_id)

                # Should raise validation error
                error_msg = str(exc_info.value).lower()
                assert any(word in error_msg for word in ["validation", "invalid", "malformed", "missing"])

    @pytest.mark.asyncio
    async def test_get_note_unicode_content_handling(self) -> None:
        """Test retrieval of notes with Unicode content."""
        # This will fail until Unicode handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        note_id = "a1b2c3d4e5f6789012345678901234567890abcd"

        unicode_note = {
            "id": note_id,
            "title": "文档标题 📋 Émojis & Ünicödé",
            "body": "# Unicöde Tëst\n\n日本語テスト\n\n🎉 Emoji test 🚀\n\n• Bullet points\n• Special chars: €£¥",
            "parent_id": "notebook123",
            "created_time": 1704067200000,
            "updated_time": 1704070800000
        }

        with patch.object(client, 'get_note') as mock_get:
            mock_get.return_value = unicode_note

            note = await client.get_note(note_id)

            # Should properly handle Unicode content
            assert "📋" in note.title
            assert "日本語" in note.body
            assert "🎉" in note.body
            assert "€" in note.body

    @pytest.mark.asyncio
    async def test_get_note_connection_timeout(self) -> None:
        """Test note retrieval handles connection timeouts."""
        # This will fail until timeout handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123",
            "timeout": 1  # Very short timeout
        }

        client = JoplinClient(config)
        note_id = "a1b2c3d4e5f6789012345678901234567890abcd"

        with patch('httpx.AsyncClient.get') as mock_get:
            import httpx
            mock_get.side_effect = httpx.TimeoutError("Request timed out")

            with pytest.raises(Exception) as exc_info:
                await client.get_note(note_id)

            # Should raise timeout-related error
            error_msg = str(exc_info.value).lower()
            assert "timeout" in error_msg or "timed out" in error_msg
