"""Input validation for watchlist operations."""

from __future__ import annotations

from fastapi import HTTPException


def validate_symbol(symbol: str | None) -> str:
    """Validate and normalize a stock symbol.

    Args:
        symbol: Raw symbol string from user input

    Returns:
        Normalized symbol (uppercase, stripped)

    Raises:
        HTTPException: If symbol is invalid (empty or None)
    """
    if not symbol or not symbol.strip():
        raise HTTPException(status_code=400, detail="Symbol cannot be empty")
    normalized = symbol.strip().upper()
    if normalized.startswith("ZZTEST"):
        raise HTTPException(
            status_code=400,
            detail="Test symbols are blocked from the live watchlist",
        )
    return normalized
