"""API utility functions."""

from __future__ import annotations

import polars as pl
from fastapi import HTTPException


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
