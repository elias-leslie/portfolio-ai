"""Research and market data query helpers for portfolio storage."""

from __future__ import annotations

from collections.abc import Callable

import polars as pl

# Type alias for the query callable
QueryFn = Callable[..., pl.DataFrame]


def get_news_data(query: QueryFn, symbol: str, start_date: str, end_date: str) -> pl.DataFrame:
    """Fetch news articles from the cache.

    Args:
        query: Query function accepting (sql, params)
        symbol: Stock symbol
        start_date: Start of lookback period (YYYY-MM-DD)
        end_date: End of lookback period (YYYY-MM-DD)

    Returns:
        DataFrame with sentiment_score, published_at, headline
    """
    sql = """
        SELECT
            sentiment_score,
            published_at,
            headline
        FROM news_cache
        WHERE symbol = %s
          AND published_at >= %s
          AND published_at <= %s
        ORDER BY published_at DESC
    """
    return query(sql, [symbol, start_date, end_date])


def get_ohlcv_data(query: QueryFn, symbol: str, limit: int = 60) -> pl.DataFrame:
    """Fetch OHLCV data for trend analysis.

    Args:
        query: Query function accepting (sql, params)
        symbol: Stock symbol
        limit: Number of bars to fetch (default 60)

    Returns:
        DataFrame with date, close, volume
    """
    sql = """
        SELECT date, close, volume
        FROM day_bars
        WHERE symbol = %s
        ORDER BY date DESC
        LIMIT %s
    """
    return query(sql, [symbol, limit])


def get_current_price(query: QueryFn, symbol: str) -> float | None:
    """Get current price for a symbol.

    Args:
        query: Query function accepting (sql, params)
        symbol: Stock symbol

    Returns:
        Current close price or None
    """
    sql = """
        SELECT close
        FROM day_bars
        WHERE symbol = %s
        ORDER BY date DESC
        LIMIT 1
    """
    df = query(sql, [symbol])
    if df.is_empty():
        return None
    return float(df["close"][0])


def get_bar_count(query: QueryFn, symbol: str) -> int:
    """Get total bar count for a symbol.

    Args:
        query: Query function accepting (sql, params)
        symbol: Stock symbol

    Returns:
        Number of bars available
    """
    sql = "SELECT COUNT(*) as count FROM day_bars WHERE symbol = %s"
    df = query(sql, [symbol])
    if df.is_empty():
        return 0
    return int(df["count"][0])


def get_fear_greed_latest(query: QueryFn) -> dict[str, int]:
    """Get latest Fear & Greed data.

    Args:
        query: Query function accepting (sql,)

    Returns:
        Dict with score and signal_count
    """
    sql = """
        SELECT score, signal_count
        FROM fear_greed_daily
        ORDER BY as_of_date DESC
        LIMIT 1
    """
    df = query(sql)
    if df.is_empty():
        return {"score": 50, "signal_count": 0}
    return {"score": int(df["score"][0]), "signal_count": int(df["signal_count"][0])}


def get_spy_and_vix_data(query: QueryFn) -> dict[str, float]:
    """Get latest SPY and VIX prices.

    Args:
        query: Query function accepting (sql,)

    Returns:
        Dict with spy_close and vix_close
    """
    spy_sql = """
        SELECT close
        FROM day_bars
        WHERE symbol = 'SPY'
        ORDER BY date DESC
        LIMIT 1
    """
    vix_sql = """
        SELECT close as vix_close
        FROM day_bars
        WHERE symbol = '^VIX'
        ORDER BY date DESC
        LIMIT 1
    """
    spy_df = query(spy_sql)
    vix_df = query(vix_sql)
    return {
        "spy_close": float(spy_df["close"][0]) if not spy_df.is_empty() else 450.0,
        "vix_close": float(vix_df["vix_close"][0]) if not vix_df.is_empty() else 15.0,
    }


def get_symbol_sector(query: QueryFn, symbol: str) -> str:
    """Get sector for a symbol from watchlist metadata.

    Args:
        query: Query function accepting (sql, params)
        symbol: Stock symbol

    Returns:
        Sector name or "Unknown"
    """
    sql = """
        SELECT metadata
        FROM watchlist_items
        WHERE symbol = %s
        LIMIT 1
    """
    df = query(sql, [symbol])
    if df.is_empty():
        return "Unknown"
    metadata = df["metadata"][0]
    if isinstance(metadata, dict):
        return str(metadata.get("sector", "Unknown"))
    return "Unknown"
