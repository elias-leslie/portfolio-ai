"""API utility functions."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

import polars as pl
from fastapi import HTTPException

from app.logging_config import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def handle_api_errors(operation_name: str) -> Callable[[F], F]:
    """Decorator to standardize API error handling.

    Catches HTTPException (re-raises as-is) and generic Exception
    (logs and wraps in 500 error).

    Args:
        operation_name: Description of the operation for error messages

    Returns:
        Decorated function with standardized error handling

    Example:
        @handle_api_errors("fetch watchlist items")
        async def get_items():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise  # Re-raise HTTP exceptions as-is
            except Exception as e:
                logger.error(
                    "api_error",
                    operation=operation_name,
                    error=str(e),
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500, detail=f"Failed to {operation_name}: {e}"
                ) from e

        # Copy __globals__ so FastAPI can resolve forward-ref annotations
        # (e.g. 'WatchlistItemCreate') from the original module's namespace.
        # functools.wraps does NOT copy __globals__, causing body params to be
        # misclassified as query params when `from __future__ import annotations`
        # turns type hints into strings.
        wrapper.__globals__.update(func.__globals__)

        return wrapper  # type: ignore[return-value]

    return decorator


def require_nonempty_df(df: pl.DataFrame, error_msg: str) -> None:
    """Raise HTTPException if DataFrame is empty.

    Args:
        df: DataFrame to check
        error_msg: Error message to include in exception

    Raises:
        HTTPException: 404 error if DataFrame is empty
    """
    if df.is_empty():
        raise HTTPException(status_code=404, detail=error_msg)
