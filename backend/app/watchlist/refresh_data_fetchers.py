"""Data fetching functions for watchlist refresh operations.

This module handles all data fetching operations including:
- Fundamental data and earnings information
- Volume data and historical bars
- News sentiment and intelligence
- Price change calculations
- Historical data backfill detection

Extracted from refresh_processor.py to improve modularity.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..logging_config import get_logger
from ..services import NewsService
from ..services.news_models import NewsBundle
from ..storage import PortfolioStorage
from .earnings import fetch_earnings_date_cached
from .fundamentals import (
    FundamentalData,
    calculate_fundamental_score,
    calculate_growth_score,
    calculate_health_score,
    calculate_sentiment_score,
    calculate_valuation_score,
    classify_company_health,
    fetch_fundamentals_cached,
)

logger = get_logger(__name__)

WATCHLIST_NEWS_ARTICLE_LIMIT = 5


def calculate_price_change(
    storage: PortfolioStorage, symbol: str, price: float | None, item_id: str | None = None
) -> tuple[float | None, bool]:
    """Calculate price change percentage for a symbol.

    First tries to calculate from day_bars historical data (preferred).
    Falls back to previous watchlist snapshot if available.

    Args:
        storage: PortfolioStorage instance
        symbol: Ticker symbol
        price: Current price
        item_id: Watchlist item ID (for snapshot fallback)

    Returns:
        Tuple of (change_pct, has_historical_data):
        - change_pct: Price change percentage or None if insufficient data
        - has_historical_data: True if day_bars data exists (False triggers backfill)
    """
    if price is None or price <= 0:
        return (None, False)

    # Try day_bars historical data first (preferred)
    df = storage.query(
        """
        SELECT close
        FROM day_bars
        WHERE ticker = ?
        ORDER BY date DESC
        LIMIT 2
        """,
        [symbol],
    )
    if df.height >= 2:
        prev_close = df["close"][1]
        if prev_close not in (0, None):
            return (float((price - prev_close) / prev_close * 100.0), True)

    # Fallback: Use previous watchlist snapshot if available
    if item_id:
        snapshot_df = storage.query(
            """
            SELECT price
            FROM watchlist_snapshots
            WHERE item_id = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            [item_id],
        )
        if snapshot_df.height > 0:
            prev_price = snapshot_df["price"][0]
            if prev_price and prev_price > 0:
                # Using snapshot fallback means no historical data
                return (float((price - prev_price) / prev_price * 100.0), False)

    # No data available for comparison
    return (None, False)


def detect_missing_historical_data(
    storage: PortfolioStorage,
    symbols: list[str],
    min_days: int = 30,
    stale_threshold_days: int = 7,
) -> list[str]:
    """Detect tickers that need historical data backfill.

    Checks day_bars table to find tickers with:
    - No historical data at all
    - Insufficient data (< min_days of trading days)
    - Stale data (most recent bar > stale_threshold_days old)

    Args:
        storage: Database storage instance
        symbols: List of ticker symbols to check
        min_days: Minimum number of trading days required (default: 30)
        stale_threshold_days: Days threshold to consider data stale (default: 7)

    Returns:
        List of ticker symbols that need backfill
    """
    if not symbols:
        return []

    with storage.connection() as conn:
        # Check each ticker's historical data status
        query = """
            WITH ticker_stats AS (
                SELECT
                    ticker,
                    COUNT(*) as bar_count,
                    MAX(date) as latest_date,
                    CURRENT_DATE - MAX(date) as days_since_latest
                FROM day_bars
                WHERE ticker = ANY(?)
                GROUP BY ticker
            )
            SELECT ticker
            FROM UNNEST(?) as t(ticker)
            LEFT JOIN ticker_stats USING (ticker)
            WHERE
                ticker_stats.ticker IS NULL  -- No data at all
                OR bar_count < ?  -- Insufficient data
                OR days_since_latest > ?  -- Stale data
        """

        result = conn.execute(
            query,
            [symbols, symbols, min_days, stale_threshold_days],  # type: ignore[list-item]
        ).fetchall()

        tickers_needing_backfill = [str(row[0]) for row in result]

        if tickers_needing_backfill:
            logger.info(
                "detected_tickers_needing_backfill",
                count=len(tickers_needing_backfill),
                tickers=tickers_needing_backfill,
                min_days=min_days,
                stale_threshold_days=stale_threshold_days,
            )

        return tickers_needing_backfill


def fetch_fundamentals_and_earnings(
    storage: PortfolioStorage,
    symbol: str,
    now: datetime,
) -> tuple[FundamentalData | None, str | None, datetime | None, int | None]:
    """Fetch fundamental data and earnings information for a symbol.

    Returns:
        Tuple of (fundamentals_data, company_health, earnings_date, earnings_days_away)
    """
    fundamentals_data = None
    company_health_str: str | None = None
    earnings_date_obj: datetime | None = None
    earnings_days_away_val: int | None = None

    with storage.connection() as conn:
        # Fetch fundamentals (cached 24 hours)
        try:
            fundamentals_data = fetch_fundamentals_cached(conn, symbol, ttl_days=1)
            if fundamentals_data:
                # Calculate 4-pillar fundamental scores
                fundamentals_data.valuation_score = calculate_valuation_score(fundamentals_data)
                fundamentals_data.growth_score = calculate_growth_score(fundamentals_data)
                fundamentals_data.health_score = calculate_health_score(fundamentals_data)
                fundamentals_data.sentiment_score = calculate_sentiment_score(fundamentals_data)
                fundamentals_data.fundamental_score = calculate_fundamental_score(fundamentals_data)
                company_health_str = classify_company_health(fundamentals_data)
        except Exception as fundamentals_error:
            logger.warning(
                "fundamentals_fetch_failed",
                symbol=symbol,
                error=str(fundamentals_error),
            )

        # Fetch earnings date (cached 30 days)
        try:
            earnings_date_obj = fetch_earnings_date_cached(conn, symbol, ttl_days=30)
            if earnings_date_obj:
                # Calculate days until earnings
                days_diff = (earnings_date_obj.date() - now.date()).days
                earnings_days_away_val = days_diff if days_diff >= 0 else None
        except Exception as earnings_error:
            logger.warning(
                "earnings_fetch_failed",
                symbol=symbol,
                error=str(earnings_error),
            )

    return fundamentals_data, company_health_str, earnings_date_obj, earnings_days_away_val


def fetch_volume_data(
    storage: PortfolioStorage,
    symbol: str,
) -> tuple[float | None, float | None]:
    """Fetch current volume and 20-day average from day_bars.

    Returns:
        Tuple of (current_volume, avg_volume_20d)
    """
    current_volume: float | None = None
    avg_volume_20d: float | None = None

    volume_df = storage.query(
        """
        SELECT volume
        FROM day_bars
        WHERE ticker = ?
        ORDER BY date DESC
        LIMIT 20
        """,
        [symbol],
    )

    if volume_df.height >= 20:
        volumes = volume_df["volume"].to_list()
        current_volume = float(volumes[0]) if volumes[0] is not None else None
        avg_volume_20d = sum(v for v in volumes if v is not None) / len(
            [v for v in volumes if v is not None]
        )
    elif volume_df.height > 0:
        # Less than 20 days available - use what we have
        volumes = volume_df["volume"].to_list()
        current_volume = float(volumes[0]) if volumes[0] is not None else None
        logger.debug(
            "insufficient_volume_history",
            symbol=symbol,
            days_available=volume_df.height,
            message="Less than 20 days of volume data - skipping 20-day average",
        )

    return current_volume, avg_volume_20d


def fetch_previous_sma5(
    storage: PortfolioStorage,
    symbol: str,
) -> float | None:
    """Fetch previous day's SMA_5 from technical indicators."""
    with storage.connection() as conn:
        prev_date = (datetime.now(UTC) - timedelta(days=1)).date()
        sma_5_prev_query = """
            SELECT sma_5 FROM technical_indicators
            WHERE ticker = %s AND DATE(calculated_at) = %s
            ORDER BY calculated_at DESC LIMIT 1
        """
        result = conn.execute(sma_5_prev_query, (symbol, str(prev_date))).fetchone()
        return float(result[0]) if result and result[0] is not None else None


def fetch_news_sentiment(
    news_service: NewsService,
    symbol: str,
    max_news_articles: int,
    news_bundle: NewsBundle | None = None,
) -> tuple[float | None, NewsBundle | None]:
    """Fetch news sentiment score and news bundle.

    Returns:
        Tuple of (news_sentiment_score, news_bundle)
    """
    news_sentiment_value: float | None = None

    try:
        if news_bundle is None:
            # Fallback: Individual fetch (backwards compatibility)
            news_bundle = news_service.get_news_intelligence(symbol, max_articles=max_news_articles)

        news_sentiment_value = news_bundle.summary.score
    except Exception as exc:  # pragma: no cover - downstream services may fail
        logger.warning("news_fetch_failed", symbol=symbol, error=str(exc))

    return news_sentiment_value, news_bundle


def fetch_auxiliary_data(
    storage: PortfolioStorage,
    news_service: NewsService,
    symbol: str,
    max_news_articles: int,
    news_bundle: NewsBundle | None,
) -> tuple[float | None, float | None, float | None, float | None, NewsBundle | None]:
    """Fetch auxiliary data: volume, SMA5, news sentiment.

    Returns:
        Tuple of (current_volume, avg_volume_20d, sma_5_prev, news_sentiment, news_bundle)
    """
    # Query volume data from day_bars (latest + 20-day average)
    current_volume, avg_volume_20d = fetch_volume_data(storage, symbol)

    # Query previous day's SMA_5
    sma_5_prev = fetch_previous_sma5(storage, symbol)

    # Fetch sentiment-scored news bundle
    news_sentiment_value, news_bundle_result = fetch_news_sentiment(
        news_service, symbol, max_news_articles, news_bundle
    )

    return current_volume, avg_volume_20d, sma_5_prev, news_sentiment_value, news_bundle_result
