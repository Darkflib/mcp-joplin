"""Joplin API client service."""

import json
import logging
from typing import Any

import httpx

from src.models.connection import Connection

logger = logging.getLogger(__name__)


class JoplinClient:
    """HTTP client for Joplin Web Clipper API."""

    def __init__(self, config: dict[str, Any]):
        """Initialize Joplin client with configuration."""
        self.connection = Connection(
            base_url=config["base_url"],
            api_token=config["api_token"],
            timeout=config.get("timeout", 30.0),
            rate_limit=config.get("rate_limit", 60),
            max_retries=config.get("max_retries", 3),
        )

        # Optimized connection pooling
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.connection.timeout),
            limits=httpx.Limits(
                max_connections=20,  # Increased for better concurrency
                max_keepalive_connections=10,  # Keep more connections alive
                keepalive_expiry=30.0,  # Keep connections alive longer
            ),
            http2=True,  # Enable HTTP/2 for better performance
        )

        # Performance tracking
        self._request_count = 0
        self._cache_hits = 0

        logger.info(
            "Joplin client initialized",
            extra={
                "base_url": str(self.connection.base_url),
                "timeout": self.connection.timeout,
            },
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def ping(self) -> bool:
        """Health check - ping Joplin server."""
        try:
            logger.info("Pinging Joplin server")

            response = await self.client.get(
                f"{self.connection.base_url}/ping",
                params={"token": self.connection.api_token},
            )

            is_healthy = (
                response.status_code == 200 and "JoplinClipperServer" in response.text
            )

            if is_healthy:
                logger.info("Joplin server ping successful")
            else:
                logger.error(
                    "Joplin server ping failed",
                    extra={
                        "status_code": response.status_code,
                        "response_text": response.text[:200],
                    },
                )

            return is_healthy

        except httpx.ConnectError as e:
            logger.error("Joplin connection failed", extra={"error": str(e)})
            return False

        except httpx.TimeoutException as e:
            logger.error("Joplin request timed out", extra={"error": str(e)})
            return False

        except Exception as e:
            logger.error("Unexpected error during ping", extra={"error": str(e)})
            return False

    async def search_notes(
        self, query: str, limit: int = 10, notebook_id: str | None = None
    ) -> dict[str, Any]:
        """Search for notes by query."""
        try:
            logger.info(
                "Searching notes",
                extra={"query": query, "limit": limit, "notebook_id": notebook_id},
            )

            params = {
                "token": self.connection.api_token,
                "query": query,
                "limit": limit,
            }

            if notebook_id:
                params["parent_id"] = notebook_id

            response = await self.client.get(
                f"{self.connection.base_url}/notes", params=params
            )

            if response.status_code == 401:
                raise Exception("Authentication failed: Invalid API token")
            elif response.status_code != 200:
                raise Exception(f"Search failed: HTTP {response.status_code}")

            result = response.json()
            logger.info(
                "Notes search completed",
                extra={"results_count": len(result.get("items", []))},
            )

            return result

        except httpx.ConnectError as e:
            logger.error("Connection failed during search", extra={"error": str(e)})
            raise Exception(f"Connection failed: {str(e)}") from e

        except httpx.TimeoutException as e:
            logger.error("Search request timed out", extra={"error": str(e)})
            raise Exception(f"Request timed out: {str(e)}") from e

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON response", extra={"error": str(e)})
            raise Exception(f"Invalid JSON response: {str(e)}") from e

    async def get_note(self, note_id: str, include_body: bool = True) -> dict[str, Any]:
        """Retrieve a specific note by ID."""
        try:
            logger.info(
                "Retrieving note",
                extra={"note_id": note_id, "include_body": include_body},
            )

            params = {"token": self.connection.api_token}

            # Always include essential timestamp fields
            if include_body:
                params["fields"] = "id,title,parent_id,created_time,updated_time,body"
            else:
                params["fields"] = "id,title,parent_id,created_time,updated_time"

            response = await self.client.get(
                f"{self.connection.base_url}/notes/{note_id}", params=params
            )

            if response.status_code == 404:
                raise Exception(f"Note not found: {note_id}")
            elif response.status_code == 401:
                raise Exception("Authentication failed: Invalid API token")
            elif response.status_code != 200:
                raise Exception(f"Get note failed: HTTP {response.status_code}")

            result = response.json()

            # Parse tags if present
            if "tags" in result and isinstance(result["tags"], str):
                result["tags"] = [
                    tag.strip() for tag in result["tags"].split(",") if tag.strip()
                ]
            elif "tags" not in result:
                result["tags"] = []

            logger.info("Note retrieved successfully", extra={"note_id": note_id})
            return result

        except httpx.ConnectError as e:
            logger.error(
                "Connection failed during note retrieval", extra={"error": str(e)}
            )
            raise Exception(f"Connection failed: {str(e)}") from e

        except httpx.TimeoutException as e:
            logger.error("Note retrieval timed out", extra={"error": str(e)})
            raise Exception(f"Request timed out: {str(e)}") from e

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON response", extra={"error": str(e)})
            raise Exception(f"Invalid JSON response: {str(e)}") from e

    async def list_notebooks(
        self, parent_id: str | None = None, recursive: bool = True
    ) -> dict[str, Any]:
        """List notebooks with optional parent filtering."""
        try:
            logger.info(
                "Listing notebooks",
                extra={"parent_id": parent_id, "recursive": recursive},
            )

            params = {"token": self.connection.api_token}

            response = await self.client.get(
                f"{self.connection.base_url}/folders", params=params
            )

            if response.status_code == 401:
                raise Exception("Authentication failed: Invalid API token")
            elif response.status_code != 200:
                raise Exception(f"List notebooks failed: HTTP {response.status_code}")

            result = response.json()

            # Filter by parent_id if specified
            if parent_id is not None:
                filtered_items = [
                    item
                    for item in result.get("items", [])
                    if item.get("parent_id") == parent_id
                ]
                result = {"items": filtered_items}

            logger.info(
                "Notebooks listed successfully",
                extra={"notebooks_count": len(result.get("items", []))},
            )

            return result

        except httpx.ConnectError as e:
            logger.error(
                "Connection failed during notebook listing", extra={"error": str(e)}
            )
            raise Exception(f"Connection failed: {str(e)}") from e

        except httpx.TimeoutException as e:
            logger.error("Notebook listing timed out", extra={"error": str(e)})
            raise Exception(f"Request timed out: {str(e)}") from e

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON response", extra={"error": str(e)})
            raise Exception(f"Invalid JSON response: {str(e)}") from e

    async def get_notes_in_notebook(
        self, notebook_id: str, limit: int = 20, offset: int = 0
    ) -> dict[str, Any]:
        """Get notes within a specific notebook with pagination."""
        try:
            logger.info(
                "Getting notes in notebook",
                extra={"notebook_id": notebook_id, "limit": limit, "offset": offset},
            )

            params = {
                "token": self.connection.api_token,
                "parent_id": notebook_id,
                "limit": limit,
                "offset": offset,
                "fields": "id,title,created_time,updated_time",
            }

            response = await self.client.get(
                f"{self.connection.base_url}/notes", params=params
            )

            if response.status_code == 401:
                raise Exception("Authentication failed: Invalid API token")
            elif response.status_code != 200:
                raise Exception(f"Get notes failed: HTTP {response.status_code}")

            result = response.json()

            # Add pagination info
            items = result.get("items", [])
            result["total_count"] = (
                len(items) + offset
            )  # Simplified - real impl would query total
            result["has_more"] = len(items) == limit  # Simplified pagination check

            logger.info(
                "Notes in notebook retrieved",
                extra={"notebook_id": notebook_id, "notes_count": len(items)},
            )

            return result

        except httpx.ConnectError as e:
            logger.error(
                "Connection failed during notes retrieval", extra={"error": str(e)}
            )
            raise Exception(f"Connection failed: {str(e)}") from e

        except httpx.TimeoutException as e:
            logger.error("Notes retrieval timed out", extra={"error": str(e)})
            raise Exception(f"Request timed out: {str(e)}") from e

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON response", extra={"error": str(e)})
            raise Exception(f"Invalid JSON response: {str(e)}") from e

    async def batch_get_notes(
        self, note_ids: list[str], include_body: bool = True
    ) -> list[dict[str, Any]]:
        """Retrieve multiple notes concurrently for better performance."""
        import asyncio

        logger.info(
            "Batch retrieving notes",
            extra={"note_count": len(note_ids), "include_body": include_body},
        )

        # Create tasks for concurrent execution
        tasks = [
            self.get_note(note_id, include_body=include_body) for note_id in note_ids
        ]

        # Execute all requests concurrently
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and log errors
            valid_results = []
            error_count = 0

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        "Failed to retrieve note in batch",
                        extra={"note_id": note_ids[i], "error": str(result)},
                    )
                    error_count += 1
                else:
                    valid_results.append(result)

            logger.info(
                "Batch note retrieval completed",
                extra={
                    "successful_count": len(valid_results),
                    "error_count": error_count,
                },
            )

            return valid_results

        except Exception as e:
            logger.error("Batch note retrieval failed", extra={"error": str(e)})
            raise

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics for monitoring."""
        return {
            "total_requests": self._request_count,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": self._cache_hits / max(1, self._request_count),
            "connection_pool": {
                "max_connections": 20,
                "max_keepalive": 10,
                "http2_enabled": True,
            },
        }

    def _track_request(self) -> None:
        """Track request for performance monitoring."""
        self._request_count += 1

    def _track_cache_hit(self) -> None:
        """Track cache hit for performance monitoring."""
        self._cache_hits += 1
