"""Helper functions for valuation metrics API endpoints."""

from __future__ import annotations

import datetime as dt

from fastapi import HTTPException

from app.logging_config import get_logger

logger = get_logger(__name__)

# SQL query used by both single and batch valuation endpoints
VALUATION_SELECT_FIELDS = """
    symbol,
    pe_ratio_trailing,
    pe_ratio_forward,
    ps_ratio,
    pb_ratio,
    peg_ratio,
    dividend_yield,
    payout_ratio,
    as_of_date
"""

VALUATION_SINGLE_QUERY = f"""
    SELECT {VALUATION_SELECT_FIELDS}
    FROM reference_cache
    WHERE symbol = %s
    ORDER BY as_of_date DESC
    LIMIT 1
"""


def build_valuation_batch_query(symbol_count: int) -> str:
    """Build a parameterized batch query for the given number of symbols.

    Raises:
        ValueError: If symbol_count is less than or equal to zero, because
            ``WHERE symbol IN ()`` is syntactically invalid in most SQL dialects.
    """
    if symbol_count <= 0:
        raise ValueError(f"symbol_count must be a positive integer, got {symbol_count}")
    placeholders = ",".join(["%s"] * symbol_count)
    return f"""
        SELECT {VALUATION_SELECT_FIELDS}
        FROM reference_cache
        WHERE symbol IN ({placeholders})
        ORDER BY symbol, as_of_date DESC
    """


def to_float_or_none(val: object) -> float | None:
    """Convert a value to float if numeric, otherwise return None."""
    if isinstance(val, (int, float)):
        return float(val)
    return None


def normalize_as_of_date(as_of: object, context: str = "") -> str:
    """Convert a date/datetime/str value to an ISO date string.

    Args:
        as_of: The raw as_of_date value from the database row.
        context: Optional context string used in error messages (e.g. a symbol).

    Returns:
        ISO-formatted date string.

    Raises:
        HTTPException: 500 if the type is unexpected.
    """
    if isinstance(as_of, (dt.date, dt.datetime)):
        return as_of.isoformat()
    if isinstance(as_of, str):
        return as_of
    raise HTTPException(status_code=500, detail=f"Invalid as_of_date type{' for ' + context if context else ''}")


def validate_single_row_fields(row: tuple[object, ...]) -> None:
    """Validate type correctness of a single-symbol result row.

    Raises HTTPException 500 if any field has an unexpected type.
    This is called for the single-symbol endpoint where strict validation is warranted.

    NOTE: The field_names list and the positional indices below (start=1 through 7)
    are tightly coupled to the column order defined in VALUATION_SELECT_FIELDS.
    If that constant changes, this function must be updated to match.
    Expected column order from VALUATION_SELECT_FIELDS:
      index 0: symbol
      index 1: pe_ratio_trailing
      index 2: pe_ratio_forward
      index 3: ps_ratio
      index 4: pb_ratio
      index 5: peg_ratio
      index 6: dividend_yield
      index 7: payout_ratio
      index 8: as_of_date
    """
    symbol_val = row[0]
    if not isinstance(symbol_val, str):
        raise HTTPException(status_code=500, detail="Invalid symbol data type from database")

    # Indices 1-7 correspond to the numeric fields in VALUATION_SELECT_FIELDS (see above).
    field_names = [
        "pe_ratio_trailing",
        "pe_ratio_forward",
        "ps_ratio",
        "pb_ratio",
        "peg_ratio",
        "dividend_yield",
        "payout_ratio",
    ]
    for idx, name in enumerate(field_names, start=1):
        val = row[idx]
        if val is not None and not isinstance(val, (int, float)):
            raise HTTPException(status_code=500, detail=f"Invalid {name}")


def parse_symbols_param(symbols: str) -> list[str]:
    """Parse and normalise a comma-separated symbols query parameter.

    Returns:
        List of upper-cased, stripped symbol strings.

    Raises:
        HTTPException: 400 if the input is blank or yields no valid tokens.
    """
    if not symbols.strip():
        raise HTTPException(
            status_code=400,
            detail="No symbols provided. Use ?symbols=AAPL,NVDA,TSLA",
        )
    symbol_list = [t.strip().upper() for t in symbols.split(",") if t.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No valid symbols provided")
    return symbol_list
