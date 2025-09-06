"""Connection manager with retry logic."""

import asyncio
import logging
from typing import Any

from src.models.connection import ConnectionState
from src.services.joplin_client import JoplinClient

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages connection state and retry logic for Joplin client."""

    def __init__(self, config: dict[str, Any]):
        """Initialize connection manager."""
        self.client = JoplinClient(config)
        self.config = config
        self.retry_delay = config.get("retry_delay", 1.0)
        self._lock = asyncio.Lock()

        logger.info(
            "Connection manager initialized",
            extra={
                "base_url": config["base_url"],
                "max_retries": config.get("max_retries", 3),
                "retry_delay": self.retry_delay,
            },
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.close()

    async def ensure_connected(self) -> bool:
        """Ensure connection is established, with retry logic."""
        async with self._lock:
            connection = self.client.connection

            # If already connected, verify with ping
            if connection.is_connected == ConnectionState.CONNECTED:
                if await self.client.ping():
                    return True
                else:
                    connection.transition_to(ConnectionState.DISCONNECTED)

            # Attempt to connect with retries
            return await self._connect_with_retry()

    async def _connect_with_retry(self) -> bool:
        """Attempt connection with retry logic."""
        connection = self.client.connection
        connection.reset_retry()

        while connection.can_retry():
            try:
                logger.info(
                    "Attempting connection",
                    extra={
                        "attempt": connection.retry_count + 1,
                        "max_retries": connection.max_retries,
                    },
                )

                # Only transition to CONNECTING if not already connecting
                if connection.is_connected != ConnectionState.CONNECTING:
                    connection.transition_to(ConnectionState.CONNECTING)

                # Attempt ping
                if await self.client.ping():
                    connection.transition_to(ConnectionState.CONNECTED)
                    logger.info("Connection successful")
                    return True

                # Connection failed, transition to error state and increment retry
                connection.transition_to(ConnectionState.ERROR, "Connection failed")
                connection.increment_retry()

                if connection.can_retry():
                    logger.warning(
                        "Connection failed, retrying",
                        extra={
                            "retry_count": connection.retry_count,
                            "retry_delay": self.retry_delay,
                        },
                    )
                    # Transition back to disconnected before retry
                    connection.transition_to(ConnectionState.DISCONNECTED)
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(
                        "Connection failed after all retries",
                        extra={"total_attempts": connection.retry_count},
                    )
                    connection.transition_to(
                        ConnectionState.ERROR,
                        f"Failed after {connection.retry_count} attempts",
                    )

            except Exception as e:
                connection.increment_retry()
                error_msg = (
                    f"Connection attempt {connection.retry_count} failed: {str(e)}"
                )

                logger.error(
                    "Connection attempt failed",
                    extra={"attempt": connection.retry_count, "error": str(e)},
                )

                connection.transition_to(ConnectionState.ERROR, error_msg)

                if connection.can_retry():
                    connection.transition_to(ConnectionState.DISCONNECTED)
                    await asyncio.sleep(self.retry_delay)
                else:
                    break

        return False

    async def is_connected(self) -> bool:
        """Check if currently connected."""
        return self.client.connection.is_connected == ConnectionState.CONNECTED

    async def get_connection_status(self) -> dict[str, Any]:
        """Get detailed connection status."""
        return self.client.connection.get_connection_info()

    async def reconnect(self) -> bool:
        """Force reconnection attempt."""
        async with self._lock:
            logger.info("Forcing reconnection")

            # Reset connection state
            self.client.connection.transition_to(ConnectionState.DISCONNECTED)
            self.client.connection.reset_retry()

            return await self._connect_with_retry()

    async def disconnect(self) -> None:
        """Explicitly disconnect."""
        async with self._lock:
            logger.info("Disconnecting from Joplin")
            self.client.connection.transition_to(ConnectionState.DISCONNECTED)
            await self.client.close()

    async def health_check(self) -> dict[str, Any]:
        """Perform comprehensive health check."""
        logger.info("Performing health check")

        health_info = {
            "connected": False,
            "response_time_ms": None,
            "error": None,
            "connection_info": self.client.connection.get_connection_info(),
        }

        try:
            import time

            start_time = time.time()

            is_healthy = await self.client.ping()

            end_time = time.time()
            health_info["response_time_ms"] = round((end_time - start_time) * 1000, 2)
            health_info["connected"] = is_healthy

            if is_healthy:
                logger.info(
                    "Health check passed",
                    extra={"response_time_ms": health_info["response_time_ms"]},
                )
            else:
                health_info["error"] = self.client.connection.last_error
                logger.warning(
                    "Health check failed", extra={"error": health_info["error"]}
                )

        except Exception as e:
            health_info["error"] = str(e)
            logger.error("Health check exception", extra={"error": str(e)})

        return health_info

    async def get_client(self) -> JoplinClient:
        """Get the underlying Joplin client (ensures connection)."""
        await self.ensure_connected()
        return self.client
