#!/usr/bin/env python3
"""
MCP Server entry point for Joplin integration.

This module provides a standalone MCP server that can be used with MCP clients
like Claude Desktop or other MCP-compatible applications.

Usage:
    python mcp_server.py [--config-file config.json]

Or install and run:
    pip install -e .
    python -m mcp_server
"""

import argparse
import asyncio
import logging
import sys

from mcp.server.stdio import stdio_server

from src.config import load_config
from src.logging_config import setup_logging
from src.server import create_mcp_server


async def main():
    """Main entry point for the MCP server."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Joplin MCP Server - Provides MCP tools for querying Joplin"
    )
    parser.add_argument(
        "--config-file",
        type=str,
        default="config.json",
        help="Path to JSON configuration file (default: config.json)",
    )

    args = parser.parse_args()

    try:
        # Load configuration
        config_manager = load_config(args.config_file)
        config = config_manager.get_config()

        # Setup logging
        logging_config = config.get("logging", {})
        setup_logging(
            level=logging_config.get("level", "INFO"),
            format_type=logging_config.get("format", "json"),
        )

        logger = logging.getLogger(__name__)
        logger.info(
            "Starting Joplin MCP Server",
            extra={"version": "0.1.0", "config_file": args.config_file},
        )

        # Create and initialize the Joplin MCP server
        joplin_server = await create_mcp_server(config)

        # Get the underlying MCP server instance
        mcp_server = joplin_server.get_mcp_server()

        # Register server info handler
        @mcp_server.list_tools()
        async def list_tools() -> list:
            """List available MCP tools."""
            return await joplin_server.list_tools()

        # Register tool call handler
        @mcp_server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list:
            """Handle tool calls."""
            # Find the appropriate tool and execute it
            tools_map = {
                "search_notes": search_notes_tool,
                "get_note": get_note_tool,
                "list_notebooks": list_notebooks_tool,
                "get_notes_in_notebook": get_notes_in_notebook_tool,
                "update_note": update_note_tool,
                "create_note": create_note_tool,
            }

            if name not in tools_map:
                raise ValueError(f"Unknown tool: {name}")

            tool = tools_map[name]

            try:
                # Check rate limits
                if (
                    joplin_server.rate_limiter
                    and not await joplin_server.rate_limiter.acquire()
                ):
                    raise Exception("Rate limit exceeded - too many requests")

                # Ensure connection
                if joplin_server.connection_manager:
                    await joplin_server.connection_manager.ensure_connected()

                # Execute tool
                return await tool.execute(arguments)

            except Exception as e:
                from src.middleware.error_handler import ErrorHandler

                return ErrorHandler.handle_tool_error(name, e)

        # Import tools for the handlers
        from src.tools.create_note import create_note_tool
        from src.tools.get_note import get_note_tool
        from src.tools.get_notes_in_notebook import get_notes_in_notebook_tool
        from src.tools.list_notebooks import list_notebooks_tool
        from src.tools.search_notes import search_notes_tool
        from src.tools.update_note import update_note_tool

        logger.info("MCP server ready, starting stdio transport")

        # Run the server with stdio transport
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(
                read_stream, write_stream, mcp_server.create_initialization_options()
            )

    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
