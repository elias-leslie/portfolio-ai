"""Technical indicators API router.

Exposes technical indicator calculations via REST API endpoints.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.analytics.indicators import calculate_indicators
from app.storage import get_storage

router = APIRouter(prefix="/api/indicators", tags=["indicators"])

# Initialize storage
storage = get_storage()


# Response models
class MACDIndicator(BaseModel):
    """MACD indicator values."""

    macd: float = Field(..., description="MACD line value")
    signal: float = Field(..., description="Signal line value")
    histogram: float = Field(..., description="MACD histogram value")


class BollingerBandsIndicator(BaseModel):
    """Bollinger Bands indicator values."""

    upper: float = Field(..., description="Upper band value")
    middle: float = Field(..., description="Middle band (SMA) value")
    lower: float = Field(..., description="Lower band value")


class StochasticIndicator(BaseModel):
    """Stochastic oscillator indicator values."""

    k: float = Field(..., description="%K line value")
    d: float = Field(..., description="%D line value")


class IndicatorValues(BaseModel):
    """All calculated indicator values."""

    rsi_14: float | None = Field(None, description="14-period RSI")
    macd_12_26_9: MACDIndicator | None = Field(None, description="MACD (12, 26, 9)")
    bbands_20_2: BollingerBandsIndicator | None = Field(
        None, description="Bollinger Bands (20, 2 std dev)"
    )
    sma_20: float | None = Field(None, description="20-period SMA")
    sma_50: float | None = Field(None, description="50-period SMA")
    sma_200: float | None = Field(None, description="200-period SMA")
    ema_20: float | None = Field(None, description="20-period EMA")
    ema_50: float | None = Field(None, description="50-period EMA")
    ema_200: float | None = Field(None, description="200-period EMA")
    atr_14: float | None = Field(None, description="14-period ATR")
    stoch_14_3_3: StochasticIndicator | None = Field(None, description="Stochastic (14, 3, 3)")


class IndicatorInterpretations(BaseModel):
    """Human-readable interpretations of indicator values."""

    rsi: str | None = Field(None, description="RSI interpretation (oversold/neutral/overbought)")
    macd: str | None = Field(
        None, description="MACD interpretation (bullish_cross/bearish_cross/neutral)"
    )
    bbands_position: str | None = Field(
        None, description="Price position relative to Bollinger Bands"
    )
    price_vs_sma_200: str | None = Field(None, description="Price position relative to 200-day SMA")
    stoch: str | None = Field(
        None, description="Stochastic interpretation (oversold/neutral/overbought)"
    )


class IndicatorsResponse(BaseModel):
    """Response model for technical indicators."""

    ticker: str = Field(..., description="Stock ticker symbol")
    date: str = Field(..., description="Date for indicator values (YYYY-MM-DD)")
    close_price: float | None = Field(None, description="Closing price on the date")
    indicators: IndicatorValues = Field(..., description="Calculated indicator values")
    interpretations: IndicatorInterpretations = Field(
        ..., description="Human-readable interpretations"
    )


# API Endpoints
@router.get("/{ticker}", response_model=IndicatorsResponse)
def get_indicators_for_ticker(
    ticker: Annotated[str, Path(description="Stock ticker symbol (e.g., AAPL)")],
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
    """Get technical indicators for a ticker.

    Calculates requested technical indicators using OHLCV data from the day_bars table.
    If no date is specified, returns indicators for the latest available date.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        date: Optional date for indicator calculation (YYYY-MM-DD)
        indicators: Optional comma-separated list of specific indicators to calculate

    Returns:
        IndicatorsResponse with indicator values and interpretations

    Raises:
        HTTPException 404: If ticker has insufficient data
        HTTPException 400: If invalid date format or indicator name
    """
    try:
        # Parse indicators list if provided
        indicator_list: list[str] | None = None
        if indicators:
            indicator_list = [ind.strip() for ind in indicators.split(",")]

        # Calculate indicators
        result = calculate_indicators(
            storage=storage,
            ticker=ticker.upper(),
            indicators=indicator_list,
            as_of_date=date,
        )

        # Transform the result to match our response model
        response_data: dict[str, Any] = {
            "ticker": result["ticker"],
            "date": result["date"],
            "close_price": result.get("close_price"),
            "indicators": result["indicators"],
            "interpretations": result["interpretations"],
        }

        return IndicatorsResponse(**response_data)

    except ValueError as e:
        # Insufficient data or invalid input
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        # Unexpected error
        raise HTTPException(status_code=500, detail=f"Error calculating indicators: {e!s}") from e


@router.get("/{ticker}/history", response_model=list[IndicatorsResponse])
def get_indicators_history(
    ticker: Annotated[str, Path(description="Stock ticker symbol (e.g., AAPL)")],
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
    """Get historical technical indicators for a ticker.

    Returns indicator values for multiple dates, useful for charting trends.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
        limit: Maximum number of records to return (default: 30, max: 365)

    Returns:
        List of IndicatorsResponse, one per date, sorted by date descending

    Raises:
        HTTPException 404: If ticker has insufficient data
        HTTPException 400: If invalid date format
    """
    try:
        # Query the technical_indicators table for cached values
        query = """
            SELECT
                ticker,
                date,
                close_price,
                rsi_14,
                macd_12_26_9_macd,
                macd_12_26_9_signal,
                macd_12_26_9_histogram,
                bbands_20_2_upper,
                bbands_20_2_middle,
                bbands_20_2_lower,
                sma_20,
                sma_50,
                sma_200,
                ema_20,
                ema_50,
                ema_200,
                atr_14,
                stoch_14_3_3_k,
                stoch_14_3_3_d
            FROM technical_indicators
            WHERE ticker = ?
        """
        params: list[str | int] = [ticker.upper()]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC LIMIT ?"
        params.append(limit)

        df = storage.query(query, params)

        if df.is_empty():
            raise ValueError(
                f"No indicator data found for ticker {ticker}. "
                "Run the update_technical_indicators Celery task first."
            )

        # Convert to list of IndicatorsResponse
        responses: list[IndicatorsResponse] = []
        for row in df.iter_rows(named=True):
            # Build indicator values
            indicators_data: dict[str, Any] = {}

            if row["rsi_14"] is not None:
                indicators_data["rsi_14"] = row["rsi_14"]

            if row["macd_12_26_9_macd"] is not None:
                indicators_data["macd_12_26_9"] = {
                    "macd": row["macd_12_26_9_macd"],
                    "signal": row["macd_12_26_9_signal"],
                    "histogram": row["macd_12_26_9_histogram"],
                }

            if row["bbands_20_2_upper"] is not None:
                indicators_data["bbands_20_2"] = {
                    "upper": row["bbands_20_2_upper"],
                    "middle": row["bbands_20_2_middle"],
                    "lower": row["bbands_20_2_lower"],
                }

            if row["sma_20"] is not None:
                indicators_data["sma_20"] = row["sma_20"]
            if row["sma_50"] is not None:
                indicators_data["sma_50"] = row["sma_50"]
            if row["sma_200"] is not None:
                indicators_data["sma_200"] = row["sma_200"]

            if row["ema_20"] is not None:
                indicators_data["ema_20"] = row["ema_20"]
            if row["ema_50"] is not None:
                indicators_data["ema_50"] = row["ema_50"]
            if row["ema_200"] is not None:
                indicators_data["ema_200"] = row["ema_200"]

            if row["atr_14"] is not None:
                indicators_data["atr_14"] = row["atr_14"]

            if row["stoch_14_3_3_k"] is not None:
                indicators_data["stoch_14_3_3"] = {
                    "k": row["stoch_14_3_3_k"],
                    "d": row["stoch_14_3_3_d"],
                }

            # Generate interpretations (simplified - could be expanded)
            interpretations_data: dict[str, str] = {}
            if row["rsi_14"] is not None:
                rsi = row["rsi_14"]
                if rsi < 30:
                    interpretations_data["rsi"] = "oversold"
                elif rsi > 70:
                    interpretations_data["rsi"] = "overbought"
                else:
                    interpretations_data["rsi"] = "neutral"

            if row["macd_12_26_9_macd"] is not None:
                macd = row["macd_12_26_9_macd"]
                signal = row["macd_12_26_9_signal"]
                if macd > signal:
                    interpretations_data["macd"] = "bullish_cross"
                elif macd < signal:
                    interpretations_data["macd"] = "bearish_cross"
                else:
                    interpretations_data["macd"] = "neutral"

            # Build response
            response = IndicatorsResponse(
                ticker=row["ticker"],
                date=str(row["date"]),
                close_price=row.get("close_price"),
                indicators=IndicatorValues(**indicators_data),
                interpretations=IndicatorInterpretations(**interpretations_data),
            )
            responses.append(response)

        return responses

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving indicator history: {e!s}"
        ) from e
