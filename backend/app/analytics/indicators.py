"""Technical indicator calculation wrapper using pandas-ta.

This module provides functions for calculating common technical indicators
including RSI, MACD, Bollinger Bands, moving averages, ATR, and Stochastic.
"""

from __future__ import annotations

import datetime as dt
from importlib import import_module
from typing import TYPE_CHECKING, Any, cast

from app.logging_config import get_logger
from app.storage import PortfolioStorage, get_storage

if TYPE_CHECKING:
    import pandas as pd

pd = cast(Any, import_module("pandas"))
ta = cast(Any, import_module("pandas_ta"))

logger = get_logger(__name__)

# Default indicators to calculate when none specified
DEFAULT_INDICATORS = [
    "rsi",
    "macd",
    "bbands",
    "sma_5",  # Added for signal classifier (trend detection)
    "sma_20",
    "sma_50",
    "sma_200",
    "ema_20",
    "ema_50",
    "ema_200",
    "atr",
    "stoch",
    "volume_avg_20",  # Added for signal classifier (volume strength)
]


def _calculate_rsi(
    df: pd.DataFrame, indicators: list[str], indicator_values: dict[str, Any]
) -> None:
    """Calculate RSI indicator and add to indicator_values dict.

    Args:
        df: pandas DataFrame with OHLCV data
        indicators: List of requested indicators
        indicator_values: Dict to update with RSI value
    """
    if "rsi" in indicators:
        rsi = ta.rsi(df["close"], length=14)
        if rsi is not None and not rsi.empty:
            indicator_values["rsi_14"] = float(rsi.iloc[-1])
        else:
            indicator_values["rsi_14"] = None


def _calculate_macd(
    df: pd.DataFrame, indicators: list[str], indicator_values: dict[str, Any]
) -> None:
    """Calculate MACD indicator and add to indicator_values dict.

    Args:
        df: pandas DataFrame with OHLCV data
        indicators: List of requested indicators
        indicator_values: Dict to update with MACD values
    """
    if "macd" in indicators:
        macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            indicator_values["macd_12_26_9"] = {
                "macd": float(macd_df["MACD_12_26_9"].iloc[-1]),
                "signal": float(macd_df["MACDs_12_26_9"].iloc[-1]),
                "histogram": float(macd_df["MACDh_12_26_9"].iloc[-1]),
            }


def _calculate_bbands(
    df: pd.DataFrame, indicators: list[str], indicator_values: dict[str, Any]
) -> None:
    """Calculate Bollinger Bands and add to indicator_values dict.

    Args:
        df: pandas DataFrame with OHLCV data
        indicators: List of requested indicators
        indicator_values: Dict to update with BBands values
    """
    if "bbands" in indicators:
        bbands_df = ta.bbands(df["close"], length=20, std=2.0)
        if bbands_df is not None and not bbands_df.empty:
            indicator_values["bbands_20_2"] = {
                "upper": float(bbands_df["BBU_20_2.0_2.0"].iloc[-1]),
                "middle": float(bbands_df["BBM_20_2.0_2.0"].iloc[-1]),
                "lower": float(bbands_df["BBL_20_2.0_2.0"].iloc[-1]),
            }


def _calculate_moving_averages(
    df: pd.DataFrame, indicators: list[str], indicator_values: dict[str, Any]
) -> None:
    """Calculate all moving averages (SMA and EMA) and add to indicator_values dict.

    Args:
        df: pandas DataFrame with OHLCV data
        indicators: List of requested indicators
        indicator_values: Dict to update with moving average values
    """
    # Simple Moving Averages
    for length in [5, 20, 50, 200]:
        key = f"sma_{length}"
        if key in indicators:
            sma = ta.sma(df["close"], length=length)
            if sma is not None and not sma.empty:
                indicator_values[key] = float(sma.iloc[-1])
            else:
                indicator_values[key] = None

    # Exponential Moving Averages
    for length in [20, 50, 200]:
        key = f"ema_{length}"
        if key in indicators:
            ema = ta.ema(df["close"], length=length)
            if ema is not None and not ema.empty:
                indicator_values[key] = float(ema.iloc[-1])
            else:
                indicator_values[key] = None


def _calculate_atr(
    df: pd.DataFrame, indicators: list[str], indicator_values: dict[str, Any]
) -> None:
    """Calculate ATR indicator and add to indicator_values dict.

    Args:
        df: pandas DataFrame with OHLCV data
        indicators: List of requested indicators
        indicator_values: Dict to update with ATR value
    """
    if "atr" in indicators:
        atr = ta.atr(df["high"], df["low"], df["close"], length=14)
        if atr is not None and not atr.empty:
            indicator_values["atr_14"] = float(atr.iloc[-1])
        else:
            indicator_values["atr_14"] = None


def _calculate_stochastic(
    df: pd.DataFrame, indicators: list[str], indicator_values: dict[str, Any]
) -> None:
    """Calculate Stochastic oscillator and add to indicator_values dict.

    Args:
        df: pandas DataFrame with OHLCV data
        indicators: List of requested indicators
        indicator_values: Dict to update with Stochastic values
    """
    if "stoch" in indicators:
        stoch_df = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
        if stoch_df is not None and not stoch_df.empty:
            indicator_values["stoch_14_3_3"] = {
                "k": float(stoch_df["STOCHk_14_3_3"].iloc[-1]),
                "d": float(stoch_df["STOCHd_14_3_3"].iloc[-1]),
            }


def _calculate_volume_avg(
    df: pd.DataFrame, indicators: list[str], indicator_values: dict[str, Any]
) -> None:
    """Calculate volume moving averages and add to indicator_values dict.

    Args:
        df: pandas DataFrame with OHLCV data
        indicators: List of requested indicators
        indicator_values: Dict to update with volume average values
    """
    if "volume_avg_20" in indicators and "volume" in df.columns:
        volume_sma = ta.sma(df["volume"], length=20)
        if volume_sma is not None and not volume_sma.empty:
            indicator_values["volume_avg_20"] = float(volume_sma.iloc[-1])
        else:
            indicator_values["volume_avg_20"] = None


def _calculate_sma_prev(
    df: pd.DataFrame, indicators: list[str], indicator_values: dict[str, Any]
) -> None:
    """Calculate previous day's SMA values for trend detection.

    Required for signal classifier to detect declining trends (sma_5 vs sma_5_prev).

    Args:
        df: pandas DataFrame with OHLCV data
        indicators: List of requested indicators
        indicator_values: Dict to update with previous SMA values
    """
    # sma_5_prev: Previous day's SMA-5 (for trend detection)
    if "sma_5" in indicators and len(df) >= 6:  # Need at least 6 days for prev SMA-5
        sma_5_series = ta.sma(df["close"], length=5)
        if sma_5_series is not None and len(sma_5_series) >= 2:
            # Get second-to-last value (previous day's SMA-5)
            indicator_values["sma_5_prev"] = float(sma_5_series.iloc[-2])
        else:
            indicator_values["sma_5_prev"] = None
    else:
        indicator_values["sma_5_prev"] = None


def calculate_indicators(
    storage: PortfolioStorage,
    symbol: str,
    indicators: list[str] | None = None,
    as_of_date: dt.date | str | None = None,
) -> dict[str, Any]:
    """Calculate technical indicators for a symbol.

    Args:
        storage: PortfolioStorage instance for database access
        symbol: Stock symbol (e.g., "AAPL")
        indicators: List of indicator names to calculate. If None, uses DEFAULT_INDICATORS.
        as_of_date: Calculate indicators as of this date (default: latest available)

    Returns:
        Dict with symbol, date, indicators dict, and interpretations dict.
        See module docstring for detailed return structure.

    Raises:
        ValueError: If symbol has insufficient historical data (need 200+ days for SMA-200)

    Example:
        >>> storage = get_storage()
        >>> result = calculate_indicators(storage, "AAPL", ["rsi", "macd"])
        >>> if result["interpretations"]["rsi"] == "oversold":
        ...     print("RSI oversold - potential buy signal")
    """
    # Use default indicators if none specified
    if indicators is None:
        indicators = DEFAULT_INDICATORS

    # Fetch OHLCV data (need at least 200 days for SMA-200)
    df = _fetch_ohlcv_data(storage, symbol, lookback_days=250, as_of_date=as_of_date)

    if df.empty:
        raise ValueError(
            f"Insufficient data for symbol {symbol}. Need at least 200 days of OHLCV data."
        )

    return calculate_indicators_from_df(df, symbol, indicators)


def calculate_indicators_from_df(
    df: pd.DataFrame,
    symbol: str,
    indicators: list[str] | None = None,
) -> dict[str, Any]:
    """Calculate technical indicators from an existing DataFrame.

    Args:
        df: pandas DataFrame with OHLCV data (must be indexed by date)
        symbol: Stock symbol
        indicators: List of indicator names to calculate. If None, uses DEFAULT_INDICATORS.

    Returns:
        Dict with symbol, date, indicators dict, and interpretations dict.
    """
    # Use default indicators if none specified
    if indicators is None:
        indicators = DEFAULT_INDICATORS

    # Get the latest date in the dataset
    latest_date = df.index[-1]

    # Calculate all requested indicators
    indicator_values: dict[str, Any] = {}
    _calculate_rsi(df, indicators, indicator_values)
    _calculate_macd(df, indicators, indicator_values)
    _calculate_bbands(df, indicators, indicator_values)
    _calculate_moving_averages(df, indicators, indicator_values)
    _calculate_atr(df, indicators, indicator_values)
    _calculate_stochastic(df, indicators, indicator_values)
    _calculate_volume_avg(df, indicators, indicator_values)
    _calculate_sma_prev(df, indicators, indicator_values)

    # Add convenience keys for signal classifier compatibility
    # MACD: Extract float from dict (signal classifier expects float, not dict)
    if "macd_12_26_9" in indicator_values:
        indicator_values["macd"] = indicator_values["macd_12_26_9"]["macd"]

    # Generate interpretations
    interpretations = _interpret_indicators(indicator_values, df["close"].iloc[-1])

    return {
        "symbol": symbol,
        "date": latest_date.date() if hasattr(latest_date, "date") else latest_date,
        "indicators": indicator_values,
        "interpretations": interpretations,
    }


def _fetch_ohlcv_data(
    storage: PortfolioStorage,
    symbol: str,
    lookback_days: int = 250,
    as_of_date: dt.date | str | None = None,
) -> Any:
    """Fetch OHLCV data from day_bars table for indicator calculations.

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        lookback_days: Number of days to fetch (default: 250 for 200+ trading days)
        as_of_date: Fetch data up to this date (default: latest available)

    Returns:
        pandas DataFrame with columns [open, high, low, close, volume]
        indexed by date, sorted chronologically
    """
    # Build query (PostgreSQL uses $1, $2 style placeholders)
    if as_of_date is None:
        query = """
            SELECT date, open, high, low, close, volume
            FROM day_bars
            WHERE symbol = $1
            ORDER BY date DESC
            LIMIT $2
        """
        params: list[object] = [symbol, lookback_days]
    else:
        # Convert string to date if needed
        if isinstance(as_of_date, str):
            as_of_date = dt.date.fromisoformat(as_of_date)

        query = """
            SELECT date, open, high, low, close, volume
            FROM day_bars
            WHERE symbol = $1 AND date <= $2
            ORDER BY date DESC
            LIMIT $3
        """
        params = [symbol, str(as_of_date), lookback_days]

    # Execute query - PortfolioStorage.query() returns Polars DataFrame
    result_df = storage.query(query, params)

    if result_df.is_empty():
        logger.warning("no_ohlcv_data", symbol=symbol)
        return pd.DataFrame()

    # Convert Polars to pandas and set date index
    pandas_df = result_df.to_pandas()
    pandas_df["date"] = pd.to_datetime(pandas_df["date"])
    pandas_df = pandas_df.set_index("date")

    # Sort chronologically (oldest first) for indicator calculations
    pandas_df = pandas_df.sort_index()

    logger.info(
        "ohlcv_data_fetched",
        symbol=symbol,
        days=len(pandas_df),
        start_date=pandas_df.index[0].strftime("%Y-%m-%d"),
        end_date=pandas_df.index[-1].strftime("%Y-%m-%d"),
    )

    return pandas_df


def _interpret_indicators(indicators: dict[str, Any], current_price: float) -> dict[str, str]:
    """Generate human-readable interpretations of indicator values.

    Args:
        indicators: Dict of calculated indicator values
        current_price: Current closing price

    Returns:
        Dict of interpretations for each indicator
    """
    interpretations: dict[str, str] = {}

    # RSI interpretation
    if "rsi_14" in indicators and indicators["rsi_14"] is not None:
        rsi = indicators["rsi_14"]
        if rsi < 30:
            interpretations["rsi"] = "oversold"
        elif rsi > 70:
            interpretations["rsi"] = "overbought"
        else:
            interpretations["rsi"] = "neutral"

    # MACD interpretation
    if "macd_12_26_9" in indicators:
        macd_data = indicators["macd_12_26_9"]
        macd = macd_data["macd"]
        signal = macd_data["signal"]

        if macd > signal:
            interpretations["macd"] = "bullish_cross"
        elif macd < signal:
            interpretations["macd"] = "bearish_cross"
        else:
            interpretations["macd"] = "neutral"

    # Bollinger Bands position interpretation
    if "bbands_20_2" in indicators:
        bbands = indicators["bbands_20_2"]
        upper = bbands["upper"]
        lower = bbands["lower"]

        # Calculate position within bands
        band_width = upper - lower
        distance_from_lower = current_price - lower
        position_pct = (distance_from_lower / band_width) * 100 if band_width > 0 else 50

        if position_pct < 20:
            interpretations["bbands_position"] = "near_lower"
        elif position_pct > 80:
            interpretations["bbands_position"] = "near_upper"
        else:
            interpretations["bbands_position"] = "middle"

    # Price vs SMA-200 (trend indicator)
    if "sma_200" in indicators and indicators["sma_200"] is not None:
        sma_200 = indicators["sma_200"]
        if current_price > sma_200:
            interpretations["price_vs_sma_200"] = "above"
        else:
            interpretations["price_vs_sma_200"] = "below"

    # Stochastic interpretation
    if "stoch_14_3_3" in indicators:
        stoch = indicators["stoch_14_3_3"]
        k = stoch["k"]

        if k < 20:
            interpretations["stoch"] = "oversold"
        elif k > 80:
            interpretations["stoch"] = "overbought"
        else:
            interpretations["stoch"] = "neutral"

    return interpretations


def calculate_indicators_for_symbol(
    symbol: str, indicators: list[str] | None = None, as_of_date: dt.date | str | None = None
) -> dict[str, Any]:
    """Calculate technical indicators for a symbol (wrapper function).

    Convenience wrapper that uses the singleton PortfolioStorage
    and calls calculate_indicators.

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        indicators: List of indicator names to calculate. If None, uses DEFAULT_INDICATORS.
        as_of_date: Calculate indicators as of this date (default: latest available)

    Returns:
        Dict with symbol, date, indicators dict, and interpretations dict.

    Raises:
        ValueError: If symbol not found or insufficient data
    """
    storage = get_storage()
    return calculate_indicators(storage, symbol, indicators, as_of_date)
