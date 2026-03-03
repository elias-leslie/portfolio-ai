"""Valuation metrics API router.

Provides endpoints for retrieving valuation metrics (P/E, P/B, P/S, etc.)
extracted from reference cache data.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.api._valuation_helpers import (
    VALUATION_SINGLE_QUERY,
    build_valuation_batch_query,
    normalize_as_of_date,
    parse_symbols_param,
    to_float_or_none,
    validate_single_row_fields,
)
from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)

router = APIRouter(prefix="/api/valuation", tags=["valuation"])
storage = get_storage()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ValuationMetrics(BaseModel):
    """Valuation metrics for a single symbol."""

    symbol: str = Field(..., description="Stock symbol")
    pe_ratio_trailing: float | None = Field(None, description="Trailing P/E ratio")
    pe_ratio_forward: float | None = Field(None, description="Forward P/E ratio")
    ps_ratio: float | None = Field(None, description="Price-to-Sales ratio (TTM)")
    pb_ratio: float | None = Field(None, description="Price-to-Book ratio")
    peg_ratio: float | None = Field(None, description="PEG ratio")
    dividend_yield: float | None = Field(None, description="Dividend yield (as decimal, 0.02 = 2%)")
    payout_ratio: float | None = Field(None, description="Dividend payout ratio (as decimal)")
    as_of_date: str = Field(..., description="Date metrics were cached (YYYY-MM-DD)")


class ValuationMetricsListResponse(BaseModel):
    """Response containing valuation metrics for multiple symbols."""

    symbols: list[ValuationMetrics] = Field(..., description="Valuation metrics for each symbol")
    count: int = Field(..., description="Number of symbols returned")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_metrics(row: tuple[object, ...]) -> ValuationMetrics:
    """Convert a DB result row to a ValuationMetrics instance."""
    return ValuationMetrics(
        symbol=str(row[0]),
        pe_ratio_trailing=to_float_or_none(row[1]),
        pe_ratio_forward=to_float_or_none(row[2]),
        ps_ratio=to_float_or_none(row[3]),
        pb_ratio=to_float_or_none(row[4]),
        peg_ratio=to_float_or_none(row[5]),
        dividend_yield=to_float_or_none(row[6]),
        payout_ratio=to_float_or_none(row[7]),
        as_of_date=normalize_as_of_date(row[8], context=str(row[0])),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{symbol}", response_model=ValuationMetrics)
async def get_valuation_metrics(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
) -> ValuationMetrics:
    """Get valuation metrics for a single symbol.

    Retrieves the most recent cached valuation metrics including trailing and
    forward P/E, P/B, P/S, PEG, dividend yield, and payout ratio.

    Raises:
        HTTPException: 404 if symbol not found in cache, 500 on data errors.
    """
    try:
        with storage.connection() as conn:
            result = conn.execute(VALUATION_SINGLE_QUERY, [symbol.upper()]).fetchone()

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No valuation metrics found for symbol {symbol}",
            )

        validate_single_row_fields(result)
        return _row_to_metrics(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get valuation metrics", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch valuation metrics: {e}",
        ) from e


@router.get("", response_model=ValuationMetricsListResponse)
async def get_valuation_metrics_batch(
    symbols: Annotated[
        str,
        Query(description="Comma-separated list of symbols (e.g., AAPL,NVDA,TSLA)"),
    ] = "",
) -> ValuationMetricsListResponse:
    """Get valuation metrics for multiple symbols.

    Retrieves the most recent cached valuation metrics for a list of symbols.

    Raises:
        HTTPException: 400 if no symbols provided, 404 if none found, 500 on DB error.
    """
    try:
        symbol_list = parse_symbols_param(symbols)

        with storage.connection() as conn:
            query = build_valuation_batch_query(len(symbol_list))
            rows = conn.execute(query, list(symbol_list)).fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No valuation metrics found for symbols: {symbols}",
            )

        metrics_by_symbol: dict[str, ValuationMetrics] = {}
        for row in rows:
            sym = row[0]
            if not isinstance(sym, str):
                logger.warning("Skipping result with non-string symbol", symbol_type=type(sym))
                continue
            if sym in metrics_by_symbol:
                continue  # already have the most recent entry
            as_of = row[8]
            if not isinstance(as_of, (str, dt.date, dt.datetime)):
                logger.warning("Skipping result with non-string as_of_date", symbol=sym, as_of_type=type(as_of))
                continue
            metrics_by_symbol[sym] = _row_to_metrics(row)

        return ValuationMetricsListResponse(
            symbols=list(metrics_by_symbol.values()),
            count=len(metrics_by_symbol),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get valuation metrics batch", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch valuation metrics: {e}",
        ) from e
