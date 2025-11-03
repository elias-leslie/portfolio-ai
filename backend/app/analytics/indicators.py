"""Technical indicator calculation wrapper using pandas-ta.

This module provides functions for calculating common technical indicators
including RSI, MACD, Bollinger Bands, moving averages, ATR, and Stochastic.
"""

from __future__ import annotations

import datetime as dt
from importlib import import_module
from typing import Any, cast

from app.logging_config import get_logger
from app.storage import DuckDBStorage

pd = cast(Any, import_module("pandas"))
ta = cast(Any, import_module("pandas_ta"))

logger = get_logger(__name__)


def calculate_indicators(
    storage: DuckDBStorage,
    ticker: str,
    indicators: list[str] | None = None,
    as_of_date: dt.date | str | None = None,
) -> dict[str, Any]:
    """Calculate technical indicators for a ticker.

    Fetches OHLCV data from the day_bars table and calculates requested
    technical indicators using pandas-ta. Returns indicator values with
    interpretations (e.g., "oversold", "bullish_cross").

    Args:
        storage: DuckDBStorage instance for database access
        ticker: Stock ticker symbol (e.g., "AAPL")
        indicators: List of indicator names to calculate. If None, calculates all.
            Supported: ["rsi", "macd", "bbands", "sma_20", "sma_50", "sma_200",
                       "ema_20", "ema_50", "ema_200", "atr", "stoch"]
        as_of_date: Calculate indicators as of this date (default: latest available)

    Returns:
        Dict with indicator values and interpretations:
        {
            "ticker": "AAPL",
            "date": "2025-01-15",
            "indicators": {
                "rsi_14": 32.5,
                "macd_12_26_9": {"macd": 1.2, "signal": 0.8, "histogram": 0.4},
                "bbands_20_2": {"upper": 182.5, "middle": 180.0, "lower": 177.5},
                "sma_20": 179.5,
                "sma_50": 175.0,
                "sma_200": 170.0,
                "ema_20": 179.8,
                "ema_50": 175.5,
                "ema_200": 170.5,
                "atr_14": 3.5,
                "stoch_14_3_3": {"k": 25.0, "d": 22.0}
            },
            "interpretations": {
                "rsi": "oversold",
                "macd": "bullish_cross",
                "bbands_position": "near_lower",
                "price_vs_sma_200": "above"
            }
        }

    Raises:
        ValueError: If ticker has insufficient historical data (need 200+ days for SMA-200)

    Example:
        >>> storage = get_storage()
        >>> result = calculate_indicators(storage, "AAPL", ["rsi", "macd"])
        >>> if result["interpretations"]["rsi"] == "oversold":
        ...     print("RSI oversold - potential buy signal")
    """
    # Default to all indicators if none specified
    if indicators is None:
        indicators = [
            "rsi",
            "macd",
            "bbands",
            "sma_20",
            "sma_50",
            "sma_200",
            "ema_20",
            "ema_50",
            "ema_200",
            "atr",
            "stoch",
        ]

    # Fetch OHLCV data (need at least 200 days for SMA-200)
    df = _fetch_ohlcv_data(storage, ticker, lookback_days=250, as_of_date=as_of_date)

    if df.empty:
        raise ValueError(
            f"Insufficient data for ticker {ticker}. Need at least 200 days of OHLCV data."
        )

    # Get the latest date in the dataset
    latest_date = df.index[-1]

    # Calculate indicators
    indicator_values: dict[str, Any] = {}

    if "rsi" in indicators:
        rsi = ta.rsi(df["close"], length=14)
        indicator_values["rsi_14"] = float(rsi.iloc[-1]) if not rsi.empty else None

    if "macd" in indicators:
        macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            indicator_values["macd_12_26_9"] = {
                "macd": float(macd_df["MACD_12_26_9"].iloc[-1]),
                "signal": float(macd_df["MACDs_12_26_9"].iloc[-1]),
                "histogram": float(macd_df["MACDh_12_26_9"].iloc[-1]),
            }

    if "bbands" in indicators:
        bbands_df = ta.bbands(df["close"], length=20, std=2.0)
        if bbands_df is not None and not bbands_df.empty:
            # pandas-ta column names: BBL_20_2.0_2.0, BBM_20_2.0_2.0, BBU_20_2.0_2.0
            indicator_values["bbands_20_2"] = {
                "upper": float(bbands_df["BBU_20_2.0_2.0"].iloc[-1]),
                "middle": float(bbands_df["BBM_20_2.0_2.0"].iloc[-1]),
                "lower": float(bbands_df["BBL_20_2.0_2.0"].iloc[-1]),
            }

    # Moving averages
    if "sma_5" in indicators:
        sma_5 = ta.sma(df["close"], length=5)
        indicator_values["sma_5"] = float(sma_5.iloc[-1]) if not sma_5.empty else None

    if "sma_20" in indicators:
        sma_20 = ta.sma(df["close"], length=20)
        indicator_values["sma_20"] = float(sma_20.iloc[-1]) if not sma_20.empty else None

    if "sma_50" in indicators:
        sma_50 = ta.sma(df["close"], length=50)
        indicator_values["sma_50"] = float(sma_50.iloc[-1]) if not sma_50.empty else None

    if "sma_200" in indicators:
        sma_200 = ta.sma(df["close"], length=200)
        indicator_values["sma_200"] = float(sma_200.iloc[-1]) if not sma_200.empty else None

    if "ema_20" in indicators:
        ema_20 = ta.ema(df["close"], length=20)
        indicator_values["ema_20"] = float(ema_20.iloc[-1]) if not ema_20.empty else None

    if "ema_50" in indicators:
        ema_50 = ta.ema(df["close"], length=50)
        indicator_values["ema_50"] = float(ema_50.iloc[-1]) if not ema_50.empty else None

    if "ema_200" in indicators:
        ema_200 = ta.ema(df["close"], length=200)
        indicator_values["ema_200"] = float(ema_200.iloc[-1]) if not ema_200.empty else None

    if "atr" in indicators:
        atr = ta.atr(df["high"], df["low"], df["close"], length=14)
        indicator_values["atr_14"] = float(atr.iloc[-1]) if not atr.empty else None

    if "stoch" in indicators:
        stoch_df = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
        if stoch_df is not None and not stoch_df.empty:
            indicator_values["stoch_14_3_3"] = {
                "k": float(stoch_df["STOCHk_14_3_3"].iloc[-1]),
                "d": float(stoch_df["STOCHd_14_3_3"].iloc[-1]),
            }

    # Generate interpretations
    interpretations = _interpret_indicators(indicator_values, df["close"].iloc[-1])

    return {
        "ticker": ticker,
        "date": latest_date.strftime("%Y-%m-%d"),
        "indicators": indicator_values,
        "interpretations": interpretations,
    }


def _fetch_ohlcv_data(
    storage: DuckDBStorage,
    ticker: str,
    lookback_days: int = 250,
    as_of_date: dt.date | str | None = None,
) -> Any:
    """Fetch OHLCV data from day_bars table for indicator calculations.

    Args:
        storage: DuckDBStorage instance
        ticker: Stock ticker symbol
        lookback_days: Number of days to fetch (default: 250 for 200+ trading days)
        as_of_date: Fetch data up to this date (default: latest available)

    Returns:
        pandas DataFrame with columns [open, high, low, close, volume]
        indexed by date, sorted chronologically
    """
    # Build query
    if as_of_date is None:
        query = """
            SELECT date, open, high, low, close, volume
            FROM day_bars
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT ?
        """
        params = [ticker, lookback_days]
    else:
        # Convert string to date if needed
        if isinstance(as_of_date, str):
            as_of_date = dt.date.fromisoformat(as_of_date)

        query = """
            SELECT date, open, high, low, close, volume
            FROM day_bars
            WHERE ticker = ? AND date <= ?
            ORDER BY date DESC
            LIMIT ?
        """
        params = [ticker, as_of_date, lookback_days]

    # Execute query
    result_df = storage.query(query, params)

    if result_df.is_empty():
        logger.warning(f"No OHLCV data found for ticker {ticker}")
        return pd.DataFrame()

    # Convert to pandas and set date index
    pandas_df = result_df.to_pandas()
    pandas_df["date"] = pd.to_datetime(pandas_df["date"])
    pandas_df = pandas_df.set_index("date")

    # Sort chronologically (oldest first) for indicator calculations
    pandas_df = pandas_df.sort_index()

    logger.info(
        f"Fetched {len(pandas_df)} days of OHLCV data for {ticker}",
        extra={
            "ticker": ticker,
            "days": len(pandas_df),
            "start_date": pandas_df.index[0].strftime("%Y-%m-%d"),
            "end_date": pandas_df.index[-1].strftime("%Y-%m-%d"),
        },
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
