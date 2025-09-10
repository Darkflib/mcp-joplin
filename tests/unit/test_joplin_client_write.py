"""Tests for JoplinClient write operations."""

import json
import pytest
from unittest.mock import AsyncMock

import httpx
import respx

from src.services.joplin_client import JoplinClient


class TestJoplinClientWrite:
    """Test JoplinClient write operations (update_note, create_note)."""

    @pytest.fixture
    def client_config(self):
        """Configuration for Joplin client."""
        return {
            "base_url": "http://localhost:41184",
            "api_token": "test_api_token",
            "timeout": 30.0,
            "max_retries": 3,
        }

    @pytest.fixture
    async def joplin_client(self, client_config):
        """Create JoplinClient instance."""
        client = JoplinClient(client_config)
        yield client
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_note_success_title_only(self, joplin_client):
        """Test successful note title update."""
        note_id = "a1b2c3d4e5f6789012345678901234ab"
        
        # Mock the PUT request
        respx.put(
            f"http://localhost:41184//notes/{note_id}",
            params={"token": "test_api_token"},
        ).mock(return_value=httpx.Response(200, json={
            "id": note_id,
            "title": "Updated Title",
            "updated_time": "2024-01-01T12:00:00.000Z",
        }))

        result = await joplin_client.update_note(note_id, title="Updated Title")

        assert result["id"] == note_id
        assert result["title"] == "Updated Title"

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_note_success_all_fields(self, joplin_client):
        """Test successful note update with all fields."""
        note_id = "a1b2c3d4e5f6789012345678901234ab"
        parent_id = "notebook123456789012345678901234"
        
        # Mock the PUT request
        respx.put(
            f"http://localhost:41184//notes/{note_id}",
            params={"token": "test_api_token"},
        ).mock(return_value=httpx.Response(200, json={
            "id": note_id,
            "title": "Updated Title",
            "body": "Updated content",
            "parent_id": parent_id,
            "updated_time": "2024-01-01T12:00:00.000Z",
        }))

        result = await joplin_client.update_note(
            note_id=note_id,
            title="Updated Title",
            body="Updated content",
            parent_id=parent_id
        )

        assert result["id"] == note_id
        assert result["title"] == "Updated Title"
        assert result["body"] == "Updated content"
        assert result["parent_id"] == parent_id

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_note_validation_error(self, joplin_client):
        """Test update_note with no fields to update."""
        note_id = "a1b2c3d4e5f6789012345678901234ab"

        with pytest.raises(ValueError, match="At least one field"):
            await joplin_client.update_note(note_id)

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_note_not_found(self, joplin_client):
        """Test update_note with non-existent note."""
        note_id = "nonexistent1234567890123456789012"
        
        # Mock 404 response
        respx.put(
            f"http://localhost:41184//notes/{note_id}",
            params={"token": "test_api_token"},
        ).mock(return_value=httpx.Response(404, text="Note not found"))

        with pytest.raises(Exception, match=f"Note not found: {note_id}"):
            await joplin_client.update_note(note_id, title="Updated Title")

    @pytest.mark.asyncio
    @respx.mock
    async def test_update_note_auth_error(self, joplin_client):
        """Test update_note with invalid API token."""
        note_id = "a1b2c3d4e5f6789012345678901234ab"
        
        # Mock 401 response
        respx.put(
            f"http://localhost:41184//notes/{note_id}",
            params={"token": "test_api_token"},
        ).mock(return_value=httpx.Response(401, text="Unauthorized"))

        with pytest.raises(Exception, match="Authentication failed: Invalid API token"):
            await joplin_client.update_note(note_id, title="Updated Title")

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_note_success_minimal(self, joplin_client):
        """Test successful note creation with minimal data."""
        # Mock the POST request
        respx.post(
            "http://localhost:41184//notes",
            params={"token": "test_api_token"},
        ).mock(return_value=httpx.Response(200, json={
            "id": "b2c3d4e5f6789012345678901234abcd",
            "title": "New Note",
            "body": "",
            "created_time": "2024-01-01T12:00:00.000Z",
            "updated_time": "2024-01-01T12:00:00.000Z",
        }))

        result = await joplin_client.create_note(title="New Note")

        assert result["id"] == "b2c3d4e5f6789012345678901234abcd"
        assert result["title"] == "New Note"
        assert result["body"] == ""

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_note_success_with_content(self, joplin_client):
        """Test successful note creation with title and body."""
        parent_id = "notebook123456789012345678901234"
        
        # Mock the POST request
        respx.post(
            "http://localhost:41184//notes",
            params={"token": "test_api_token"},
        ).mock(return_value=httpx.Response(200, json={
            "id": "b2c3d4e5f6789012345678901234abcd",
            "title": "New Note",
            "body": "Note content with **markdown**",
            "parent_id": parent_id,
            "created_time": "2024-01-01T12:00:00.000Z",
            "updated_time": "2024-01-01T12:00:00.000Z",
        }))

        result = await joplin_client.create_note(
            title="New Note",
            body="Note content with **markdown**",
            parent_id=parent_id
        )

        assert result["id"] == "b2c3d4e5f6789012345678901234abcd"
        assert result["title"] == "New Note"
        assert result["body"] == "Note content with **markdown**"
        assert result["parent_id"] == parent_id

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_note_auth_error(self, joplin_client):
        """Test create_note with invalid API token."""
        # Mock 401 response
        respx.post(
            "http://localhost:41184//notes",
            params={"token": "test_api_token"},
        ).mock(return_value=httpx.Response(401, text="Unauthorized"))

        with pytest.raises(Exception, match="Authentication failed: Invalid API token"):
            await joplin_client.create_note(title="New Note")

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_note_server_error(self, joplin_client):
        """Test create_note with server error."""
        # Mock 500 response
        respx.post(
            "http://localhost:41184//notes",
            params={"token": "test_api_token"},
        ).mock(return_value=httpx.Response(500, text="Internal Server Error"))

        with pytest.raises(Exception, match="Create note failed: HTTP 500"):
            await joplin_client.create_note(title="New Note")

    @pytest.mark.asyncio
    async def test_update_note_connection_error(self, joplin_client):
        """Test update_note with connection error."""
        note_id = "a1b2c3d4e5f6789012345678901234ab"
        
        # Mock connection error
        with pytest.raises(Exception, match="Connection failed"):
            # This will cause a real connection error since respx is not mocked
            await joplin_client.update_note(note_id, title="Updated Title")

    @pytest.mark.asyncio
    async def test_create_note_connection_error(self, joplin_client):
        """Test create_note with connection error."""
        # Mock connection error
        with pytest.raises(Exception, match="Connection failed"):
            # This will cause a real connection error since respx is not mocked
            await joplin_client.create_note(title="New Note")