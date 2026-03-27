"""Technical indicator calculation wrapper using pandas-ta."""

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

DEFAULT_INDICATORS = [
    "rsi",
    "macd",
    "bbands",
    "sma_5",
    "sma_20",
    "sma_50",
    "sma_200",
    "ema_20",
    "ema_50",
    "ema_200",
    "atr",
    "stoch",
    "volume_avg_20",
]


def _series_last(series: Any) -> float | None:
    """Return last float value of a series, or None if empty/None."""
    if series is not None and not series.empty:
        return float(series.iloc[-1])
    return None


def _calculate_rsi(df: pd.DataFrame, indicators: list[str], out: dict[str, Any]) -> None:
    if "rsi" in indicators:
        out["rsi_14"] = _series_last(ta.rsi(df["close"], length=14))

def _calculate_macd(df: pd.DataFrame, indicators: list[str], out: dict[str, Any]) -> None:
    if "macd" in indicators:
        macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            out["macd_12_26_9"] = {
                "macd": float(macd_df["MACD_12_26_9"].iloc[-1]),
                "signal": float(macd_df["MACDs_12_26_9"].iloc[-1]),
                "histogram": float(macd_df["MACDh_12_26_9"].iloc[-1]),
            }

def _calculate_bbands(df: pd.DataFrame, indicators: list[str], out: dict[str, Any]) -> None:
    if "bbands" in indicators:
        bbands_df = ta.bbands(df["close"], length=20, std=2.0)
        if bbands_df is not None and not bbands_df.empty:
            out["bbands_20_2"] = {
                "upper": float(bbands_df["BBU_20_2.0_2.0"].iloc[-1]),
                "middle": float(bbands_df["BBM_20_2.0_2.0"].iloc[-1]),
                "lower": float(bbands_df["BBL_20_2.0_2.0"].iloc[-1]),
            }

def _calculate_moving_averages(
    df: pd.DataFrame, indicators: list[str], out: dict[str, Any]
) -> None:
    for length in [5, 20, 50, 200]:
        key = f"sma_{length}"
        if key in indicators:
            out[key] = _series_last(ta.sma(df["close"], length=length))
    for length in [20, 50, 200]:
        key = f"ema_{length}"
        if key in indicators:
            out[key] = _series_last(ta.ema(df["close"], length=length))

def _calculate_atr(df: pd.DataFrame, indicators: list[str], out: dict[str, Any]) -> None:
    if "atr" in indicators:
        out["atr_14"] = _series_last(ta.atr(df["high"], df["low"], df["close"], length=14))

def _calculate_stochastic(df: pd.DataFrame, indicators: list[str], out: dict[str, Any]) -> None:
    if "stoch" in indicators:
        stoch_df = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
        if stoch_df is not None and not stoch_df.empty:
            out["stoch_14_3_3"] = {
                "k": float(stoch_df["STOCHk_14_3_3"].iloc[-1]),
                "d": float(stoch_df["STOCHd_14_3_3"].iloc[-1]),
            }

def _calculate_volume_avg(df: pd.DataFrame, indicators: list[str], out: dict[str, Any]) -> None:
    if "volume_avg_20" in indicators and "volume" in df.columns:
        out["volume_avg_20"] = _series_last(ta.sma(df["volume"], length=20))

def _calculate_sma_prev(df: pd.DataFrame, indicators: list[str], out: dict[str, Any]) -> None:
    if "sma_5" in indicators and len(df) >= 6:
        sma_5_series = ta.sma(df["close"], length=5)
        if sma_5_series is not None and len(sma_5_series) >= 2:
            out["sma_5_prev"] = float(sma_5_series.iloc[-2])
            return
    out["sma_5_prev"] = None


def _build_query(as_of_date: dt.date | str | None, lookback_days: int) -> tuple[str, list[object]]:
    """Return (query, params) for OHLCV fetch."""
    base = "SELECT date, open, high, low, close, volume FROM day_bars WHERE symbol = $1"
    if as_of_date is None:
        return f"{base} ORDER BY date DESC LIMIT $2", [lookback_days]
    if isinstance(as_of_date, str):
        as_of_date = dt.date.fromisoformat(as_of_date)
    return f"{base} AND date <= $2 ORDER BY date DESC LIMIT $3", [str(as_of_date), lookback_days]


def _fetch_ohlcv_data(
    storage: PortfolioStorage,
    symbol: str,
    lookback_days: int = 250,
    as_of_date: dt.date | str | None = None,
) -> Any:
    """Fetch OHLCV data from day_bars table, returns pandas DataFrame indexed by date."""
    query, extra_params = _build_query(as_of_date, lookback_days)
    params: list[object] = [symbol, *extra_params]
    result_df = storage.query(query, params)

    if result_df.is_empty():
        logger.warning("no_ohlcv_data", symbol=symbol)
        return pd.DataFrame()

    pandas_df = result_df.to_pandas()
    pandas_df["date"] = pd.to_datetime(pandas_df["date"])
    pandas_df = pandas_df.set_index("date").sort_index()

    logger.info(
        "ohlcv_data_fetched",
        symbol=symbol,
        days=len(pandas_df),
        start_date=pandas_df.index[0].strftime("%Y-%m-%d"),
        end_date=pandas_df.index[-1].strftime("%Y-%m-%d"),
    )
    return pandas_df


def _interp_rsi(indicators: dict[str, Any], out: dict[str, str]) -> None:
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        out["rsi"] = "oversold" if rsi < 30 else "overbought" if rsi > 70 else "neutral"

def _interp_macd(indicators: dict[str, Any], out: dict[str, str]) -> None:
    if "macd_12_26_9" in indicators:
        macd_data = indicators["macd_12_26_9"]
        macd, signal = macd_data["macd"], macd_data["signal"]
        out["macd"] = "bullish_cross" if macd > signal else "bearish_cross" if macd < signal else "neutral"

def _interp_bbands(indicators: dict[str, Any], current_price: float, out: dict[str, str]) -> None:
    if "bbands_20_2" in indicators:
        upper, lower = indicators["bbands_20_2"]["upper"], indicators["bbands_20_2"]["lower"]
        band_width = upper - lower
        pos = ((current_price - lower) / band_width * 100) if band_width > 0 else 50
        out["bbands_position"] = "near_lower" if pos < 20 else "near_upper" if pos > 80 else "middle"

def _interp_sma200(indicators: dict[str, Any], current_price: float, out: dict[str, str]) -> None:
    sma_200 = indicators.get("sma_200")
    if sma_200 is not None:
        out["price_vs_sma_200"] = "above" if current_price > sma_200 else "below"

def _interp_stoch(indicators: dict[str, Any], out: dict[str, str]) -> None:
    if "stoch_14_3_3" in indicators:
        k = indicators["stoch_14_3_3"]["k"]
        out["stoch"] = "oversold" if k < 20 else "overbought" if k > 80 else "neutral"

def _interpret_indicators(indicators: dict[str, Any], current_price: float) -> dict[str, str]:
    """Generate human-readable interpretations of indicator values."""
    out: dict[str, str] = {}
    _interp_rsi(indicators, out)
    _interp_macd(indicators, out)
    _interp_bbands(indicators, current_price, out)
    _interp_sma200(indicators, current_price, out)
    _interp_stoch(indicators, out)
    return out


def calculate_indicators(
    storage: PortfolioStorage,
    symbol: str,
    indicators: list[str] | None = None,
    as_of_date: dt.date | str | None = None,
) -> dict[str, Any]:
    """Calculate technical indicators for a symbol.

    Returns dict with symbol, date, indicators, and interpretations.
    Raises ValueError if insufficient historical data.
    """
    if indicators is None:
        indicators = DEFAULT_INDICATORS
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
    """Calculate technical indicators from an existing DataFrame."""
    if indicators is None:
        indicators = DEFAULT_INDICATORS

    latest_date = df.index[-1]
    indicator_values: dict[str, Any] = {}
    _calculate_rsi(df, indicators, indicator_values)
    _calculate_macd(df, indicators, indicator_values)
    _calculate_bbands(df, indicators, indicator_values)
    _calculate_moving_averages(df, indicators, indicator_values)
    _calculate_atr(df, indicators, indicator_values)
    _calculate_stochastic(df, indicators, indicator_values)
    _calculate_volume_avg(df, indicators, indicator_values)
    _calculate_sma_prev(df, indicators, indicator_values)

    if "macd_12_26_9" in indicator_values:
        indicator_values["macd"] = indicator_values["macd_12_26_9"]["macd"]

    interpretations = _interpret_indicators(indicator_values, df["close"].iloc[-1])
    return {
        "symbol": symbol,
        "date": latest_date.date() if hasattr(latest_date, "date") else latest_date,
        "indicators": indicator_values,
        "interpretations": interpretations,
    }


def calculate_indicators_for_symbol(
    symbol: str, indicators: list[str] | None = None, as_of_date: dt.date | str | None = None
) -> dict[str, Any]:
    """Calculate technical indicators for a symbol using singleton storage."""
    storage = get_storage()
    return calculate_indicators(storage, symbol, indicators, as_of_date)
