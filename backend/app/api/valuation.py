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
    """Valuation metrics for a single ticker."""

    ticker: str = Field(..., description="Stock ticker symbol")
    pe_ratio_trailing: float | None = Field(None, description="Trailing P/E ratio")
    pe_ratio_forward: float | None = Field(None, description="Forward P/E ratio")
    ps_ratio: float | None = Field(None, description="Price-to-Sales ratio (TTM)")
    pb_ratio: float | None = Field(None, description="Price-to-Book ratio")
    peg_ratio: float | None = Field(None, description="PEG ratio")
    dividend_yield: float | None = Field(None, description="Dividend yield (as decimal, 0.02 = 2%)")
    payout_ratio: float | None = Field(None, description="Dividend payout ratio (as decimal)")
    as_of_date: str = Field(..., description="Date metrics were cached (YYYY-MM-DD)")


class ValuationMetricsListResponse(BaseModel):
    """Response containing valuation metrics for multiple tickers."""

    tickers: list[ValuationMetrics] = Field(..., description="Valuation metrics for each ticker")
    count: int = Field(..., description="Number of tickers returned")


# Endpoints


@router.get("/{ticker}", response_model=ValuationMetrics)
async def get_valuation_metrics(
    ticker: Annotated[str, Path(description="Stock ticker symbol (e.g., AAPL)")],
) -> ValuationMetrics:
    """Get valuation metrics for a single ticker.

    Retrieves the most recent cached valuation metrics including:
    - Trailing and forward P/E ratios
    - Price-to-Book and Price-to-Sales ratios
    - PEG ratio, dividend yield, and payout ratio

    Args:
        ticker: Stock ticker symbol (e.g., AAPL, NVDA, TSLA)

    Returns:
        ValuationMetrics with all available metrics

    Raises:
        HTTPException: 404 if ticker not found in cache
    """
    try:
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    ticker,
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
                [ticker.upper()],
            ).fetchone()

            if result is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No valuation metrics found for ticker {ticker}",
                )

            # Type narrowing for database result tuple
            ticker_val = result[0]
            pe_trailing = result[1]
            pe_forward = result[2]
            ps = result[3]
            pb = result[4]
            peg = result[5]
            div_yield = result[6]
            payout = result[7]
            as_of = result[8]

            # Validate ticker is a string
            if not isinstance(ticker_val, str):
                raise HTTPException(
                    status_code=500,
                    detail="Invalid ticker data type from database",
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
                ticker=ticker_val,
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
        logger.error("Failed to get valuation metrics", ticker=ticker, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch valuation metrics: {e}",
        ) from e


@router.get("", response_model=ValuationMetricsListResponse)
async def get_valuation_metrics_batch(
    tickers: Annotated[
        str,
        Query(
            description="Comma-separated list of ticker symbols (e.g., AAPL,NVDA,TSLA)",
        ),
    ] = "",
) -> ValuationMetricsListResponse:
    """Get valuation metrics for multiple tickers.

    Retrieves the most recent cached valuation metrics for a list of tickers.

    Args:
        tickers: Comma-separated list of ticker symbols

    Returns:
        List of ValuationMetrics for requested tickers

    Raises:
        HTTPException: 400 if no tickers provided or 500 on database error
    """
    try:
        if not tickers.strip():
            raise HTTPException(
                status_code=400,
                detail="No tickers provided. Use ?tickers=AAPL,NVDA,TSLA",
            )

        # Parse and normalize tickers
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]

        if not ticker_list:
            raise HTTPException(
                status_code=400,
                detail="No valid tickers provided",
            )

        with storage.connection() as conn:
            # Build IN clause for multiple tickers
            placeholders = ",".join(["%s"] * len(ticker_list))
            query = f"""
                SELECT
                    ticker,
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
            ] = list(ticker_list)

            results = conn.execute(query, params).fetchall()

            if not results:
                raise HTTPException(
                    status_code=404,
                    detail=f"No valuation metrics found for tickers: {tickers}",
                )

            # Build response, taking only the most recent per ticker
            metrics_by_ticker: dict[str, ValuationMetrics] = {}

            for result in results:
                ticker_symbol = result[0]

                # Type narrowing for ticker_symbol
                if not isinstance(ticker_symbol, str):
                    logger.warning(
                        "Skipping result with non-string ticker",
                        ticker_type=type(ticker_symbol),
                    )
                    continue

                # Skip if we already have a (more recent) entry for this ticker
                if ticker_symbol in metrics_by_ticker:
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
                        ticker=ticker_symbol,
                        as_of_type=type(as_of),
                    )
                    continue

                # Helper to convert numeric values to float or None
                def to_float_or_none(val: object) -> float | None:
                    return val if isinstance(val, (int, float)) else None

                metrics_by_ticker[ticker_symbol] = ValuationMetrics(
                    ticker=ticker_symbol,
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
                tickers=list(metrics_by_ticker.values()),
                count=len(metrics_by_ticker),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get valuation metrics batch", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch valuation metrics: {e}",
        ) from e
