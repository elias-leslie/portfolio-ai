"""History query helpers for technical indicators API."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from fastapi import HTTPException

from app.storage.types import ParameterValue

from ._indicators_models import (
    BollingerBandsIndicator,
    IndicatorInterpretations,
    IndicatorsResponse,
    IndicatorValues,
    MACDIndicator,
    StochasticIndicator,
)
from .types import IndicatorRowDict, IndicatorValuesDict, InterpretationValuesDict


def build_indicators_query(
    symbol: str,
    start_date: str | None,
    end_date: str | None,
    limit: int,
) -> tuple[str, list[str | int | float | bool | datetime | None]]:
    """Build SQL query for fetching indicator history.

    Args:
        symbol: Stock symbol
        start_date: Optional start date filter
        end_date: Optional end date filter
        limit: Maximum number of records

    Returns:
        Tuple of (query, params)
    """
    query = """
        SELECT
            symbol,
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
        WHERE symbol = ?
    """
    params: list[str | int | float | bool | datetime | None] = [symbol.upper()]

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    query += " ORDER BY date DESC LIMIT ?"
    params.append(limit)

    return query, params


def build_indicator_values(row: IndicatorRowDict) -> IndicatorValuesDict:
    """Build indicator values dict from database row.

    Args:
        row: Database row with indicator values

    Returns:
        Dict of indicator values
    """
    data: IndicatorValuesDict = {}

    if row["rsi_14"] is not None:
        data["rsi_14"] = row["rsi_14"]

    macd_val = row["macd_12_26_9_macd"]
    signal_val = row["macd_12_26_9_signal"]
    hist_val = row["macd_12_26_9_histogram"]
    if macd_val is not None and signal_val is not None and hist_val is not None:
        data["macd_12_26_9"] = {
            "macd": float(macd_val),
            "signal": float(signal_val),
            "histogram": float(hist_val),
        }

    upper_val = row["bbands_20_2_upper"]
    middle_val = row["bbands_20_2_middle"]
    lower_val = row["bbands_20_2_lower"]
    if upper_val is not None and middle_val is not None and lower_val is not None:
        data["bbands_20_2"] = {
            "upper": float(upper_val),
            "middle": float(middle_val),
            "lower": float(lower_val),
        }

    for key in ("sma_20", "sma_50", "sma_200", "ema_20", "ema_50", "ema_200", "atr_14"):
        val = row[key]  # type: ignore[literal-required]
        if val is not None:
            data[key] = val  # type: ignore[literal-required]

    k_val = row["stoch_14_3_3_k"]
    d_val = row["stoch_14_3_3_d"]
    if k_val is not None and d_val is not None:
        data["stoch_14_3_3"] = {"k": float(k_val), "d": float(d_val)}

    return data


def generate_interpretations(row: IndicatorRowDict) -> InterpretationValuesDict:
    """Generate indicator interpretations from values.

    Args:
        row: Database row with indicator values

    Returns:
        Dict of interpretations
    """
    data: InterpretationValuesDict = {}

    rsi_val = row["rsi_14"]
    if rsi_val is not None:
        rsi = float(rsi_val)
        if rsi < 30:
            data["rsi"] = "oversold"
        elif rsi > 70:
            data["rsi"] = "overbought"
        else:
            data["rsi"] = "neutral"

    macd = row["macd_12_26_9_macd"]
    signal = row["macd_12_26_9_signal"]
    if macd is not None and signal is not None:
        if macd > signal:
            data["macd"] = "bullish_cross"
        elif macd < signal:
            data["macd"] = "bearish_cross"
        else:
            data["macd"] = "neutral"

    return data


def _build_response_from_row(row: dict) -> IndicatorsResponse:  # type: ignore[type-arg]
    """Build an IndicatorsResponse from a single database row dict."""
    indicators_dict = build_indicator_values(cast(IndicatorRowDict, row))
    interpretations_dict = generate_interpretations(cast(IndicatorRowDict, row))

    macd_data = indicators_dict.get("macd_12_26_9")
    bbands_data = indicators_dict.get("bbands_20_2")
    stoch_data = indicators_dict.get("stoch_14_3_3")

    return IndicatorsResponse(
        symbol=row["symbol"],
        date=str(row["date"]),
        close_price=row.get("close_price"),
        indicators=IndicatorValues(
            rsi_14=indicators_dict.get("rsi_14"),
            macd_12_26_9=MACDIndicator(**macd_data) if macd_data else None,
            bbands_20_2=BollingerBandsIndicator(**bbands_data) if bbands_data else None,
            sma_20=indicators_dict.get("sma_20"),
            sma_50=indicators_dict.get("sma_50"),
            sma_200=indicators_dict.get("sma_200"),
            ema_20=indicators_dict.get("ema_20"),
            ema_50=indicators_dict.get("ema_50"),
            ema_200=indicators_dict.get("ema_200"),
            atr_14=indicators_dict.get("atr_14"),
            stoch_14_3_3=StochasticIndicator(**stoch_data) if stoch_data else None,
        ),
        interpretations=IndicatorInterpretations(**interpretations_dict),
    )


def fetch_indicators_history(
    storage: object,
    symbol: str,
    start_date: str | None,
    end_date: str | None,
    limit: int,
) -> list[IndicatorsResponse]:
    """Fetch historical indicator data and return a list of response objects.

    Args:
        storage: Storage instance with query method
        symbol: Stock symbol
        start_date: Optional start date filter
        end_date: Optional end date filter
        limit: Maximum number of records

    Returns:
        List of IndicatorsResponse objects

    Raises:
        HTTPException 404: If no data is found for the symbol
        HTTPException 500: On unexpected errors
    """
    try:
        query, params = build_indicators_query(symbol, start_date, end_date, limit)
        df = storage.query(query, cast(list[ParameterValue], params))  # type: ignore[attr-defined]

        if df.is_empty():
            raise ValueError(
                f"No indicator data found for symbol {symbol}. "
                "Run the update_technical_indicators workflow first."
            )

        return [_build_response_from_row(row) for row in df.iter_rows(named=True)]

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving indicator history: {e!s}"
        ) from e
