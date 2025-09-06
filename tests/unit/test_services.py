"""Unit tests for core services."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from src.services.connection_manager import ConnectionManager
from src.services.joplin_client import JoplinClient
from src.services.rate_limiter import RateLimiter
from src.services.search_service import SearchService


class TestJoplinClient:
    """Unit tests for JoplinClient."""

    @pytest.fixture
    def client(self):
        """Create JoplinClient instance for testing."""
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test_token",
            "timeout": 30.0
        }
        return JoplinClient(config)

    @pytest.mark.asyncio
    async def test_search_notes_success(self, client):
        """Test successful note search."""
        mock_response = {
            "items": [
                {
                    "id": "a" * 32,
                    "title": "Test Note",
                    "body": "Test content",
                    "created_time": 1640995200000,
                    "updated_time": 1640995200000
                }
            ],
            "has_more": False
        }

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.search_notes("test query", limit=10)

            assert result == mock_response
            mock_request.assert_called_once()

            # Verify the request parameters
            call_args = mock_request.call_args
            assert "search" in call_args[0][1]  # endpoint
            assert call_args[1]["params"]["query"] == "test query"
            assert call_args[1]["params"]["limit"] == 10

    @pytest.mark.asyncio
    async def test_search_notes_with_notebook(self, client):
        """Test note search with notebook filter."""
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"items": [], "has_more": False}

            await client.search_notes("test", limit=5, notebook_id="n" * 32)

            call_args = mock_request.call_args
            assert call_args[1]["params"]["notebook"] == "n" * 32

    @pytest.mark.asyncio
    async def test_get_note_success(self, client):
        """Test successful note retrieval."""
        mock_note = {
            "id": "a" * 32,
            "title": "Test Note",
            "body": "Test content",
            "parent_id": "b" * 32,
            "created_time": 1640995200000,
            "updated_time": 1640995200000
        }

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_note

            result = await client.get_note("a" * 32)

            assert result == mock_note
            mock_request.assert_called_once_with("GET", f"notes/{'a' * 32}")

    @pytest.mark.asyncio
    async def test_get_note_with_fields(self, client):
        """Test note retrieval with specific fields."""
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"id": "a" * 32, "title": "Test"}

            await client.get_note("a" * 32, fields="id,title")

            call_args = mock_request.call_args
            assert call_args[1]["params"]["fields"] == "id,title"

    @pytest.mark.asyncio
    async def test_list_notebooks_success(self, client):
        """Test successful notebook listing."""
        mock_response = {
            "items": [
                {
                    "id": "n1" + "a" * 30,
                    "title": "Notebook 1",
                    "created_time": 1640995200000
                },
                {
                    "id": "n2" + "a" * 30,
                    "title": "Notebook 2",
                    "parent_id": "n1" + "a" * 30,
                    "created_time": 1640995200000
                }
            ],
            "has_more": False
        }

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.list_notebooks()

            assert result == mock_response
            mock_request.assert_called_once_with("GET", "folders", params={"limit": 100})

    @pytest.mark.asyncio
    async def test_get_notes_in_notebook_success(self, client):
        """Test successful retrieval of notes in notebook."""
        mock_response = {
            "items": [
                {
                    "id": "a" * 32,
                    "title": "Note in Notebook",
                    "body": "Content",
                    "parent_id": "n" * 32
                }
            ],
            "has_more": False
        }

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.get_notes_in_notebook("n" * 32, limit=50)

            assert result == mock_response
            mock_request.assert_called_once()

            call_args = mock_request.call_args
            assert "notes" in call_args[0][1]
            assert call_args[1]["params"]["parent_id"] == "n" * 32
            assert call_args[1]["params"]["limit"] == 50

    @pytest.mark.asyncio
    async def test_ping_success(self, client):
        """Test successful ping."""
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"status": "ok"}

            result = await client.ping()

            assert result["status"] == "ok"
            mock_request.assert_called_once_with("GET", "ping")

    @pytest.mark.asyncio
    async def test_make_request_http_error(self, client):
        """Test HTTP error handling."""
        with patch('httpx.AsyncClient.request') as mock_request:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                message="Not Found",
                request=Mock(),
                response=Mock(status_code=404)
            )
            mock_request.return_value = mock_response

            with pytest.raises(Exception) as exc_info:
                await client._make_request("GET", "invalid")

            assert "404" in str(exc_info.value) or "Not Found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_timeout(self, client):
        """Test request timeout handling."""
        with patch('httpx.AsyncClient.request') as mock_request:
            mock_request.side_effect = httpx.TimeoutException("Request timed out")

            with pytest.raises(Exception) as exc_info:
                await client._make_request("GET", "test")

            assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test client cleanup."""
        client._client = Mock()
        client._client.aclose = AsyncMock()

        await client.close()

        client._client.aclose.assert_called_once()


class TestSearchService:
    """Unit tests for SearchService."""

    @pytest.fixture
    def joplin_client_mock(self):
        """Create mock JoplinClient."""
        return AsyncMock(spec=JoplinClient)

    @pytest.fixture
    def search_service(self, joplin_client_mock):
        """Create SearchService instance for testing."""
        return SearchService(joplin_client_mock)

    @pytest.mark.asyncio
    async def test_search_notes_success(self, search_service, joplin_client_mock):
        """Test successful note search with relevance scoring."""
        mock_joplin_response = {
            "items": [
                {
                    "id": "a" * 32,
                    "title": "Python Programming",
                    "body": "Learn Python programming basics and advanced concepts",
                    "created_time": 1640995200000
                },
                {
                    "id": "b" * 32,
                    "title": "JavaScript Guide",
                    "body": "Comprehensive guide to JavaScript development",
                    "created_time": 1640995200000
                }
            ],
            "has_more": False
        }

        joplin_client_mock.search_notes.return_value = mock_joplin_response

        result = await search_service.search_notes("Python", limit=10)

        assert result.query == "Python"
        assert len(result.items) == 2
        assert result.total_count == 2

        # First item should have higher relevance (title match)
        assert result.items[0].note_id == "a" * 32
        assert result.items[0].relevance_score > result.items[1].relevance_score
        assert "Python" in result.items[0].snippet

    @pytest.mark.asyncio
    async def test_search_notes_with_notebook_filter(self, search_service, joplin_client_mock):
        """Test search with notebook filter."""
        joplin_client_mock.search_notes.return_value = {"items": [], "has_more": False}

        await search_service.search_notes("test", notebook_id="n" * 32)

        joplin_client_mock.search_notes.assert_called_once_with(
            "test", limit=10, notebook_id="n" * 32
        )

    def test_calculate_relevance_title_match(self, search_service):
        """Test relevance calculation with title match."""
        note = {
            "title": "Python Programming Guide",
            "body": "This guide covers Python basics"
        }

        score = search_service._calculate_relevance("Python", note)

        assert score > 0.5  # Title match should give high score

    def test_calculate_relevance_body_match(self, search_service):
        """Test relevance calculation with body match only."""
        note = {
            "title": "Programming Guide",
            "body": "This guide covers Python programming concepts"
        }

        score = search_service._calculate_relevance("Python", note)

        assert 0 < score < 0.5  # Body match should give lower score than title

    def test_calculate_relevance_no_match(self, search_service):
        """Test relevance calculation with no match."""
        note = {
            "title": "JavaScript Guide",
            "body": "This guide covers JavaScript concepts"
        }

        score = search_service._calculate_relevance("Python", note)

        assert score == 0.0  # No match should give zero score

    def test_generate_snippet_with_match(self, search_service):
        """Test snippet generation with query match."""
        body = "This is a long text about Python programming. It covers many concepts including variables, functions, and classes. Python is a great language for beginners."

        snippet = search_service._generate_snippet(body, "Python", max_length=100)

        assert len(snippet) <= 100
        assert "Python" in snippet
        assert "..." in snippet or len(body) <= 100

    def test_generate_snippet_no_match(self, search_service):
        """Test snippet generation without query match."""
        body = "This is a text about programming concepts and development practices."

        snippet = search_service._generate_snippet(body, "missing", max_length=50)

        assert len(snippet) <= 50
        assert snippet.startswith("This is a text")


class TestConnectionManager:
    """Unit tests for ConnectionManager."""

    @pytest.fixture
    def connection_config(self):
        """Create connection config for testing."""
        return {
            "base_url": "http://localhost:41184",
            "api_token": "test_token",
            "timeout": 30.0,
            "max_retries": 3,
            "retry_delay": 1.0
        }

    @pytest.fixture
    def connection_manager(self, connection_config):
        """Create ConnectionManager instance for testing."""
        return ConnectionManager(connection_config)

    @pytest.mark.asyncio
    async def test_get_client_first_time(self, connection_manager):
        """Test getting client for first time."""
        with patch('src.services.connection_manager.JoplinClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            client = await connection_manager.get_client()

            assert client == mock_client
            assert connection_manager._client == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_cached(self, connection_manager):
        """Test getting cached client."""
        mock_client = AsyncMock()
        connection_manager._client = mock_client

        client = await connection_manager.get_client()

        assert client == mock_client

    @pytest.mark.asyncio
    async def test_ensure_connected_success(self, connection_manager):
        """Test successful connection check."""
        mock_client = AsyncMock()
        mock_client.ping.return_value = {"status": "ok"}
        connection_manager._client = mock_client

        await connection_manager.ensure_connected()

        mock_client.ping.assert_called_once()
        assert connection_manager.connection_state.connected is True

    @pytest.mark.asyncio
    async def test_ensure_connected_retry_success(self, connection_manager):
        """Test connection with retry success."""
        mock_client = AsyncMock()
        # First call fails, second succeeds
        mock_client.ping.side_effect = [
            Exception("Connection failed"),
            {"status": "ok"}
        ]
        connection_manager._client = mock_client

        await connection_manager.ensure_connected()

        assert mock_client.ping.call_count == 2
        assert connection_manager.connection_state.connected is True

    @pytest.mark.asyncio
    async def test_ensure_connected_max_retries(self, connection_manager):
        """Test connection fails after max retries."""
        mock_client = AsyncMock()
        mock_client.ping.side_effect = Exception("Connection failed")
        connection_manager._client = mock_client

        with pytest.raises(Exception):
            await connection_manager.ensure_connected()

        assert mock_client.ping.call_count == 4  # Initial + 3 retries

    @pytest.mark.asyncio
    async def test_health_check_connected(self, connection_manager):
        """Test health check when connected."""
        connection_manager.connection_state.connected = True
        connection_manager.connection_state.last_ping_time = datetime.now()

        health = await connection_manager.health_check()

        assert health["connected"] is True
        assert health["last_ping_time"] is not None

    @pytest.mark.asyncio
    async def test_health_check_disconnected(self, connection_manager):
        """Test health check when disconnected."""
        connection_manager.connection_state.connected = False
        connection_manager.connection_state.last_error = "Connection refused"

        health = await connection_manager.health_check()

        assert health["connected"] is False
        assert health["error"] == "Connection refused"

    @pytest.mark.asyncio
    async def test_disconnect(self, connection_manager):
        """Test disconnection cleanup."""
        mock_client = AsyncMock()
        connection_manager._client = mock_client

        await connection_manager.disconnect()

        mock_client.close.assert_called_once()
        assert connection_manager._client is None


class TestRateLimiter:
    """Unit tests for RateLimiter."""

    @pytest.fixture
    def rate_config(self):
        """Create rate limiter config for testing."""
        return {
            "requests_per_second": 10,
            "burst_size": 20
        }

    @pytest.fixture
    def rate_limiter(self, rate_config):
        """Create RateLimiter instance for testing."""
        return RateLimiter(rate_config)

    def test_rate_limiter_initialization(self, rate_limiter):
        """Test rate limiter initialization."""
        assert rate_limiter.rate == 10
        assert rate_limiter.capacity == 20
        assert rate_limiter.tokens == 20  # Start with full bucket

    @pytest.mark.asyncio
    async def test_acquire_success(self, rate_limiter):
        """Test successful token acquisition."""
        result = await rate_limiter.acquire()

        assert result is True
        assert rate_limiter.tokens == 19  # One token consumed

    @pytest.mark.asyncio
    async def test_acquire_multiple_tokens(self, rate_limiter):
        """Test acquiring multiple tokens."""
        result = await rate_limiter.acquire(tokens=5)

        assert result is True
        assert rate_limiter.tokens == 15  # Five tokens consumed

    @pytest.mark.asyncio
    async def test_acquire_insufficient_tokens(self, rate_limiter):
        """Test acquisition when insufficient tokens."""
        # Consume all tokens
        rate_limiter.tokens = 0

        result = await rate_limiter.acquire()

        assert result is False
        assert rate_limiter.tokens == 0  # No tokens consumed

    def test_token_refill(self, rate_limiter):
        """Test token bucket refill."""
        # Consume some tokens
        rate_limiter.tokens = 10
        original_time = rate_limiter.last_refill

        # Simulate time passing
        rate_limiter.last_refill = original_time - 1.0  # 1 second ago

        # Trigger refill
        rate_limiter._refill_tokens()

        # Should have refilled 10 tokens (1 second * 10 per second)
        assert rate_limiter.tokens == 20  # Min of (10 + 10, 20)

    @pytest.mark.asyncio
    async def test_get_status(self, rate_limiter):
        """Test getting rate limiter status."""
        # Consume some tokens
        await rate_limiter.acquire(tokens=5)

        status = await rate_limiter.get_status()

        assert status["tokens_available"] == 15
        assert status["capacity"] == 20
        assert status["rate_per_second"] == 10
        assert status["utilization_percent"] == 25.0  # (20-15)/20 * 100

    def test_rate_limiter_disabled(self):
        """Test rate limiter when disabled."""
        rate_limiter = RateLimiter({})  # No rate limiting config

        # Should always allow requests
        assert asyncio.run(rate_limiter.acquire()) is True
        assert asyncio.run(rate_limiter.acquire(tokens=1000)) is True

    def test_token_refill_maximum_capacity(self, rate_limiter):
        """Test token refill doesn't exceed capacity."""
        rate_limiter.tokens = 0
        rate_limiter.last_refill = rate_limiter.last_refill - 10.0  # 10 seconds ago

        rate_limiter._refill_tokens()

        # Should not exceed capacity even with large time gap
        assert rate_limiter.tokens == 20  # Capacity limit

    @pytest.mark.asyncio
    async def test_concurrent_acquire(self, rate_limiter):
        """Test concurrent token acquisition."""
        # Create multiple concurrent acquire tasks
        tasks = [rate_limiter.acquire() for _ in range(25)]  # More than capacity

        results = await asyncio.gather(*tasks)

        # First 20 should succeed (capacity), rest should fail
        successful = sum(1 for result in results if result is True)
        assert successful == 20
        assert rate_limiter.tokens == 0
