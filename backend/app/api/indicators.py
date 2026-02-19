"""Technical indicators API router.

Exposes technical indicator calculations via REST API endpoints.
Sub-modules:
  _indicators_models  - Pydantic response models
  _indicators_history - History query helpers and history endpoint logic
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query

from app.analytics.indicators import calculate_indicators
from app.storage import get_storage

from ._indicators_history import fetch_indicators_history
from ._indicators_models import (
    BollingerBandsIndicator,
    IndicatorInterpretations,
    IndicatorsResponse,
    IndicatorValues,
    MACDIndicator,
    StochasticIndicator,
)

# Re-export all public names so existing importers continue to work
__all__ = [
    "BollingerBandsIndicator",
    "IndicatorInterpretations",
    "IndicatorValues",
    "IndicatorsResponse",
    "MACDIndicator",
    "StochasticIndicator",
    "router",
]

router = APIRouter(prefix="/api/indicators", tags=["indicators"])

# Initialize storage
storage = get_storage()


def _calculate_indicator_response(
    symbol: str,
    date: str | None,
    indicators: str | None,
) -> IndicatorsResponse:
    """Calculate indicators and return a response, raising HTTPException on error."""
    try:
        indicator_list: list[str] | None = None
        if indicators:
            indicator_list = [ind.strip() for ind in indicators.split(",")]

        result = calculate_indicators(
            storage=storage,
            symbol=symbol,
            indicators=indicator_list,
            as_of_date=date,
        )

        response_data: dict[str, Any] = {
            "symbol": result["symbol"],
            "date": result["date"],
            "close_price": result.get("close_price"),
            "indicators": result["indicators"],
            "interpretations": result["interpretations"],
        }

        return IndicatorsResponse(**response_data)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating indicators: {e!s}") from e


@router.get("/{symbol}", response_model=IndicatorsResponse)
def get_indicators_for_symbol(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
    date: Annotated[
        str | None,
        Query(
            description="Date for indicators (YYYY-MM-DD). Defaults to latest available.",
            pattern=r"^\d{4}-\d{2}-\d{2}$",
        ),
    ] = None,
    indicators: Annotated[
        str | None,
        Query(
            description="Comma-separated list of indicators to calculate. If omitted, calculates all. "
            "Supported: rsi, macd, bbands, sma_20, sma_50, sma_200, ema_20, ema_50, ema_200, atr, stoch"
        ),
    ] = None,
) -> IndicatorsResponse:
    """Get technical indicators for a symbol."""
    return _calculate_indicator_response(symbol.upper(), date, indicators)


@router.get("/{symbol}/history", response_model=list[IndicatorsResponse])
def get_indicators_history(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
    start_date: Annotated[
        str | None,
        Query(
            description="Start date for historical indicators (YYYY-MM-DD)",
            pattern=r"^\d{4}-\d{2}-\d{2}$",
        ),
    ] = None,
    end_date: Annotated[
        str | None,
        Query(
            description="End date for historical indicators (YYYY-MM-DD). Defaults to latest.",
            pattern=r"^\d{4}-\d{2}-\d{2}$",
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            description="Maximum number of historical records to return",
            ge=1,
            le=365,
        ),
    ] = 30,
) -> list[IndicatorsResponse]:
    """Get historical technical indicators for a symbol.

    Returns indicator values for multiple dates, useful for charting trends.

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
        limit: Maximum number of records to return (default: 30, max: 365)

    Returns:
        List of IndicatorsResponse, one per date, sorted by date descending

    Raises:
        HTTPException 404: If symbol has insufficient data
        HTTPException 400: If invalid date format
    """
    return fetch_indicators_history(storage, symbol.upper(), start_date, end_date, limit)
