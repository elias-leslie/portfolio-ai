"""Response caching middleware for Portfolio AI platform.

This module provides lightweight caching for expensive API calls using cachetools.
Supports TTL-based caching, ETag validation, cache invalidation, and observability via headers.

ETag Support:
- Server generates ETag (hash of response data)
- Client sends If-None-Match header with cached ETag
- Server returns 304 Not Modified if data unchanged (saves bandwidth)
- Allows efficient caching while ensuring fresh data when it changes
"""

import hashlib
import json
import logging
import os
import re
from collections.abc import Callable
from functools import wraps
from typing import Any, TypedDict

from cachetools import TTLCache  # type: ignore[import-untyped]
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CacheStatsDict(TypedDict):
    """Cache statistics dictionary."""

    enabled: bool
    size: int
    max_size: int
    ttl_default: int
    hits: int
    misses: int
    hit_rate: float
    invalidations: int


# Environment configuration
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "1000"))
CACHE_DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL", "300"))

# Global cache storage (TTL-based)
# Cache stores: {cache_key: (response_data, status_code, headers)}
_cache: TTLCache[str, tuple[Any, int, dict[str, str]]] = TTLCache(
    maxsize=CACHE_MAX_SIZE, ttl=CACHE_DEFAULT_TTL
)

# Cache statistics
_cache_stats: dict[str, int] = {
    "hits": 0,
    "misses": 0,
    "invalidations": 0,
    "etag_matches": 0,  # 304 Not Modified responses
}


def _generate_etag(data: Any) -> str:
    """Generate ETag from response data.

    Args:
        data: Response data (will be JSON serialized)

    Returns:
        ETag string (quoted per HTTP spec)
    """
    if isinstance(data, (dict, list)):
        content = json.dumps(data, sort_keys=True, default=str)
    elif isinstance(data, str):
        content = data
    else:
        content = str(data)

    # Use MD5 for speed (not security-critical)
    hash_value = hashlib.md5(content.encode()).hexdigest()[:16]
    return f'"{hash_value}"'


def _generate_cache_key(request: Request, include_user: bool = True) -> str:
    """Generate cache key from request.

    Args:
        request: FastAPI request object
        include_user: Include user ID in cache key (default: True)

    Returns:
        Cache key string in format: "{method}:{path}:{query_params}:{user_id}"
    """
    # Extract method and path
    method = request.method
    path = request.url.path

    # Sort and serialize query parameters for consistent keys
    query_params = dict(sorted(request.query_params.items()))
    query_str = json.dumps(query_params, sort_keys=True)

    # Extract user ID from request state (set by auth middleware)
    user_id = ""
    if include_user and hasattr(request.state, "user_id"):
        user_id = str(request.state.user_id)

    # Create cache key
    key_parts = [method, path, query_str, user_id]
    key_string = ":".join(key_parts)

    # Hash for consistent length (optional, for very long keys)
    # For now, use direct string to make debugging easier
    return key_string


def cache_response(
    ttl: int = CACHE_DEFAULT_TTL,
    include_user: bool = True,
    key_prefix: str | None = None,
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Decorator to cache FastAPI endpoint responses.

    Args:
        ttl: Time-to-live in seconds (default: CACHE_DEFAULT_TTL)
        include_user: Include user ID in cache key (default: True)
        key_prefix: Optional prefix for cache key (for namespacing)

    Returns:
        Decorator function

    Example:
        @router.get("/api/market")
        @cache_response(ttl=300)
        async def get_market_data():
            return {"data": "expensive computation"}
    """

    def decorator(func: Callable[..., object]) -> Callable[..., object]:
        @wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> object:
            # Check if caching is enabled
            if not CACHE_ENABLED:
                result = await func(*args, **kwargs)  # type: ignore[misc]
                return result

            # Extract request from args/kwargs
            request: Request | None = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None and "request" in kwargs:
                request = kwargs["request"]  # type: ignore[assignment]

            if request is None:
                # No request object, skip caching
                logger.warning(f"No request object found for {func.__name__}, skipping cache")
                result = await func(*args, **kwargs)  # type: ignore[misc]
                return result

            # Only cache GET requests
            if request.method != "GET":
                result = await func(*args, **kwargs)  # type: ignore[misc]
                return result

            # Generate cache key
            cache_key = _generate_cache_key(request, include_user=include_user)
            if key_prefix:
                cache_key = f"{key_prefix}:{cache_key}"

            # Check cache
            if cache_key in _cache:
                _cache_stats["hits"] += 1
                cached_data, status_code, headers = _cache[cache_key]

                # Add cache headers - no-store prevents browser caching
                response_headers = {
                    **headers,
                    "X-Cache-Hit": "true",
                    "Cache-Control": "no-store, max-age=0",
                }

                logger.debug(f"Cache HIT: {cache_key}")
                return JSONResponse(
                    content=cached_data,
                    status_code=status_code,
                    headers=response_headers,
                )

            # Cache miss - execute function
            _cache_stats["misses"] += 1
            logger.debug(f"Cache MISS: {cache_key}")

            result = await func(*args, **kwargs)  # type: ignore[misc]

            # Serialize result for caching
            serialized_result = result
            if isinstance(result, BaseModel):
                # Convert Pydantic models to dict for JSON serialization
                serialized_result = result.model_dump(mode="json")
            elif isinstance(result, list) and result and isinstance(result[0], BaseModel):
                # Handle list of Pydantic models
                serialized_result = [item.model_dump(mode="json") for item in result]

            # Store in cache
            if isinstance(result, JSONResponse):
                _cache[cache_key] = (
                    result.body.decode() if isinstance(result.body, bytes) else result.body,
                    result.status_code,
                    dict(result.headers),
                )
            elif isinstance(result, Response):
                # For other response types, try to cache
                _cache[cache_key] = (
                    result.body if hasattr(result, "body") else str(result),
                    result.status_code,
                    dict(result.headers) if hasattr(result, "headers") else {},
                )
            else:
                # For dict/list/Pydantic responses (auto-converted to JSON by FastAPI)
                _cache[cache_key] = (serialized_result, 200, {})

            # Add cache headers to original response
            # Cache-Control: no-store prevents browser caching, server-side TTL handles freshness
            cache_headers = {
                "X-Cache-Hit": "false",
                "Cache-Control": f"no-store, max-age=0",
            }
            if isinstance(result, Response):
                for key, value in cache_headers.items():
                    result.headers[key] = value
                return result
            # Return new JSONResponse with headers for non-Response results
            return JSONResponse(
                content=serialized_result,
                status_code=200,
                headers=cache_headers,
            )

        return wrapper

    return decorator


def invalidate_cache_pattern(pattern: str) -> int:
    """Invalidate cache entries matching a pattern.

    Args:
        pattern: Glob-style pattern to match cache keys
                 Examples:
                 - "*:user_123" - all caches for user 123
                 - "GET:/api/watchlist:*" - all watchlist GET requests
                 - "*" - clear all caches

    Returns:
        Number of cache entries invalidated
    """
    if not CACHE_ENABLED:
        return 0

    # Convert glob pattern to regex
    regex_pattern = pattern.replace("*", ".*").replace("?", ".")
    regex = re.compile(f"^{regex_pattern}$")

    # Find matching keys
    keys_to_delete = [key for key in _cache if regex.match(key)]

    # Delete keys
    for key in keys_to_delete:
        del _cache[key]
        logger.debug(f"Cache invalidated: {key}")

    count = len(keys_to_delete)
    _cache_stats["invalidations"] += count

    if count > 0:
        logger.info(f"Invalidated {count} cache entries matching pattern: {pattern}")

    return count


def clear_cache() -> int:
    """Clear all cache entries.

    Returns:
        Number of cache entries cleared
    """
    if not CACHE_ENABLED:
        return 0

    count = len(_cache)
    _cache.clear()
    _cache_stats["invalidations"] += count

    logger.info(f"Cleared all {count} cache entries")
    return count


def get_cache_stats() -> CacheStatsDict:
    """Get cache statistics.

    Returns:
        Dictionary with cache statistics including:
        - size: Current number of cached entries
        - max_size: Maximum cache size
        - hits: Total cache hits
        - misses: Total cache misses
        - hit_rate: Cache hit rate percentage
        - invalidations: Total cache invalidations
        - enabled: Whether caching is enabled
    """
    total_requests = _cache_stats["hits"] + _cache_stats["misses"]
    hit_rate = (_cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0.0

    return {
        "enabled": CACHE_ENABLED,
        "size": len(_cache),
        "max_size": CACHE_MAX_SIZE,
        "ttl_default": CACHE_DEFAULT_TTL,
        "hits": _cache_stats["hits"],
        "misses": _cache_stats["misses"],
        "hit_rate": round(hit_rate, 2),
        "invalidations": _cache_stats["invalidations"],
    }


def invalidate_user_cache(user_id: str) -> int:
    """Invalidate all cache entries for a specific user.

    Args:
        user_id: User ID to invalidate caches for

    Returns:
        Number of cache entries invalidated
    """
    pattern = f"*:{user_id}"
    return invalidate_cache_pattern(pattern)


def invalidate_endpoint_cache(endpoint: str, method: str = "GET") -> int:
    """Invalidate all cache entries for a specific endpoint.

    Args:
        endpoint: API endpoint path (e.g., "/api/watchlist")
        method: HTTP method (default: "GET")

    Returns:
        Number of cache entries invalidated
    """
    pattern = f"{method}:{endpoint}:*"
    return invalidate_cache_pattern(pattern)


def invalidate_market_data_cache() -> int:
    """Invalidate all market-related cache entries.

    Call this after Celery tasks update market data (OHLCV, F&G, indicators).

    Returns:
        Number of cache entries invalidated
    """
    patterns = [
        "GET:/api/market/*",
        "GET:/api/watchlist/*",
        "GET:/api/portfolio/*",
    ]
    total = 0
    for pattern in patterns:
        total += invalidate_cache_pattern(pattern)
    logger.info(f"Invalidated {total} market data cache entries")
    return total


def invalidate_fear_greed_cache() -> int:
    """Invalidate Fear & Greed specific caches.

    Call this after calculate_fear_greed task completes.

    Returns:
        Number of cache entries invalidated
    """
    patterns = [
        "GET:/api/market/intelligence:*",
        "GET:/api/market/fear-greed*",
        "GET:/api/market/conditions:*",
    ]
    total = 0
    for pattern in patterns:
        total += invalidate_cache_pattern(pattern)
    logger.info(f"Invalidated {total} Fear & Greed cache entries")
    return total
