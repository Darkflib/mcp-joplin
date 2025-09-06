"""Integration tests for notebook listing functionality.

These tests verify notebook hierarchy listing works end-to-end.
They must fail initially (RED phase) before implementation.
"""

from unittest.mock import patch

import pytest

from src.services.joplin_client import JoplinClient


class TestNotebooksIntegration:
    """Test notebook listing functionality integration scenarios."""

    @pytest.fixture
    def mock_joplin_notebooks(self):
        """Sample Joplin notebooks with hierarchy for testing."""
        return {
            "items": [
                {
                    "id": "root1",
                    "title": "Personal",
                    "parent_id": "",
                    "created_time": 1704067200000,
                    "updated_time": 1704067200000
                },
                {
                    "id": "root2",
                    "title": "Work",
                    "parent_id": "",
                    "created_time": 1704067200000,
                    "updated_time": 1704067200000
                },
                {
                    "id": "child1",
                    "title": "Projects",
                    "parent_id": "root2",
                    "created_time": 1704070800000,
                    "updated_time": 1704070800000
                },
                {
                    "id": "child2",
                    "title": "Meeting Notes",
                    "parent_id": "root2",
                    "created_time": 1704074400000,
                    "updated_time": 1704074400000
                },
                {
                    "id": "grandchild1",
                    "title": "Project Alpha",
                    "parent_id": "child1",
                    "created_time": 1704078000000,
                    "updated_time": 1704078000000
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_list_all_notebooks(self, mock_joplin_notebooks) -> None:
        """Test listing all notebooks without filters."""
        # This will fail until JoplinClient.list_notebooks is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)

        with patch.object(client, 'list_notebooks') as mock_list:
            mock_list.return_value = mock_joplin_notebooks

            notebooks = await client.list_notebooks()

            # Should return all notebooks
            assert len(notebooks) == 5

            # Should include root and child notebooks
            titles = [nb.title for nb in notebooks]
            assert "Personal" in titles
            assert "Work" in titles
            assert "Projects" in titles

    @pytest.mark.asyncio
    async def test_list_notebooks_hierarchical_structure(self, mock_joplin_notebooks) -> None:
        """Test notebooks are organized in proper hierarchy."""
        # This will fail until hierarchy building is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)

        with patch.object(client, 'list_notebooks') as mock_list:
            mock_list.return_value = mock_joplin_notebooks

            notebooks = await client.list_notebooks(recursive=True)

            # Find root notebooks (no parent_id)
            root_notebooks = [nb for nb in notebooks if not nb.parent_id]
            assert len(root_notebooks) == 2

            # Find child notebooks
            work_notebook = next(nb for nb in notebooks if nb.title == "Work")
            child_notebooks = [nb for nb in notebooks if nb.parent_id == work_notebook.id]
            assert len(child_notebooks) == 2

            # Find grandchild notebooks
            projects_notebook = next(nb for nb in notebooks if nb.title == "Projects")
            grandchild_notebooks = [nb for nb in notebooks if nb.parent_id == projects_notebook.id]
            assert len(grandchild_notebooks) == 1

    @pytest.mark.asyncio
    async def test_list_notebooks_by_parent_id(self, mock_joplin_notebooks) -> None:
        """Test listing notebooks filtered by parent_id."""
        # This will fail until parent_id filtering is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        parent_id = "root2"  # Work notebook

        # Mock filtered response
        with patch.object(client, 'list_notebooks') as mock_list:
            filtered_notebooks = {
                "items": [nb for nb in mock_joplin_notebooks["items"]
                         if nb["parent_id"] == parent_id]
            }
            mock_list.return_value = filtered_notebooks

            notebooks = await client.list_notebooks(parent_id=parent_id)

            # Should only return children of Work notebook
            assert len(notebooks) == 2
            titles = [nb.title for nb in notebooks]
            assert "Projects" in titles
            assert "Meeting Notes" in titles

            # All should have the same parent
            assert all(nb.parent_id == parent_id for nb in notebooks)

    @pytest.mark.asyncio
    async def test_list_notebooks_non_recursive(self, mock_joplin_notebooks) -> None:
        """Test non-recursive listing (flat structure)."""
        # This will fail until recursive=False handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)

        with patch.object(client, 'list_notebooks') as mock_list:
            mock_list.return_value = mock_joplin_notebooks

            notebooks = await client.list_notebooks(recursive=False)

            # Should return flat list without nested structure
            assert len(notebooks) == 5

            # Each notebook should not have nested children property
            for notebook in notebooks:
                assert not hasattr(notebook, 'children') or notebook.children is None

    @pytest.mark.asyncio
    async def test_list_notebooks_with_nested_children(self, mock_joplin_notebooks) -> None:
        """Test recursive listing includes nested children."""
        # This will fail until nested children structure is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)

        with patch.object(client, 'list_notebooks') as mock_list:
            mock_list.return_value = mock_joplin_notebooks

            notebooks = await client.list_notebooks(recursive=True, nested=True)

            # Root notebooks should have children property
            work_notebook = next(nb for nb in notebooks if nb.title == "Work")
            assert hasattr(work_notebook, 'children')
            assert len(work_notebook.children) == 2

            # Child notebooks should have their own children
            projects_notebook = next(child for child in work_notebook.children
                                   if child.title == "Projects")
            assert hasattr(projects_notebook, 'children')
            assert len(projects_notebook.children) == 1

    @pytest.mark.asyncio
    async def test_list_notebooks_empty_result(self) -> None:
        """Test handling of empty notebook list."""
        # This will fail until empty results handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)

        with patch.object(client, 'list_notebooks') as mock_list:
            mock_list.return_value = {"items": []}

            notebooks = await client.list_notebooks()

            # Should return empty list, not error
            assert notebooks == []
            assert isinstance(notebooks, list)

    @pytest.mark.asyncio
    async def test_list_notebooks_invalid_parent_id(self) -> None:
        """Test handling of invalid parent_id."""
        # This will fail until parent_id validation is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)
        invalid_parent_id = "nonexistent123"

        with patch.object(client, 'list_notebooks') as mock_list:
            mock_list.return_value = {"items": []}

            notebooks = await client.list_notebooks(parent_id=invalid_parent_id)

            # Should return empty list for invalid parent
            assert notebooks == []

    @pytest.mark.asyncio
    async def test_list_notebooks_circular_reference_detection(self, mock_joplin_notebooks) -> None:
        """Test detection and handling of circular references."""
        # This will fail until circular reference detection is implemented

        # Create circular reference in test data
        circular_notebooks = mock_joplin_notebooks.copy()
        circular_notebooks["items"].append({
            "id": "circular1",
            "title": "Circular Parent",
            "parent_id": "circular2",
            "created_time": 1704081600000,
            "updated_time": 1704081600000
        })
        circular_notebooks["items"].append({
            "id": "circular2",
            "title": "Circular Child",
            "parent_id": "circular1",
            "created_time": 1704081600000,
            "updated_time": 1704081600000
        })

        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)

        with patch.object(client, 'list_notebooks') as mock_list:
            mock_list.return_value = circular_notebooks

            # Should detect and handle circular reference
            notebooks = await client.list_notebooks(recursive=True)

            # Should not get stuck in infinite loop
            assert len(notebooks) > 0

            # Circular notebooks should be included but without infinite nesting
            circular_titles = [nb.title for nb in notebooks
                              if nb.title in ["Circular Parent", "Circular Child"]]
            assert len(circular_titles) == 2

    @pytest.mark.asyncio
    async def test_list_notebooks_metadata_completeness(self, mock_joplin_notebooks) -> None:
        """Test all notebook metadata fields are properly populated."""
        # This will fail until metadata mapping is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)

        with patch.object(client, 'list_notebooks') as mock_list:
            mock_list.return_value = mock_joplin_notebooks

            notebooks = await client.list_notebooks()

            for notebook in notebooks:
                # Required fields should be present
                assert hasattr(notebook, 'id') and notebook.id
                assert hasattr(notebook, 'title') and notebook.title
                assert hasattr(notebook, 'created_time') and notebook.created_time > 0
                assert hasattr(notebook, 'updated_time') and notebook.updated_time > 0

                # parent_id can be None for root notebooks
                assert hasattr(notebook, 'parent_id')

                # Timestamps should be valid
                assert isinstance(notebook.created_time, int)
                assert isinstance(notebook.updated_time, int)
                assert notebook.created_time <= notebook.updated_time
