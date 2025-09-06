"""Integration tests for search notes functionality.

These tests verify search functionality works end-to-end.
They must fail initially (RED phase) before implementation.
"""

from unittest.mock import patch

import pytest

from src.services.joplin_client import JoplinClient
from src.services.search_service import SearchService


class TestSearchIntegration:
    """Test search notes functionality integration scenarios."""

    @pytest.fixture
    def mock_joplin_notes(self):
        """Sample Joplin notes for testing."""
        return {
            "items": [
                {
                    "id": "note1",
                    "title": "Project Planning Meeting",
                    "body": "Discussed project timeline and deliverables",
                    "parent_id": "notebook1",
                    "created_time": 1704067200000,
                    "updated_time": 1704067200000
                },
                {
                    "id": "note2",
                    "title": "Daily Todo List",
                    "body": "1. Review project status\n2. Update documentation",
                    "parent_id": "notebook1",
                    "created_time": 1704070800000,
                    "updated_time": 1704070800000
                },
                {
                    "id": "note3",
                    "title": "Meeting Notes",
                    "body": "Team discussed upcoming project milestones",
                    "parent_id": "notebook2",
                    "created_time": 1704074400000,
                    "updated_time": 1704074400000
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_search_notes_basic_query(self, mock_joplin_notes) -> None:
        """Test basic search functionality with keyword matching."""
        # This will fail until SearchService is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        search_service = SearchService(client)

        # Mock Joplin API response
        with patch.object(client, 'search_notes') as mock_search:
            mock_search.return_value = mock_joplin_notes

            results = await search_service.search("project")

            # Should return relevant results with scoring
            assert len(results) > 0
            assert all(hasattr(result, 'score') for result in results)
            assert all(0.0 <= result.score <= 1.0 for result in results)

            # Results should contain project-related notes
            project_results = [r for r in results if "project" in r.title.lower() or "project" in r.snippet.lower()]
            assert len(project_results) >= 2

    @pytest.mark.asyncio
    async def test_search_notes_relevance_scoring(self, mock_joplin_notes) -> None:
        """Test search results are properly scored by relevance."""
        # This will fail until relevance scoring is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        search_service = SearchService(client)

        with patch.object(client, 'search_notes') as mock_search:
            mock_search.return_value = mock_joplin_notes

            results = await search_service.search("project")

            # Results should be ordered by relevance score
            scores = [result.score for result in results]
            assert scores == sorted(scores, reverse=True)

            # Title matches should score higher than body matches
            title_match = next((r for r in results if "project" in r.title.lower()), None)
            body_match = next((r for r in results if "project" in r.snippet.lower() and "project" not in r.title.lower()), None)

            if title_match and body_match:
                assert title_match.score > body_match.score

    @pytest.mark.asyncio
    async def test_search_notes_with_limit(self, mock_joplin_notes) -> None:
        """Test search respects limit parameter."""
        # This will fail until limit handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        search_service = SearchService(client)

        with patch.object(client, 'search_notes') as mock_search:
            mock_search.return_value = mock_joplin_notes

            results = await search_service.search("project", limit=2)

            # Should return at most 2 results
            assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_search_notes_notebook_filter(self, mock_joplin_notes) -> None:
        """Test search with notebook_id filter."""
        # This will fail until notebook filtering is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        search_service = SearchService(client)

        with patch.object(client, 'search_notes') as mock_search:
            # Filter mock data for specific notebook
            filtered_notes = {
                "items": [note for note in mock_joplin_notes["items"]
                         if note["parent_id"] == "notebook1"]
            }
            mock_search.return_value = filtered_notes

            results = await search_service.search("project", notebook_id="notebook1")

            # All results should be from notebook1
            assert all(result.note_id in ["note1", "note2"] for result in results)

    @pytest.mark.asyncio
    async def test_search_notes_empty_results(self) -> None:
        """Test search handles empty results gracefully."""
        # This will fail until empty results handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        search_service = SearchService(client)

        with patch.object(client, 'search_notes') as mock_search:
            mock_search.return_value = {"items": []}

            results = await search_service.search("nonexistent")

            # Should return empty list, not error
            assert results == []
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_notes_connection_error_handling(self) -> None:
        """Test search handles Joplin connection errors gracefully."""
        # This will fail until error handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        search_service = SearchService(client)

        with patch.object(client, 'search_notes') as mock_search:
            import httpx
            mock_search.side_effect = httpx.ConnectError("Connection failed")

            with pytest.raises(Exception) as exc_info:
                await search_service.search("project")

            # Should raise appropriate error with context
            error_msg = str(exc_info.value).lower()
            assert "connection" in error_msg or "failed" in error_msg

    @pytest.mark.asyncio
    async def test_search_with_special_characters(self, mock_joplin_notes) -> None:
        """Test search handles special characters in queries."""
        # This will fail until query sanitization is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        search_service = SearchService(client)

        special_queries = ["project & task", "meeting (notes)", "todo: important!"]

        for query in special_queries:
            with patch.object(client, 'search_notes') as mock_search:
                mock_search.return_value = mock_joplin_notes

                # Should not raise exception
                results = await search_service.search(query)
                assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_snippet_generation(self, mock_joplin_notes) -> None:
        """Test search generates appropriate content snippets."""
        # This will fail until snippet generation is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        search_service = SearchService(client)

        with patch.object(client, 'search_notes') as mock_search:
            mock_search.return_value = mock_joplin_notes

            results = await search_service.search("project")

            for result in results:
                # Snippets should be limited length
                assert len(result.snippet) <= 200

                # Snippets should contain search context
                assert result.snippet.strip() != ""
