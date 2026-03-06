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


def validate_account_id(account_id: str | None) -> str:
    """Validate account ID is present.

    Args:
        account_id: Account ID from request

    Returns:
        Account ID if valid

    Raises:
        HTTPException: If account ID is missing or empty
    """
    if not account_id or not account_id.strip():
        raise HTTPException(status_code=400, detail="Account ID is required")

    return account_id.strip()


def validate_item_id(item_id: str | None) -> str:
    """Validate watchlist item ID is present.

    Args:
        item_id: Item ID from request

    Returns:
        Item ID if valid

    Raises:
        HTTPException: If item ID is missing or empty
    """
    if not item_id or not item_id.strip():
        raise HTTPException(status_code=400, detail="Item ID is required")

    return item_id.strip()
