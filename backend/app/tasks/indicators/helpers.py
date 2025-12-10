"""Helper functions for technical indicator calculations.

This module contains shared utilities for building indicator data structures
and database operations.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, TypedDict

from app.logging_config import get_logger
from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


class IndicatorDataDict(TypedDict, total=False):
    """Technical indicator data dictionary for database insertion."""

    symbol: str
    date: dt.date
    rsi_14: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    bb_upper: float | None
    bb_middle: float | None
    bb_lower: float | None
    sma_5: float | None
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    ema_20: float | None
    ema_50: float | None
    ema_200: float | None
    atr_14: float | None
    stoch_k: float | None
    stoch_d: float | None
    calculated_at: dt.datetime


def build_indicator_data(
    symbol: str, indicators: dict[str, Any], date: dt.date
) -> IndicatorDataDict:
    """Build indicator data dictionary for database insertion.

    Args:
        symbol: Stock symbol
        indicators: Calculated indicators dictionary
        date: Date of the indicator values

    Returns:
        Dictionary with all indicator fields ready for database insertion
    """
    return {
        "symbol": symbol,
        "date": date,
        "rsi_14": indicators.get("rsi_14"),
        "macd": indicators.get("macd_12_26_9", {}).get("macd"),
        "macd_signal": indicators.get("macd_12_26_9", {}).get("signal"),
        "macd_histogram": indicators.get("macd_12_26_9", {}).get("histogram"),
        "bb_upper": indicators.get("bbands_20_2", {}).get("upper"),
        "bb_middle": indicators.get("bbands_20_2", {}).get("middle"),
        "bb_lower": indicators.get("bbands_20_2", {}).get("lower"),
        "sma_5": indicators.get("sma_5"),
        "sma_20": indicators.get("sma_20"),
        "sma_50": indicators.get("sma_50"),
        "sma_200": indicators.get("sma_200"),
        "ema_20": indicators.get("ema_20"),
        "ema_50": indicators.get("ema_50"),
        "ema_200": indicators.get("ema_200"),
        "atr_14": indicators.get("atr_14"),
        "stoch_k": indicators.get("stoch_14_3_3", {}).get("k"),
        "stoch_d": indicators.get("stoch_14_3_3", {}).get("d"),
        "calculated_at": dt.datetime.now(dt.UTC),
    }


def upsert_indicators(storage: PortfolioStorage, indicator_data: IndicatorDataDict) -> None:
    """Insert or update technical indicators in database.

    Uses PostgreSQL UPSERT (ON CONFLICT) to update existing records
    or insert new ones based on (symbol, date) unique constraint.

    Args:
        storage: Storage instance with connection context manager
        indicator_data: Dictionary containing all indicator fields
    """
    with storage.connection() as conn:
        # Ensure symbol exists in symbols table (FK constraint)
        conn.execute(
            """
            INSERT INTO symbols (symbol, security_type, created_at)
            VALUES (%s, 'equity', NOW())
            ON CONFLICT (symbol) DO NOTHING
            """,
            [indicator_data["symbol"]],
        )
        conn.execute(
            """
            INSERT INTO technical_indicators (
                symbol, date, rsi_14, macd, macd_signal, macd_histogram,
                bb_upper, bb_middle, bb_lower,
                sma_5, sma_20, sma_50, sma_200,
                ema_20, ema_50, ema_200,
                atr_14, stoch_k, stoch_d,
                calculated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?
            )
            ON CONFLICT (symbol, date) DO UPDATE SET
                rsi_14 = EXCLUDED.rsi_14,
                macd = EXCLUDED.macd,
                macd_signal = EXCLUDED.macd_signal,
                macd_histogram = EXCLUDED.macd_histogram,
                bb_upper = EXCLUDED.bb_upper,
                bb_middle = EXCLUDED.bb_middle,
                bb_lower = EXCLUDED.bb_lower,
                sma_5 = EXCLUDED.sma_5,
                sma_20 = EXCLUDED.sma_20,
                sma_50 = EXCLUDED.sma_50,
                sma_200 = EXCLUDED.sma_200,
                ema_20 = EXCLUDED.ema_20,
                ema_50 = EXCLUDED.ema_50,
                ema_200 = EXCLUDED.ema_200,
                atr_14 = EXCLUDED.atr_14,
                stoch_k = EXCLUDED.stoch_k,
                stoch_d = EXCLUDED.stoch_d,
                calculated_at = EXCLUDED.calculated_at
            """,
            [
                indicator_data["symbol"],
                indicator_data["date"].isoformat(),
                indicator_data["rsi_14"],
                indicator_data["macd"],
                indicator_data["macd_signal"],
                indicator_data["macd_histogram"],
                indicator_data["bb_upper"],
                indicator_data["bb_middle"],
                indicator_data["bb_lower"],
                indicator_data["sma_5"],
                indicator_data["sma_20"],
                indicator_data["sma_50"],
                indicator_data["sma_200"],
                indicator_data["ema_20"],
                indicator_data["ema_50"],
                indicator_data["ema_200"],
                indicator_data["atr_14"],
                indicator_data["stoch_k"],
                indicator_data["stoch_d"],
                indicator_data["calculated_at"],
            ],
        )
        conn.commit()
