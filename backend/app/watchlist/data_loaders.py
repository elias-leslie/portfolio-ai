"""Data loaders for watchlist service.

Helper functions for loading technical indicators, preferences, and related data.
"""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from .models import ScoreWeights, TechnicalSnapshot

logger = get_logger(__name__)


def load_latest_technical(
    storage: PortfolioStorage, symbols: list[str]
) -> dict[str, TechnicalSnapshot]:
    """Load latest technical indicators for symbols.

    Args:
        storage: PortfolioStorage instance
        symbols: List of ticker symbols

    Returns:
        Dict mapping ticker symbol to TechnicalSnapshot
    """
    if not symbols:
        return {}

    placeholders = ",".join(["?"] * len(symbols))
    df = storage.query(
        f"""
        SELECT *
        FROM technical_indicators
        WHERE ticker IN ({placeholders})
        ORDER BY ticker, date DESC
        """,
        symbols,  # type: ignore[arg-type]
    )

    if df.is_empty():
        return {}

    grouped = df.group_by("ticker").agg(pl.all().first())
    snapshots: dict[str, TechnicalSnapshot] = {}
    for row in grouped.iter_rows(named=True):
        calculated_at = row.get("calculated_at")
        if isinstance(calculated_at, datetime) and calculated_at.tzinfo is None:
            calculated_at = calculated_at.replace(tzinfo=UTC)
        snapshots[row["ticker"]] = TechnicalSnapshot(
            rsi_14=row.get("rsi_14"),
            sma_20=row.get("sma_20"),
            sma_5=row.get("sma_5"),
            sma_50=row.get("sma_50"),
            sma_200=row.get("sma_200"),
            ema_20=row.get("ema_20"),
            ema_50=row.get("ema_50"),
            ema_200=row.get("ema_200"),
            macd=row.get("macd"),
            macd_signal=row.get("macd_signal"),
            price=None,
            calculated_at=calculated_at,
        )
    return snapshots


def load_default_weights(storage: PortfolioStorage) -> ScoreWeights:
    """Load default score weights from user preferences.

    Args:
        storage: PortfolioStorage instance

    Returns:
        ScoreWeights with price and technical weights
    """
    df = storage.query(
        """
        SELECT watchlist_price_weight, watchlist_technical_weight
        FROM user_preferences
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    if df.is_empty():
        return ScoreWeights()

    row = df.to_dicts()[0]
    return ScoreWeights(
        price=row.get("watchlist_price_weight", 50.0) or 0.0,
        technical=row.get("watchlist_technical_weight", 50.0) or 0.0,
    )


def load_stale_ttl_minutes(storage: PortfolioStorage) -> int:
    """Load stale TTL from preferences (3x refresh interval).

    Args:
        storage: PortfolioStorage instance

    Returns:
        TTL in minutes for stale score detection
    """
    df = storage.query(
        """
        SELECT watchlist_refresh_override, default_refresh_minutes
        FROM user_preferences
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )

    if df.is_empty():
        # Default: 3x of 15 minutes = 45 minutes
        return 45

    row = df.to_dicts()[0]
    refresh_minutes = row.get("watchlist_refresh_override") or row.get(
        "default_refresh_minutes", 15
    )

    # Stale = 3x refresh interval
    return int(refresh_minutes * 3) if refresh_minutes else 45


def load_risk_budget(storage: PortfolioStorage) -> float:
    """Load risk budget from preferences.

    Args:
        storage: PortfolioStorage instance

    Returns:
        Risk budget as decimal (e.g., 0.02 for 2%)
    """
    df = storage.query(
        """
        SELECT risk_budget_pct
        FROM user_preferences
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )

    if df.is_empty():
        return 0.02  # Default 2%

    row = df.to_dicts()[0]
    risk_budget_pct = row.get("risk_budget_pct")
    if risk_budget_pct is None:
        return 0.02

    # Convert percentage to decimal
    return float(risk_budget_pct) / 100.0


def calculate_price_change(
    storage: PortfolioStorage, symbol: str, current_price: float
) -> tuple[float | None, float | None]:
    """Calculate 1-day and 5-day price changes.

    Args:
        storage: PortfolioStorage instance
        symbol: Ticker symbol
        current_price: Current price

    Returns:
        Tuple of (1-day change %, 5-day change %)
    """
    df = storage.query(
        """
        SELECT date, close
        FROM day_bars
        WHERE ticker = ?
        ORDER BY date DESC
        LIMIT 6
        """,
        [symbol],
    )

    if df.is_empty():
        return None, None

    rows = df.to_dicts()

    # Calculate 1-day change (today vs yesterday's close)
    change_1d = None
    if len(rows) >= 1:
        yesterday_close = rows[0]["close"]
        change_1d = ((current_price - yesterday_close) / yesterday_close) * 100

    # Calculate 5-day change (today vs 5 days ago close)
    change_5d = None
    if len(rows) >= 5:
        five_days_ago_close = rows[4]["close"]
        change_5d = ((current_price - five_days_ago_close) / five_days_ago_close) * 100

    return change_1d, change_5d
