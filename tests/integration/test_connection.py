"""Integration tests for basic connection and authentication.

These tests verify the MCP server can connect to Joplin instance.
They must fail initially (RED phase) before implementation.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.connection_manager import ConnectionManager
from src.services.joplin_client import JoplinClient


class TestConnectionIntegration:
    """Test basic connection and authentication scenarios."""

    @pytest.mark.asyncio
    async def test_joplin_connection_success(self) -> None:
        """Test successful connection to Joplin instance."""
        # This will fail until JoplinClient is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123",
            "timeout": 30
        }

        client = JoplinClient(config)

        # Mock successful ping response
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = "JoplinClipperServer"
            mock_get.return_value = mock_response

            is_connected = await client.ping()
            assert is_connected is True

    @pytest.mark.asyncio
    async def test_joplin_connection_failure_not_running(self) -> None:
        """Test connection failure when Joplin is not running."""
        # This will fail until error handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123",
            "timeout": 5
        }

        client = JoplinClient(config)

        # Mock connection refused error
        with patch('httpx.AsyncClient.get') as mock_get:
            import httpx
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            is_connected = await client.ping()
            assert is_connected is False

    @pytest.mark.asyncio
    async def test_joplin_authentication_failure(self) -> None:
        """Test authentication failure with invalid token."""
        # This will fail until authentication handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "invalid-token",
            "timeout": 30
        }

        client = JoplinClient(config)

        # Mock 401 unauthorized response
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_get.return_value = mock_response

            is_connected = await client.ping()
            assert is_connected is False

    @pytest.mark.asyncio
    async def test_connection_manager_retry_logic(self) -> None:
        """Test connection manager implements retry logic."""
        # This will fail until ConnectionManager is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123",
            "timeout": 10,
            "max_retries": 3
        }

        manager = ConnectionManager(config)

        # Mock temporary failure then success
        call_count = 0
        def mock_ping():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return False
            return True

        with patch.object(manager.client, 'ping', side_effect=lambda: mock_ping()):
            result = await manager.ensure_connected()
            assert result is True
            assert call_count == 3  # Should have retried

    @pytest.mark.asyncio
    async def test_connection_health_check_logging(self) -> None:
        """Test connection health check includes structured logging."""
        # This will fail until logging is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = "JoplinClipperServer"
            mock_get.return_value = mock_response

            # Mock logger to capture log calls
            with patch('src.services.joplin_client.logger') as mock_logger:
                await client.ping()

                # Should log connection attempt and success
                assert mock_logger.info.called
                log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                assert any("ping" in call.lower() for call in log_calls)

    @pytest.mark.asyncio
    async def test_connection_timeout_handling(self) -> None:
        """Test connection properly handles timeout scenarios."""
        # This will fail until timeout handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123",
            "timeout": 1  # Very short timeout
        }

        client = JoplinClient(config)

        # Mock timeout error
        with patch('httpx.AsyncClient.get') as mock_get:
            import httpx
            mock_get.side_effect = httpx.TimeoutError("Request timed out")

            is_connected = await client.ping()
            assert is_connected is False

    @pytest.mark.asyncio
    async def test_mcp_server_connection_integration(self) -> None:
        """Test MCP server properly integrates with connection manager."""
        # This will fail until MCP server integration is implemented
        from src.server import create_mcp_server

        config = {
            "joplin": {
                "base_url": "http://localhost:41184",
                "api_token": "test-token-123"
            }
        }

        # Mock successful Joplin connection
        with patch('src.services.joplin_client.JoplinClient.ping') as mock_ping:
            mock_ping.return_value = True

            server = await create_mcp_server(config)

            # Server should have connection manager
            assert hasattr(server, 'connection_manager')

            # Connection should be established
            is_connected = await server.connection_manager.is_connected()
            assert is_connected is True
