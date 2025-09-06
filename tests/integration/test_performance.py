"""Integration tests for rate limiting and performance.

These tests verify performance requirements and rate limiting behavior.
They must fail initially (RED phase) before implementation.
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.services.joplin_client import JoplinClient
from src.services.rate_limiter import RateLimiter


class TestPerformanceIntegration:
    """Test rate limiting and performance integration scenarios."""

    @pytest.mark.asyncio
    async def test_response_time_under_500ms(self) -> None:
        """Test API responses complete within 500ms target."""
        # This will fail until performance optimization is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)

        # Mock fast response
        with patch.object(client, 'search_notes') as mock_search:
            mock_search.return_value = {
                "items": [
                    {"id": "note1", "title": "Test Note", "body": "Content"}
                ]
            }

            start_time = time.time()
            await client.search_notes("test query")
            end_time = time.time()

            response_time = (end_time - start_time) * 1000  # Convert to ms
            assert response_time < 500, f"Response time {response_time}ms exceeded 500ms target"

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_limits(self) -> None:
        """Test rate limiter properly enforces request limits."""
        # This will fail until RateLimiter is implemented
        config = {
            "requests_per_minute": 10,
            "burst_size": 5
        }

        rate_limiter = RateLimiter(config)

        # Make rapid requests
        allowed_count = 0
        denied_count = 0

        for i in range(15):  # More than the limit
            is_allowed = await rate_limiter.acquire()
            if is_allowed:
                allowed_count += 1
            else:
                denied_count += 1

        # Should allow some requests and deny others
        assert allowed_count <= 10  # Respects per-minute limit
        assert denied_count > 0  # Some requests denied
        assert allowed_count + denied_count == 15

    @pytest.mark.asyncio
    async def test_rate_limiter_burst_handling(self) -> None:
        """Test rate limiter allows burst requests within limits."""
        # This will fail until burst handling is implemented
        config = {
            "requests_per_minute": 60,
            "burst_size": 10
        }

        rate_limiter = RateLimiter(config)

        # Make burst of requests
        start_time = time.time()
        results = []

        for i in range(10):  # Within burst limit
            is_allowed = await rate_limiter.acquire()
            results.append(is_allowed)

        end_time = time.time()
        elapsed = end_time - start_time

        # All burst requests should be allowed quickly
        assert all(results), "Not all burst requests were allowed"
        assert elapsed < 1.0, f"Burst requests took {elapsed}s, should be <1s"

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self) -> None:
        """Test server handles 100+ concurrent requests efficiently."""
        # This will fail until concurrent handling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123",
            "max_concurrent": 50
        }

        client = JoplinClient(config)

        # Mock responses for concurrent requests
        with patch.object(client, 'search_notes') as mock_search:
            mock_search.return_value = {"items": []}

            # Launch 100 concurrent requests
            tasks = []
            for i in range(100):
                task = asyncio.create_task(client.search_notes(f"query{i}"))
                tasks.append(task)

            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()

            elapsed = end_time - start_time
            successful = sum(1 for r in results if not isinstance(r, Exception))

            # Should handle most requests successfully within reasonable time
            assert successful >= 90, f"Only {successful}/100 requests succeeded"
            assert elapsed < 10.0, f"Concurrent requests took {elapsed}s, should be <10s"

    @pytest.mark.asyncio
    async def test_memory_usage_under_50mb(self) -> None:
        """Test server memory usage stays under 50MB during operation."""
        # This will fail until memory optimization is implemented
        import os

        import psutil

        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Simulate heavy usage
        with patch.object(client, 'search_notes') as mock_search:
            # Large response to test memory handling
            large_items = []
            for i in range(1000):
                large_items.append({
                    "id": f"note{i:04d}",
                    "title": f"Note {i}",
                    "body": "Content " * 100  # Moderate size content
                })

            mock_search.return_value = {"items": large_items}

            # Process multiple large responses
            for i in range(10):
                result = await client.search_notes(f"query{i}")
                # Simulate processing results
                processed = [item["title"] for item in result["items"]]
                del processed  # Cleanup

            # Check memory usage after processing
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            assert memory_increase < 50, f"Memory increased by {memory_increase}MB, should be <50MB"

    @pytest.mark.asyncio
    async def test_large_note_retrieval_performance(self) -> None:
        """Test retrieval of large notes (>1MB) within performance limits."""
        # This will fail until large content optimization is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)

        # Mock large note (>1MB content)
        large_content = "# Large Document\n" + ("Content line\n" * 50000)
        large_note = {
            "id": "large_note_123",
            "title": "Large Document",
            "body": large_content,
            "parent_id": "notebook1",
            "created_time": 1704067200000,
            "updated_time": 1704067200000
        }

        with patch.object(client, 'get_note') as mock_get:
            mock_get.return_value = large_note

            start_time = time.time()
            result = await client.get_note("large_note_123")
            end_time = time.time()

            elapsed = (end_time - start_time) * 1000  # ms

            # Large note should still be retrieved quickly
            assert elapsed < 2000, f"Large note retrieval took {elapsed}ms, should be <2000ms"
            assert len(result["body"]) > 1000000, "Note content should be >1MB"

    @pytest.mark.asyncio
    async def test_search_pagination_performance(self) -> None:
        """Test search pagination doesn't degrade performance significantly."""
        # This will fail until pagination optimization is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123"
        }

        client = JoplinClient(config)

        # Mock paginated responses
        def create_page(offset, limit):
            items = []
            for i in range(limit):
                items.append({
                    "id": f"note{offset + i:04d}",
                    "title": f"Note {offset + i}",
                    "body": f"Content for note {offset + i}"
                })
            return {"items": items, "has_more": offset + limit < 1000}

        with patch.object(client, 'search_notes') as mock_search:
            # Test multiple pages
            page_times = []

            for page in range(5):  # 5 pages
                offset = page * 20
                mock_search.return_value = create_page(offset, 20)

                start_time = time.time()
                result = await client.search_notes("test", offset=offset, limit=20)
                end_time = time.time()

                page_time = (end_time - start_time) * 1000
                page_times.append(page_time)

                assert len(result["items"]) == 20

            # Page retrieval times should be consistent (no significant degradation)
            avg_time = sum(page_times) / len(page_times)
            max_time = max(page_times)

            assert max_time < avg_time * 2, f"Page time degradation: max={max_time}ms avg={avg_time}ms"
            assert avg_time < 100, f"Average page time {avg_time}ms should be <100ms"

    @pytest.mark.asyncio
    async def test_connection_pooling_efficiency(self) -> None:
        """Test HTTP connection pooling improves performance."""
        # This will fail until connection pooling is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123",
            "connection_pool_size": 10
        }

        client = JoplinClient(config)

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"items": []}
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Make multiple sequential requests
            start_time = time.time()

            for i in range(10):
                await client.search_notes(f"query{i}")

            end_time = time.time()
            elapsed = (end_time - start_time) * 1000

            # Connection reuse should make this faster
            assert elapsed < 1000, f"Sequential requests took {elapsed}ms, should be <1000ms with pooling"

            # Should reuse HTTP client, not create new ones
            assert mock_client_class.call_count <= 1, "Should reuse HTTP client connection"

    @pytest.mark.asyncio
    async def test_caching_improves_repeated_requests(self) -> None:
        """Test caching improves performance for repeated requests."""
        # This will fail until caching is implemented
        config = {
            "base_url": "http://localhost:41184",
            "api_token": "test-token-123",
            "cache_ttl": 300  # 5 minutes
        }

        client = JoplinClient(config)

        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {"items": [{"id": "note1", "title": "Cached Note"}]}

            # First request
            start_time = time.time()
            result1 = await client.search_notes("cached query")
            first_time = (time.time() - start_time) * 1000

            # Second identical request (should be cached)
            start_time = time.time()
            result2 = await client.search_notes("cached query")
            second_time = (time.time() - start_time) * 1000

            # Results should be identical
            assert result1 == result2

            # Second request should be much faster (cached)
            assert second_time < first_time / 2, f"Cached request {second_time}ms not much faster than first {first_time}ms"

            # Should have made only one actual HTTP request
            assert mock_request.call_count == 1, "Should cache and not repeat HTTP request"
