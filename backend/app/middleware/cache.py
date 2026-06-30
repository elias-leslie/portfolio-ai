"""Response caching middleware for Portfolio AI platform.

Provides lightweight TTL-based caching for expensive API calls using cachetools.
Supports ETag validation, cache invalidation, and observability via headers.

ETag Support:
- Server generates ETag (hash of response data)
- Client sends If-None-Match header with cached ETag
- Server returns 304 Not Modified if data unchanged (saves bandwidth)
"""

import fnmatch
import hashlib
import json
from collections.abc import Callable
from functools import wraps
from time import monotonic
from typing import Any, TypedDict

from cachetools import LRUCache
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import settings
from ..logging_config import get_logger

logger = get_logger(__name__)


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


CACHE_ENABLED = settings.cache_enabled
CACHE_MAX_SIZE = settings.cache_max_size
CACHE_DEFAULT_TTL = settings.cache_default_ttl

_cache: LRUCache[str, tuple[Any, int, dict[str, str], float]] = LRUCache(
    maxsize=CACHE_MAX_SIZE
)

_cache_stats: dict[str, int] = {
    "hits": 0,
    "misses": 0,
    "invalidations": 0,
    "etag_matches": 0,
}

_CACHE_HEADERS_MISS = {"X-Cache-Hit": "false", "Cache-Control": "no-store, max-age=0"}
_CACHE_HEADERS_HIT = {"X-Cache-Hit": "true", "Cache-Control": "no-store, max-age=0"}


def _generate_etag(data: Any) -> str:
    """Generate ETag from response data (quoted per HTTP spec)."""
    if isinstance(data, (dict, list)):
        content = json.dumps(data, sort_keys=True, default=str)
    elif isinstance(data, str):
        content = data
    else:
        content = str(data)
    hash_value = hashlib.md5(content.encode()).hexdigest()[:16]
    return f'"{hash_value}"'


def _generate_cache_key(request: Request, include_user: bool = True) -> str:
    """Generate cache key: '{method}:{path}:{query_params}:{user_id}'."""
    query_str = json.dumps(dict(sorted(request.query_params.items())), sort_keys=True)
    user_id = str(request.state.user_id) if include_user and hasattr(request.state, "user_id") else ""
    return ":".join([request.method, request.url.path, query_str, user_id])


def _serialize_result(result: Any) -> Any:
    """Convert Pydantic models to dicts for JSON serialization."""
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if isinstance(result, list) and result and isinstance(result[0], BaseModel):
        return [item.model_dump(mode="json") for item in result]
    return result


def _store_result_in_cache(cache_key: str, result: Any, serialized: Any, ttl: int) -> None:
    """Store a handler result in the cache."""
    expires_at = monotonic() + ttl
    if isinstance(result, JSONResponse):
        body = result.body.decode() if isinstance(result.body, bytes) else result.body
        _cache[cache_key] = (body, result.status_code, dict(result.headers), expires_at)
    elif isinstance(result, Response):
        body = result.body if hasattr(result, "body") else str(result)
        headers = dict(result.headers) if hasattr(result, "headers") else {}
        _cache[cache_key] = (body, result.status_code, headers, expires_at)
    else:
        _cache[cache_key] = (serialized, 200, {}, expires_at)


def _get_cached_entry(cache_key: str) -> tuple[Any, int, dict[str, str]] | None:
    """Return cached entry if present and unexpired."""
    cached = _cache.get(cache_key)
    if cached is None:
        return None

    cached_data, status_code, headers, expires_at = cached
    if monotonic() >= expires_at:
        del _cache[cache_key]
        logger.debug("cache_expired", cache_key=cache_key)
        return None

    return cached_data, status_code, headers


def _build_cached_response(cache_key: str) -> JSONResponse:
    """Return a JSONResponse from a cache hit."""
    cached_entry = _get_cached_entry(cache_key)
    if cached_entry is None:
        raise KeyError(cache_key)
    cached_data, status_code, headers = cached_entry
    _cache_stats["hits"] += 1
    logger.debug("cache_hit", cache_key=cache_key)
    return JSONResponse(
        content=cached_data,
        status_code=status_code,
        headers={**headers, **_CACHE_HEADERS_HIT},
    )


def _extract_request(args: tuple, kwargs: dict) -> Request | None:
    """Extract the FastAPI Request object from handler args/kwargs."""
    for arg in args:
        if isinstance(arg, Request):
            return arg
    for value in kwargs.values():
        if isinstance(value, Request):
            return value
    return None


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

    Example:
        @router.get("/api/market")
        @cache_response(ttl=300)
        async def get_market_data():
            return {"data": "expensive computation"}
    """

    def decorator(func: Callable[..., object]) -> Callable[..., object]:
        @wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> object:
            if not CACHE_ENABLED:
                return await func(*args, **kwargs)  # type: ignore[misc]

            request = _extract_request(args, kwargs)
            if request is None:
                logger.warning("cache_no_request_object", func_name=func.__name__)
                return await func(*args, **kwargs)  # type: ignore[misc]

            if request.method != "GET":
                return await func(*args, **kwargs)  # type: ignore[misc]

            cache_key = _generate_cache_key(request, include_user=include_user)
            if key_prefix:
                cache_key = f"{key_prefix}:{cache_key}"

            if _get_cached_entry(cache_key) is not None:
                return _build_cached_response(cache_key)

            _cache_stats["misses"] += 1
            logger.debug("cache_miss", cache_key=cache_key)

            result = await func(*args, **kwargs)  # type: ignore[misc]
            serialized = _serialize_result(result)
            _store_result_in_cache(cache_key, result, serialized, ttl)

            if isinstance(result, Response):
                for key, value in _CACHE_HEADERS_MISS.items():
                    result.headers[key] = value
                return result

            return JSONResponse(content=serialized, status_code=200, headers=_CACHE_HEADERS_MISS)

        return wrapper

    return decorator


def invalidate_cache_pattern(pattern: str) -> int:
    """Invalidate cache entries matching a glob-style pattern. Returns count removed."""
    if not CACHE_ENABLED:
        return 0
    keys_to_delete = [key for key in _cache if fnmatch.fnmatchcase(key, pattern)]
    for key in keys_to_delete:
        del _cache[key]
        logger.debug("cache_invalidated", cache_key=key)
    count = len(keys_to_delete)
    _cache_stats["invalidations"] += count
    if count > 0:
        logger.info("cache_entries_invalidated", count=count, pattern=pattern)
    return count


def clear_cache() -> int:
    """Clear all cache entries. Returns count cleared."""
    if not CACHE_ENABLED:
        return 0
    count = len(_cache)
    _cache.clear()
    _cache_stats["invalidations"] += count
    logger.info("cache_cleared", count=count)
    return count


def get_cache_stats() -> CacheStatsDict:
    """Return cache statistics dict."""
    total = _cache_stats["hits"] + _cache_stats["misses"]
    hit_rate = round(_cache_stats["hits"] / total * 100, 2) if total > 0 else 0.0
    return {
        "enabled": CACHE_ENABLED,
        "size": len(_cache),
        "max_size": CACHE_MAX_SIZE,
        "ttl_default": CACHE_DEFAULT_TTL,
        "hits": _cache_stats["hits"],
        "misses": _cache_stats["misses"],
        "hit_rate": hit_rate,
        "invalidations": _cache_stats["invalidations"],
    }


def invalidate_user_cache(user_id: str) -> int:
    """Invalidate all cache entries for a specific user."""
    return invalidate_cache_pattern(f"*:{user_id}")


def invalidate_endpoint_cache(endpoint: str, method: str = "GET") -> int:
    """Invalidate all cache entries for a specific endpoint."""
    variants = {endpoint, endpoint.rstrip("/"), f"{endpoint.rstrip('/')}/"}
    return sum(invalidate_cache_pattern(f"{method}:{v}:*") for v in variants)


def invalidate_market_data_cache() -> int:
    """Invalidate all market-related cache entries."""
    patterns = ["GET:/api/market/*", "GET:/api/watchlist/*", "GET:/api/portfolio/*"]
    total = sum(invalidate_cache_pattern(p) for p in patterns)
    logger.info("market_data_cache_invalidated", count=total)
    return total


def invalidate_fear_greed_cache() -> int:
    """Invalidate Fear & Greed specific caches."""
    patterns = [
        "GET:/api/market/intelligence:*",
        "GET:/api/market/fear-greed*",
        "GET:/api/market/conditions:*",
    ]
    total = sum(invalidate_cache_pattern(p) for p in patterns)
    logger.info("fear_greed_cache_invalidated", count=total)
    return total
