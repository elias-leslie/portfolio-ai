"""Valuation metrics API router.

Provides endpoints for retrieving valuation metrics (P/E, P/B, P/S, etc.)
extracted from reference cache data.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.logging_config import get_logger
from app.middleware.cache import cache_response
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
@cache_response(ttl=3600)  # 1 hour cache
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
                WHERE ticker = %s
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

            return ValuationMetrics(
                ticker=result[0],
                pe_ratio_trailing=result[1],
                pe_ratio_forward=result[2],
                ps_ratio=result[3],
                pb_ratio=result[4],
                peg_ratio=result[5],
                dividend_yield=result[6],
                payout_ratio=result[7],
                as_of_date=str(result[8]),
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
@cache_response(ttl=3600)  # 1 hour cache
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
                WHERE ticker IN ({placeholders})
                ORDER BY ticker, as_of_date DESC
            """

            results = conn.execute(query, ticker_list).fetchall()

            if not results:
                raise HTTPException(
                    status_code=404,
                    detail=f"No valuation metrics found for tickers: {tickers}",
                )

            # Build response, taking only the most recent per ticker
            metrics_by_ticker: dict[str, ValuationMetrics] = {}

            for result in results:
                ticker_symbol = result[0]

                # Skip if we already have a (more recent) entry for this ticker
                if ticker_symbol in metrics_by_ticker:
                    continue

                metrics_by_ticker[ticker_symbol] = ValuationMetrics(
                    ticker=result[0],
                    pe_ratio_trailing=result[1],
                    pe_ratio_forward=result[2],
                    ps_ratio=result[3],
                    pb_ratio=result[4],
                    peg_ratio=result[5],
                    dividend_yield=result[6],
                    payout_ratio=result[7],
                    as_of_date=str(result[8]),
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
