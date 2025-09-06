"""CLI entry point with server startup."""

import argparse
import asyncio
import logging
import signal
import sys

from src.config import ConfigurationError, load_config
from src.logging_config import setup_logging
from src.server import create_mcp_server


def create_argument_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Joplin MCP Server - Provides MCP tools for querying Joplin personal knowledge manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --port 3000
  %(prog)s --config-file config.json --port 8080
  %(prog)s --help
  %(prog)s --version

Environment Variables:
  JOPLIN_API_URL       Joplin API endpoint (default: http://localhost:41184)
  JOPLIN_API_TOKEN     Joplin API authentication token (required)
  MCP_SERVER_PORT      MCP server port (default: 3000)
  LOG_LEVEL           Logging level (default: INFO)
        """,
    )

    parser.add_argument(
        "--config-file", type=str, help="Path to JSON configuration file"
    )

    parser.add_argument(
        "--port", type=int, help="Server port (overrides config file and env var)"
    )

    parser.add_argument(
        "--host", type=str, default="localhost", help="Server host (default: localhost)"
    )

    parser.add_argument(
        "--version", action="version", version="joplin-mcp-server 0.1.0"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (overrides config)",
    )

    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )

    return parser


class MCPServerRunner:
    """Manages MCP server lifecycle."""

    def __init__(self, config_file: str | None = None):
        """Initialize server runner."""
        self.config_file = config_file
        self.server = None
        self.config_manager = None
        self.shutdown_event = asyncio.Event()
        self.logger = logging.getLogger(__name__)

    async def run(
        self, host: str, port: int | None = None, log_level: str | None = None
    ) -> None:
        """Run the MCP server."""
        try:
            # Load configuration
            self.config_manager = load_config(self.config_file)
            config = self.config_manager.get_config()

            # Override with command line arguments
            if port:
                config["server"]["port"] = port
            if log_level:
                config["logging"]["level"] = log_level

            # Setup logging
            logging_config = config.get("logging", {})
            setup_logging(
                level=logging_config.get("level", "INFO"),
                format_type=logging_config.get("format", "json"),
            )

            self.logger = logging.getLogger(__name__)
            self.logger.info(
                "Starting Joplin MCP Server",
                extra={
                    "version": "0.1.0",
                    "config_file": self.config_file,
                    "port": config["server"]["port"],
                },
            )

            # Create and initialize server
            self.server = await create_mcp_server(config)

            # Setup signal handlers
            self._setup_signal_handlers()

            # Get server info
            server_info = await self.server.get_server_info()
            # Remove 'name' field to avoid conflict with LogRecord
            safe_server_info = {k: v for k, v in server_info.items() if k != "name"}
            safe_server_info["server_name"] = server_info.get("name")
            self.logger.info("Server initialized", extra=safe_server_info)

            # Perform health check
            health = await self.server.health_check()
            if health["status"] != "healthy":
                self.logger.warning("Server health check failed", extra=health)

            # Start MCP server (this would integrate with actual MCP runtime)
            self.logger.info(
                "MCP server ready",
                extra={
                    "host": host,
                    "port": config["server"]["port"],
                    "tools_available": 4,
                },
            )

            # Keep server running until shutdown signal
            await self.shutdown_event.wait()

        except ConfigurationError as e:
            self.logger.error(f"Configuration error: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Server error: {e}", exc_info=True)
            sys.exit(1)
        finally:
            await self._cleanup()

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}")
            asyncio.create_task(self._shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _shutdown(self) -> None:
        """Initiate graceful shutdown."""
        self.logger.info("Initiating graceful shutdown")
        self.shutdown_event.set()

    async def _cleanup(self) -> None:
        """Cleanup server resources."""
        if self.server:
            self.logger.info("Shutting down server")
            await self.server.shutdown()

        self.logger.info("Server shutdown complete")


def main() -> None:
    """Main entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Create and run server
    runner = MCPServerRunner(config_file=args.config_file)

    try:
        asyncio.run(
            runner.run(host=args.host, port=args.port, log_level=args.log_level)
        )
    except KeyboardInterrupt:
        pass  # Handled gracefully in runner
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
