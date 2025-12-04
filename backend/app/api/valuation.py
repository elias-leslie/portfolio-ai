"""Valuation metrics API router.

Provides endpoints for retrieving valuation metrics (P/E, P/B, P/S, etc.)
extracted from reference cache data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)

router = APIRouter(prefix="/api/valuation", tags=["valuation"])

# Initialize storage
storage = get_storage()


# Response models
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


# Endpoints


@router.get("/{symbol}", response_model=ValuationMetrics)
async def get_valuation_metrics(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
) -> ValuationMetrics:
    """Get valuation metrics for a single symbol.

    Retrieves the most recent cached valuation metrics including:
    - Trailing and forward P/E ratios
    - Price-to-Book and Price-to-Sales ratios
    - PEG ratio, dividend yield, and payout ratio

    Args:
        symbol: Stock symbol (e.g., AAPL, NVDA, TSLA)

    Returns:
        ValuationMetrics with all available metrics

    Raises:
        HTTPException: 404 if symbol not found in cache
    """
    try:
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    symbol,
                    pe_ratio_trailing,
                    pe_ratio_forward,
                    ps_ratio,
                    pb_ratio,
                    peg_ratio,
                    dividend_yield,
                    payout_ratio,
                    as_of_date
                FROM reference_cache
                WHERE symbol = %s
                ORDER BY as_of_date DESC
                LIMIT 1
                """,
                [symbol.upper()],
            ).fetchone()

            if result is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No valuation metrics found for symbol {symbol}",
                )

            # Type narrowing for database result tuple
            symbol_val = result[0]
            pe_trailing = result[1]
            pe_forward = result[2]
            ps = result[3]
            pb = result[4]
            peg = result[5]
            div_yield = result[6]
            payout = result[7]
            as_of = result[8]

            # Validate symbol is a string
            if not isinstance(symbol_val, str):
                raise HTTPException(
                    status_code=500,
                    detail="Invalid symbol data type from database",
                )

            # Validate and convert float fields (allowing None for optional fields)
            if pe_trailing is not None and not isinstance(pe_trailing, (int, float)):
                raise HTTPException(status_code=500, detail="Invalid pe_ratio_trailing")
            if pe_forward is not None and not isinstance(pe_forward, (int, float)):
                raise HTTPException(status_code=500, detail="Invalid pe_ratio_forward")
            if ps is not None and not isinstance(ps, (int, float)):
                raise HTTPException(status_code=500, detail="Invalid ps_ratio")
            if pb is not None and not isinstance(pb, (int, float)):
                raise HTTPException(status_code=500, detail="Invalid pb_ratio")
            if peg is not None and not isinstance(peg, (int, float)):
                raise HTTPException(status_code=500, detail="Invalid peg_ratio")
            if div_yield is not None and not isinstance(div_yield, (int, float)):
                raise HTTPException(status_code=500, detail="Invalid dividend_yield")
            if payout is not None and not isinstance(payout, (int, float)):
                raise HTTPException(status_code=500, detail="Invalid payout_ratio")

            # Validate as_of_date
            if not isinstance(as_of, str):
                raise HTTPException(status_code=500, detail="Invalid as_of_date")

            return ValuationMetrics(
                symbol=symbol_val,
                pe_ratio_trailing=pe_trailing if isinstance(pe_trailing, (int, float)) else None,
                pe_ratio_forward=pe_forward if isinstance(pe_forward, (int, float)) else None,
                ps_ratio=ps if isinstance(ps, (int, float)) else None,
                pb_ratio=pb if isinstance(pb, (int, float)) else None,
                peg_ratio=peg if isinstance(peg, (int, float)) else None,
                dividend_yield=div_yield if isinstance(div_yield, (int, float)) else None,
                payout_ratio=payout if isinstance(payout, (int, float)) else None,
                as_of_date=as_of,
            )

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
        Query(
            description="Comma-separated list of symbols (e.g., AAPL,NVDA,TSLA)",
        ),
    ] = "",
) -> ValuationMetricsListResponse:
    """Get valuation metrics for multiple symbols.

    Retrieves the most recent cached valuation metrics for a list of symbols.

    Args:
        symbols: Comma-separated list of symbols

    Returns:
        List of ValuationMetrics for requested symbols

    Raises:
        HTTPException: 400 if no symbols provided or 500 on database error
    """
    try:
        if not symbols.strip():
            raise HTTPException(
                status_code=400,
                detail="No symbols provided. Use ?symbols=AAPL,NVDA,TSLA",
            )

        # Parse and normalize symbols
        symbol_list = [t.strip().upper() for t in symbols.split(",") if t.strip()]

        if not symbol_list:
            raise HTTPException(
                status_code=400,
                detail="No valid symbols provided",
            )

        with storage.connection() as conn:
            # Build IN clause for multiple symbols
            placeholders = ",".join(["%s"] * len(symbol_list))
            query = f"""
                SELECT
                    symbol,
                    pe_ratio_trailing,
                    pe_ratio_forward,
                    ps_ratio,
                    pb_ratio,
                    peg_ratio,
                    dividend_yield,
                    payout_ratio,
                    as_of_date
                FROM reference_cache
                WHERE symbol IN ({placeholders})
                ORDER BY symbol, as_of_date DESC
            """

            # Cast list[str] to expected parameter type for type checking
            # This is safe since str is a valid ParameterValue
            params: list[
                str | int | float | bool | datetime | list[str | int | float | bool | None] | None
            ] = list(symbol_list)

            results = conn.execute(query, params).fetchall()

            if not results:
                raise HTTPException(
                    status_code=404,
                    detail=f"No valuation metrics found for symbols: {symbols}",
                )

            # Build response, taking only the most recent per symbol
            metrics_by_symbol: dict[str, ValuationMetrics] = {}

            for result in results:
                symbol_symbol = result[0]

                # Type narrowing for symbol_symbol
                if not isinstance(symbol_symbol, str):
                    logger.warning(
                        "Skipping result with non-string symbol",
                        symbol_type=type(symbol_symbol),
                    )
                    continue

                # Skip if we already have a (more recent) entry for this symbol
                if symbol_symbol in metrics_by_symbol:
                    continue

                # Type narrowing and validation for result fields
                pe_trailing = result[1]
                pe_forward = result[2]
                ps = result[3]
                pb = result[4]
                peg = result[5]
                div_yield = result[6]
                payout = result[7]
                as_of = result[8]

                # Validate as_of_date
                if not isinstance(as_of, str):
                    logger.warning(
                        "Skipping result with non-string as_of_date",
                        symbol=symbol_symbol,
                        as_of_type=type(as_of),
                    )
                    continue

                # Helper to convert numeric values to float or None
                def to_float_or_none(val: object) -> float | None:
                    return val if isinstance(val, (int, float)) else None

                metrics_by_symbol[symbol_symbol] = ValuationMetrics(
                    symbol=symbol_symbol,
                    pe_ratio_trailing=to_float_or_none(pe_trailing),
                    pe_ratio_forward=to_float_or_none(pe_forward),
                    ps_ratio=to_float_or_none(ps),
                    pb_ratio=to_float_or_none(pb),
                    peg_ratio=to_float_or_none(peg),
                    dividend_yield=to_float_or_none(div_yield),
                    payout_ratio=to_float_or_none(payout),
                    as_of_date=as_of,
                )

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
