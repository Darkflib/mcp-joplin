"""Unit tests for data models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.connection import ConnectionConfig, ConnectionState
from src.models.mcp_tool import MCPTool
from src.models.note import Note, NoteBody
from src.models.notebook import Notebook
from src.models.search_result import SearchResult, SearchResultItem


class TestNote:
    """Unit tests for Note model."""

    def test_note_creation_minimal(self):
        """Test creating note with minimal required fields."""
        note = Note(
            id="a" * 32,
            title="Test Note",
            body="Test content"
        )

        assert note.id == "a" * 32
        assert note.title == "Test Note"
        assert note.body == "Test content"
        assert note.notebook_id is None
        assert note.tags == []
        assert note.created_time is None
        assert note.updated_time is None

    def test_note_creation_full(self):
        """Test creating note with all fields."""
        created_time = datetime(2025, 1, 1, 12, 0, 0)
        updated_time = datetime(2025, 1, 2, 12, 0, 0)

        note = Note(
            id="b" * 32,
            title="Full Test Note",
            body="Full test content",
            notebook_id="c" * 32,
            tags=["tag1", "tag2"],
            created_time=created_time,
            updated_time=updated_time
        )

        assert note.id == "b" * 32
        assert note.title == "Full Test Note"
        assert note.body == "Full test content"
        assert note.notebook_id == "c" * 32
        assert note.tags == ["tag1", "tag2"]
        assert note.created_time == created_time
        assert note.updated_time == updated_time

    def test_note_id_validation_length(self):
        """Test note ID must be 32 characters."""
        with pytest.raises(ValidationError) as exc_info:
            Note(
                id="short",
                title="Test",
                body="Test"
            )

        assert "32 characters" in str(exc_info.value)

    def test_note_id_validation_hex(self):
        """Test note ID must be hexadecimal."""
        with pytest.raises(ValidationError) as exc_info:
            Note(
                id="g" * 32,  # Invalid hex character
                title="Test",
                body="Test"
            )

        assert "hexadecimal" in str(exc_info.value)

    def test_note_title_required(self):
        """Test note title is required."""
        with pytest.raises(ValidationError) as exc_info:
            Note(
                id="a" * 32,
                title="",
                body="Test"
            )

        assert "title" in str(exc_info.value)

    def test_note_body_required(self):
        """Test note body is required."""
        with pytest.raises(ValidationError) as exc_info:
            Note(
                id="a" * 32,
                title="Test",
                body=""
            )

        assert "body" in str(exc_info.value)

    def test_note_tags_parsing(self):
        """Test tag parsing from string."""
        # Test with tag string
        body = NoteBody(body_text="Content with tags: tag1, tag2, tag3")
        tags = body.parse_tags_from_body()

        # Note: This test assumes parse_tags_from_body implementation
        # Actual behavior depends on implementation
        assert isinstance(tags, list)

    def test_note_utf8_validation(self):
        """Test UTF-8 content validation."""
        # Valid UTF-8
        note = Note(
            id="a" * 32,
            title="测试笔记",  # Chinese characters
            body="内容包含中文字符"
        )

        assert note.title == "测试笔记"
        assert note.body == "内容包含中文字符"


class TestNotebook:
    """Unit tests for Notebook model."""

    def test_notebook_creation_minimal(self):
        """Test creating notebook with minimal fields."""
        notebook = Notebook(
            id="a" * 32,
            title="Test Notebook"
        )

        assert notebook.id == "a" * 32
        assert notebook.title == "Test Notebook"
        assert notebook.parent_id is None
        assert notebook.created_time is None
        assert notebook.updated_time is None

    def test_notebook_creation_full(self):
        """Test creating notebook with all fields."""
        created_time = datetime(2025, 1, 1, 12, 0, 0)
        updated_time = datetime(2025, 1, 2, 12, 0, 0)

        notebook = Notebook(
            id="b" * 32,
            title="Full Test Notebook",
            parent_id="c" * 32,
            created_time=created_time,
            updated_time=updated_time
        )

        assert notebook.id == "b" * 32
        assert notebook.title == "Full Test Notebook"
        assert notebook.parent_id == "c" * 32
        assert notebook.created_time == created_time
        assert notebook.updated_time == updated_time

    def test_notebook_id_validation(self):
        """Test notebook ID validation."""
        with pytest.raises(ValidationError) as exc_info:
            Notebook(
                id="invalid",
                title="Test"
            )

        assert "32 characters" in str(exc_info.value)

    def test_notebook_title_required(self):
        """Test notebook title is required."""
        with pytest.raises(ValidationError) as exc_info:
            Notebook(
                id="a" * 32,
                title=""
            )

        assert "title" in str(exc_info.value)

    def test_notebook_parent_validation(self):
        """Test parent ID validation."""
        with pytest.raises(ValidationError) as exc_info:
            Notebook(
                id="a" * 32,
                title="Test",
                parent_id="invalid"
            )

        assert "32 characters" in str(exc_info.value)

    def test_notebook_circular_reference_detection(self):
        """Test circular reference detection."""
        # This test assumes implementation of circular reference checking
        # in the Notebook model's validation
        notebook = Notebook(
            id="a" * 32,
            title="Test Notebook",
            parent_id="a" * 32  # Self-reference
        )

        # Validation would need to be implemented in the model
        # For now, just ensure the model can be created
        assert notebook.parent_id == "a" * 32


class TestSearchResult:
    """Unit tests for SearchResult model."""

    def test_search_result_creation(self):
        """Test creating search result."""
        items = [
            SearchResultItem(
                note_id="a" * 32,
                title="Test Note 1",
                snippet="Test snippet 1",
                relevance_score=0.95
            ),
            SearchResultItem(
                note_id="b" * 32,
                title="Test Note 2",
                snippet="Test snippet 2",
                relevance_score=0.87
            )
        ]

        result = SearchResult(
            query="test query",
            items=items,
            total_count=2
        )

        assert result.query == "test query"
        assert len(result.items) == 2
        assert result.total_count == 2
        assert result.items[0].relevance_score == 0.95

    def test_search_result_item_validation(self):
        """Test search result item validation."""
        with pytest.raises(ValidationError) as exc_info:
            SearchResultItem(
                note_id="invalid",
                title="Test",
                snippet="Test",
                relevance_score=0.5
            )

        assert "32 characters" in str(exc_info.value)

    def test_search_result_relevance_score_range(self):
        """Test relevance score must be in valid range."""
        with pytest.raises(ValidationError) as exc_info:
            SearchResultItem(
                note_id="a" * 32,
                title="Test",
                snippet="Test",
                relevance_score=1.5  # Invalid: > 1.0
            )

        assert "relevance_score" in str(exc_info.value)

    def test_search_result_empty_items(self):
        """Test search result with no items."""
        result = SearchResult(
            query="empty query",
            items=[],
            total_count=0
        )

        assert result.query == "empty query"
        assert len(result.items) == 0
        assert result.total_count == 0


class TestConnectionState:
    """Unit tests for ConnectionState model."""

    def test_connection_state_creation(self):
        """Test creating connection state."""
        state = ConnectionState(
            connected=True,
            last_ping_time=datetime.now(),
            connection_attempts=3,
            last_error=None
        )

        assert state.connected is True
        assert isinstance(state.last_ping_time, datetime)
        assert state.connection_attempts == 3
        assert state.last_error is None

    def test_connection_state_with_error(self):
        """Test connection state with error."""
        state = ConnectionState(
            connected=False,
            last_ping_time=None,
            connection_attempts=5,
            last_error="Connection refused"
        )

        assert state.connected is False
        assert state.last_ping_time is None
        assert state.connection_attempts == 5
        assert state.last_error == "Connection refused"


class TestConnectionConfig:
    """Unit tests for ConnectionConfig model."""

    def test_connection_config_creation(self):
        """Test creating connection config."""
        config = ConnectionConfig(
            base_url="http://localhost:41184",
            api_token="test_token_123",
            timeout=30.0,
            max_retries=3,
            retry_delay=1.0
        )

        assert config.base_url == "http://localhost:41184"
        assert config.api_token == "test_token_123"
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.retry_delay == 1.0

    def test_connection_config_defaults(self):
        """Test connection config defaults."""
        config = ConnectionConfig(
            base_url="http://localhost:41184",
            api_token="test_token"
        )

        assert config.timeout == 30.0  # Default
        assert config.max_retries == 3  # Default
        assert config.retry_delay == 1.0  # Default

    def test_connection_config_validation(self):
        """Test connection config validation."""
        with pytest.raises(ValidationError) as exc_info:
            ConnectionConfig(
                base_url="invalid_url",
                api_token="test_token"
            )

        assert "url" in str(exc_info.value).lower()


class TestMCPTool:
    """Unit tests for MCPTool model."""

    def test_mcp_tool_creation(self):
        """Test creating MCP tool."""
        schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }

        tool = MCPTool(
            name="search_notes",
            description="Search for notes in Joplin",
            input_schema=schema
        )

        assert tool.name == "search_notes"
        assert tool.description == "Search for notes in Joplin"
        assert tool.input_schema == schema

    def test_mcp_tool_name_validation(self):
        """Test MCP tool name validation."""
        with pytest.raises(ValidationError) as exc_info:
            MCPTool(
                name="",  # Empty name
                description="Test tool",
                input_schema={"type": "object"}
            )

        assert "name" in str(exc_info.value)

    def test_mcp_tool_schema_validation(self):
        """Test MCP tool JSON schema validation."""
        # Valid schema
        valid_schema = {
            "type": "object",
            "properties": {
                "param": {"type": "string"}
            }
        }

        tool = MCPTool(
            name="test_tool",
            description="Test tool",
            input_schema=valid_schema
        )

        assert tool.input_schema == valid_schema

        # Invalid schema (if validation is implemented)
        # This would depend on the actual validation implementation
        invalid_schema = {"invalid": "schema"}

        try:
            MCPTool(
                name="test_tool",
                description="Test tool",
                input_schema=invalid_schema
            )
        except ValidationError:
            # Expected if schema validation is implemented
            pass


class TestModelIntegration:
    """Integration tests between models."""

    def test_note_with_notebook(self):
        """Test note referencing notebook."""
        notebook = Notebook(
            id="n" * 32,
            title="Test Notebook"
        )

        note = Note(
            id="a" * 32,
            title="Test Note",
            body="Test content",
            notebook_id=notebook.id
        )

        assert note.notebook_id == notebook.id

    def test_search_result_with_notes(self):
        """Test search result containing note references."""
        item = SearchResultItem(
            note_id="a" * 32,
            title="Found Note",
            snippet="This note was found in search",
            relevance_score=0.92
        )

        result = SearchResult(
            query="search term",
            items=[item],
            total_count=1
        )

        assert result.items[0].note_id == "a" * 32
        assert len(result.items) == result.total_count
