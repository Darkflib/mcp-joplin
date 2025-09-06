"""MCP server setup and tool registration."""

import logging
import time
from typing import Any

from mcp import types
from mcp.server import Server

from src.middleware.error_handler import ErrorHandler
from src.middleware.health_check import HealthChecker
from src.services.connection_manager import ConnectionManager
from src.services.joplin_client import JoplinClient
from src.services.rate_limiter import RateLimiter
from src.services.search_service import SearchService
from src.tools.get_note import get_note_tool
from src.tools.get_notes_in_notebook import get_notes_in_notebook_tool
from src.tools.list_notebooks import list_notebooks_tool
from src.tools.search_notes import search_notes_tool

logger = logging.getLogger(__name__)

# Global client instance for tools to access
_global_joplin_client = None
_global_search_service = None


class JoplinMCPServer:
    """Joplin MCP Server with tool registration and connection management."""

    def __init__(self, config: dict[str, Any]):
        """Initialize MCP server with configuration."""
        self.config = config
        self.server = Server("joplin-mcp-server")

        # Initialize services
        self.connection_manager: ConnectionManager | None = None
        self.joplin_client: JoplinClient | None = None
        self.search_service: SearchService | None = None
        self.rate_limiter: RateLimiter | None = None
        self.health_checker: HealthChecker | None = None

        logger.info(
            "Joplin MCP server initialized",
            extra={
                "server_name": "joplin-mcp-server",
                "config_keys": list(config.keys()),
            },
        )

    async def initialize(self) -> None:
        """Initialize server services and connections."""
        try:
            logger.info("Initializing server services")

            # Initialize rate limiter
            rate_config = self.config.get("rate_limiting", {})
            self.rate_limiter = RateLimiter(rate_config)

            # Initialize connection manager
            joplin_config = self.config.get("joplin", {})
            self.connection_manager = ConnectionManager(joplin_config)

            # Get Joplin client
            self.joplin_client = await self.connection_manager.get_client()

            # Initialize search service
            self.search_service = SearchService(self.joplin_client)

            # Initialize health checker
            self.health_checker = HealthChecker(
                connection_manager=self.connection_manager,
                rate_limiter=self.rate_limiter,
            )

            # Set global references for tools
            global _global_joplin_client, _global_search_service
            _global_joplin_client = self.joplin_client
            _global_search_service = self.search_service

            # Register MCP tools
            await self._register_tools()

            # Test initial connection
            await self.connection_manager.ensure_connected()

            logger.info("Server services initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize server", extra={"error": str(e)})
            raise

    async def _register_tools(self) -> None:
        """Register all MCP tools with the server."""
        tools = [
            search_notes_tool,
            get_note_tool,
            list_notebooks_tool,
            get_notes_in_notebook_tool,
        ]

        for tool in tools:
            # Register tool with MCP server
            @self.server.call_tool()
            async def handle_tool_call(
                name: str, arguments: dict[str, Any]
            ) -> list[types.TextContent]:
                """Handle MCP tool calls."""
                try:
                    logger.info(
                        "Handling tool call",
                        extra={"tool_name": name, "arguments": arguments},
                    )

                    # Find matching tool
                    matching_tool = None
                    for registered_tool in tools:
                        if registered_tool.name == name:
                            matching_tool = registered_tool
                            break

                    if not matching_tool:
                        raise ValueError(f"Unknown tool: {name}")

                    # Check rate limits
                    if self.rate_limiter and not await self.rate_limiter.acquire():
                        raise Exception("Rate limit exceeded - too many requests")

                    # Ensure connection
                    if self.connection_manager:
                        await self.connection_manager.ensure_connected()

                    # Execute tool
                    result = await matching_tool.execute(arguments)

                    logger.info(
                        "Tool call completed successfully", extra={"tool_name": name}
                    )

                    return result

                except Exception as e:
                    # Use error handler for consistent error responses
                    return ErrorHandler.handle_tool_error(name, e)

            logger.info("Registered MCP tool", extra={"tool_name": tool.name})

    async def list_tools(self) -> list[types.Tool]:
        """List available MCP tools."""
        tools = [
            types.Tool(
                name=search_notes_tool.name,
                description=search_notes_tool.description,
                inputSchema=search_notes_tool.input_schema,
            ),
            types.Tool(
                name=get_note_tool.name,
                description=get_note_tool.description,
                inputSchema=get_note_tool.input_schema,
            ),
            types.Tool(
                name=list_notebooks_tool.name,
                description=list_notebooks_tool.description,
                inputSchema=list_notebooks_tool.input_schema,
            ),
            types.Tool(
                name=get_notes_in_notebook_tool.name,
                description=get_notes_in_notebook_tool.description,
                inputSchema=get_notes_in_notebook_tool.input_schema,
            ),
        ]

        logger.info("Listed available tools", extra={"tool_count": len(tools)})
        return tools

    async def get_server_info(self) -> dict[str, Any]:
        """Get server information and status."""
        info = {
            "name": "joplin-mcp-server",
            "version": "0.1.0",
            "tools_count": 4,
            "connection_status": None,
            "rate_limiter_status": None,
        }

        # Get connection status
        if self.connection_manager:
            info[
                "connection_status"
            ] = await self.connection_manager.get_connection_status()

        # Get rate limiter status
        if self.rate_limiter:
            info["rate_limiter_status"] = await self.rate_limiter.get_status()

        return info

    async def health_check(self) -> dict[str, Any]:
        """Perform comprehensive health check."""
        if self.health_checker:
            return await self.health_checker.check_health()
        else:
            return {
                "status": "unknown",
                "message": "Health checker not initialized",
                "timestamp": time.time(),
            }

    async def shutdown(self) -> None:
        """Shutdown server and cleanup resources."""
        try:
            logger.info("Shutting down server")

            if self.connection_manager:
                await self.connection_manager.disconnect()

            if self.joplin_client:
                await self.joplin_client.close()

            logger.info("Server shutdown complete")

        except Exception as e:
            logger.error("Error during shutdown", extra={"error": str(e)})

    def get_mcp_server(self) -> Server:
        """Get the underlying MCP server instance."""
        return self.server


async def create_mcp_server(config: dict[str, Any]) -> JoplinMCPServer:
    """Create and initialize Joplin MCP server."""
    server = JoplinMCPServer(config)
    await server.initialize()
    return server
