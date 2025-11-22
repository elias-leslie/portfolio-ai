"""Middleware package for Portfolio AI platform.

This package contains middleware components for request/response processing,
including caching, logging, and other cross-cutting concerns.
"""

from app.middleware.cache import (
    cache_response,
    clear_cache,
    get_cache_stats,
    invalidate_cache_pattern,
)

__all__ = [
    "cache_response",
    "clear_cache",
    "get_cache_stats",
    "invalidate_cache_pattern",
]
