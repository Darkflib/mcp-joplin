"""Search service with relevance scoring and caching."""

import logging
import re
import time
from typing import Any

from src.models.search_result import MatchType, SearchResult, SearchResultItem
from src.services.joplin_client import JoplinClient

logger = logging.getLogger(__name__)


class SearchCache:
    """Simple in-memory cache for search results."""

    def __init__(self, ttl_seconds: int = 300):
        """Initialize cache with TTL (time-to-live) in seconds."""
        self.cache: dict[str, tuple[float, list[SearchResultItem]]] = {}
        self.ttl = ttl_seconds

    def get(self, key: str) -> list[SearchResultItem] | None:
        """Get cached results if still valid."""
        if key not in self.cache:
            return None

        timestamp, results = self.cache[key]
        if time.time() - timestamp > self.ttl:
            # Cache expired
            del self.cache[key]
            return None

        return results

    def set(self, key: str, results: list[SearchResultItem]) -> None:
        """Cache search results."""
        self.cache[key] = (time.time(), results)

    def clear(self) -> None:
        """Clear all cached results."""
        self.cache.clear()

    def cleanup_expired(self) -> None:
        """Remove expired cache entries."""
        current_time = time.time()
        expired_keys = [
            key
            for key, (timestamp, _) in self.cache.items()
            if current_time - timestamp > self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]


class SearchService:
    """Service for searching notes with relevance scoring."""

    def __init__(self, joplin_client: JoplinClient, cache_ttl: int = 300):
        """Initialize search service with Joplin client and caching."""
        self.client = joplin_client
        self.cache = SearchCache(cache_ttl)
        self._last_cleanup = time.time()

    async def search_notes(
        self, query: str, limit: int = 10, notebook_id: str | None = None
    ) -> SearchResult:
        """Search for notes with relevance scoring and caching."""
        try:
            # Periodic cache cleanup
            self._maybe_cleanup_cache()

            # Create cache key
            cache_key = self._create_cache_key(query, limit, notebook_id)

            # Check cache first
            cached_results = self.cache.get(cache_key)
            if cached_results:
                logger.info(
                    "Returning cached search results",
                    extra={
                        "query": query,
                        "cache_key": cache_key,
                        "results_count": len(cached_results),
                    },
                )
                return SearchResult(
                    query=query,
                    items=cached_results,
                    total_count=len(cached_results),
                    execution_time_ms=0.0,  # Cached results
                    has_more=False,
                )

            logger.info(
                "Starting search with scoring",
                extra={"query": query, "limit": limit, "notebook_id": notebook_id},
            )

            # Get raw results from Joplin
            raw_results = await self.client.search_notes(
                query, limit=limit * 2, notebook_id=notebook_id
            )
            items = raw_results.get("items", [])

            if not items:
                logger.info("No search results found")
                empty_result = SearchResult(
                    query=query,
                    items=[],
                    total_count=0,
                    execution_time_ms=0.0,
                    has_more=False,
                )
                return empty_result

            # Score and rank results
            scored_results = []
            for item in items:
                relevance_score = self._calculate_relevance(query, item)
                snippet = self._generate_snippet(query, item)

                result_item = SearchResultItem(
                    note_id=item["id"],
                    title=item["title"],
                    snippet=snippet,
                    relevance_score=relevance_score,
                )
                scored_results.append(result_item)

            # Sort by relevance score (highest first) and limit results
            scored_results.sort(key=lambda x: x.relevance_score, reverse=True)
            final_results = scored_results[:limit]

            # Cache the results
            self.cache.set(cache_key, final_results)

            logger.info(
                "Search completed with scoring",
                extra={
                    "results_count": len(final_results),
                    "top_score": final_results[0].relevance_score
                    if final_results
                    else 0,
                    "cached": True,
                },
            )

            return SearchResult(
                query=query,
                items=final_results,
                total_count=len(final_results),
                execution_time_ms=0.0,
                has_more=len(items) > limit,
            )

        except Exception as e:
            logger.error("Search failed", extra={"error": str(e), "query": query})
            raise

    def _calculate_relevance(self, query: str, item: dict[str, Any]) -> float:
        """Calculate relevance score for a search result."""
        query_lower = query.lower().strip()
        title_lower = item.get("title", "").lower()
        body_lower = item.get("body", "").lower()

        score = 0.0

        # Title matches get highest weight
        if query_lower in title_lower:
            score += 1.0
            # Exact title match gets bonus
            if query_lower == title_lower:
                score += 0.5
            # Title starting with query gets bonus
            elif title_lower.startswith(query_lower):
                score += 0.3

        # Body content matches get medium weight
        body_matches = len(re.findall(re.escape(query_lower), body_lower))
        if body_matches > 0:
            # Diminishing returns for multiple matches
            score += min(0.5, body_matches * 0.1)

        # Word boundary matches get bonus (whole word vs partial)
        title_word_match = bool(
            re.search(r"\b" + re.escape(query_lower) + r"\b", title_lower)
        )
        body_word_match = bool(
            re.search(r"\b" + re.escape(query_lower) + r"\b", body_lower)
        )

        if title_word_match:
            score += 0.2
        if body_word_match:
            score += 0.1

        # Tag matches (if available)
        tags = item.get("tags", [])
        if isinstance(tags, list):
            tag_matches = sum(1 for tag in tags if query_lower in tag.lower())
            if tag_matches > 0:
                score += min(0.3, tag_matches * 0.1)

        # Normalize score to 0.0-1.0 range
        # Max possible score is roughly 2.0, so divide by 2
        normalized_score = min(1.0, score / 2.0)

        # Ensure minimum score for any match
        return max(0.1, normalized_score)

    def _determine_match_type(self, query: str, item: dict[str, Any]) -> MatchType:
        """Determine where the match occurred."""
        query_lower = query.lower().strip()
        title_lower = item.get("title", "").lower()
        body_lower = item.get("body", "").lower()
        tags = item.get("tags", [])

        title_match = query_lower in title_lower
        body_match = query_lower in body_lower
        tag_match = False

        if isinstance(tags, list):
            tag_match = any(query_lower in tag.lower() for tag in tags)

        # Determine primary match type
        match_count = sum([title_match, body_match, tag_match])

        if match_count > 1:
            return MatchType.MIXED
        elif title_match:
            return MatchType.TITLE
        elif body_match:
            return MatchType.BODY
        elif tag_match:
            return MatchType.TAGS
        else:
            # Fallback for partial matches
            return MatchType.MIXED

    def _generate_snippet(self, query: str, item: dict[str, Any]) -> str:
        """Generate content snippet showing match context."""
        title = item.get("title", "")
        body = item.get("body", "")
        query_lower = query.lower().strip()

        # If query matches title, use title as snippet
        if query_lower in title.lower():
            return title[:200]

        # If no body content, use title
        if not body:
            return title[:200]

        # Find first occurrence of query in body
        body_lower = body.lower()
        match_pos = body_lower.find(query_lower)

        if match_pos == -1:
            # No exact match, return beginning of body or title
            content = body if len(body) > len(title) else title
            return content[:200]

        # Generate snippet around match
        snippet_length = 200
        start_pos = max(0, match_pos - 50)  # Show some context before match
        end_pos = min(len(body), start_pos + snippet_length)

        # Adjust start if we're near the end
        if end_pos - start_pos < snippet_length:
            start_pos = max(0, end_pos - snippet_length)

        snippet = body[start_pos:end_pos]

        # Add ellipsis if truncated
        if start_pos > 0:
            snippet = "..." + snippet
        if end_pos < len(body):
            snippet = snippet + "..."

        # Clean up snippet (remove excessive whitespace)
        snippet = " ".join(snippet.split())

        return snippet

    def _create_cache_key(self, query: str, limit: int, notebook_id: str | None) -> str:
        """Create cache key for search parameters."""
        return f"{query.strip().lower()}:{limit}:{notebook_id or 'all'}"

    def _maybe_cleanup_cache(self) -> None:
        """Periodically cleanup expired cache entries."""
        current_time = time.time()
        if current_time - self._last_cleanup > 300:  # Cleanup every 5 minutes
            self.cache.cleanup_expired()
            self._last_cleanup = current_time

    def clear_cache(self) -> None:
        """Clear all cached search results."""
        self.cache.clear()
        logger.info("Search cache cleared")

    def _sanitize_query(self, query: str) -> str:
        """Sanitize search query for safe processing."""
        if not query:
            return ""

        # Remove excessive whitespace
        query = " ".join(query.split())

        # Limit query length
        if len(query) > 200:
            query = query[:200]

        return query
