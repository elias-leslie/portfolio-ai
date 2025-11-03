"""Watchlist scoring service for background refresh tasks.

This module handles:
- Watchlist score calculation and refresh
- Background scoring tasks
- Score persistence to snapshots
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import polars as pl
import redis

from ..logging_config import get_logger
from ..portfolio.price_fetcher import PriceDataFetcher
from ..storage import DuckDBStorage
from ..utils.market_hours import is_stale
from .calculator import (
    calculate_entry_price,
    calculate_position_size,
    calculate_profit_target,
    calculate_stop_loss,
)
from .earnings import fetch_earnings_date_cached
from .fundamentals import classify_company_health, fetch_fundamentals_cached
from .models import (
    ScoreWeights,
    SignalType,
    TechnicalSnapshot,
    WatchlistScoreInputs,
    WatchlistSnapshot,
)
from .narrative import (
    classify_signal,
    classify_trading_style,
    generate_action_plan,
    generate_company_health_bullets,
    generate_headline,
    generate_position_sizing_text,
    generate_special_notes,
)
from .news import fetch_news_headlines_cached
from .scoring import calculate_watchlist_scores

logger = get_logger(__name__)

# Redis client for tracking refresh progress
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_redis_client: Any = None


def _get_redis_client() -> Any:  # redis.Redis with decode_responses=True
    """Get or create Redis client for progress tracking."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _load_watchlist_items(storage: DuckDBStorage, account_id: str | None) -> pl.DataFrame:
    """Load watchlist items from database."""
    params: list[Any] = []
    sql = """
        SELECT id, account_id, symbol
        FROM watchlist_items
    """
    if account_id:
        sql += " WHERE account_id = ?"
        params.append(account_id)
    return storage.query(sql, params)


def _load_latest_technical(
    storage: DuckDBStorage, symbols: list[str]
) -> dict[str, TechnicalSnapshot]:
    """Load latest technical indicators for symbols."""
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
        symbols,
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
            sma_5=row.get("sma_5"),  # Add 5-day SMA
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


def _load_default_weights(storage: DuckDBStorage) -> ScoreWeights:
    """Load score weights from user preferences."""
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


def _load_stale_ttl_minutes(storage: DuckDBStorage) -> int:
    """Load stale TTL from preferences (3x refresh interval).

    Priority: watchlist_refresh_override → default_refresh_minutes → fallback (15min)
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
        return 45  # Default: 3x 15min refresh = 45min

    row = df.to_dicts()[0]

    # Use override if set, otherwise use default, otherwise fallback to 15
    refresh_override = row.get("watchlist_refresh_override")
    default_refresh = row.get("default_refresh_minutes", 15)

    if refresh_override is not None:
        refresh_minutes = int(refresh_override)
    else:
        refresh_minutes = int(default_refresh) if default_refresh is not None else 15

    return int(refresh_minutes * 3)  # Stale = 3x refresh interval


def _load_risk_budget(storage: DuckDBStorage) -> float:
    """Load risk budget from user preferences.

    Returns the amount a user is willing to risk per trade for position sizing.

    Returns:
        Risk budget in dollars (default: $500)
    """
    df = storage.query(
        """
        SELECT watchlist_risk_budget
        FROM user_preferences
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    if df.is_empty():
        return 500.0  # Default risk budget

    row = df.to_dicts()[0]
    risk_budget = row.get("watchlist_risk_budget", 500)
    return float(risk_budget) if risk_budget is not None else 500.0


def _calculate_price_change(
    storage: DuckDBStorage, symbol: str, price: float | None, item_id: str | None = None
) -> tuple[float | None, bool]:
    """Calculate price change percentage for a symbol.

    First tries to calculate from day_bars historical data (preferred).
    Falls back to previous watchlist snapshot if available.

    Args:
        storage: DuckDBStorage instance
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
    storage: DuckDBStorage,
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
            [symbols, symbols, min_days, stale_threshold_days],
        ).fetchall()

        tickers_needing_backfill = [row[0] for row in result]

        if tickers_needing_backfill:
            logger.info(
                "detected_tickers_needing_backfill",
                count=len(tickers_needing_backfill),
                tickers=tickers_needing_backfill,
                min_days=min_days,
                stale_threshold_days=stale_threshold_days,
            )

        return tickers_needing_backfill


def refresh_watchlist_scores(
    storage: DuckDBStorage,
    *,
    account_id: str | None = None,
    price_fetcher: PriceDataFetcher | None = None,
    batch_size: int = 20,
    batch_delay_seconds: float = 2.0,
) -> dict[str, Any]:
    """Refresh watchlist scores for all items or a specific account.

    Args:
        storage: Database storage instance
        account_id: Optional account ID to filter items (None = all accounts)
        price_fetcher: Optional price fetcher instance (creates new if None)
        batch_size: Number of symbols to fetch in each batch (default: 20)
        batch_delay_seconds: Delay between batches to respect rate limits (default: 2.0)

    Returns:
        Dict with processing statistics:
        - processed: Number of items successfully processed
        - symbols: List of symbols processed
        - batches: Number of batches executed

    Note:
        Batching strategy respects API quota limits:
        - YFinance: Unlimited (primary source, handles bulk requests)
        - TwelveData: 8 req/min, 800/day (batch_size=20, delay=2s = 6/min conservative)
        - Polygon: 5 req/min (batch_size=20, delay=2s = well under limit)
        Conservative defaults ensure we stay within free tier quotas even with failover.
    """
    items_df = _load_watchlist_items(storage, account_id)
    if items_df.is_empty():
        logger.info("watchlist_refresh_no_items", account_id=account_id)
        return {"processed": 0, "symbols": [], "batches": 0}

    symbols = sorted(set(items_df["symbol"]))
    total_items = len(items_df)

    # AUTO-BACKFILL: Check for missing or stale historical data
    # This ensures sparklines, trendlines, and indicators always have data
    tickers_needing_backfill = detect_missing_historical_data(
        storage=storage,
        symbols=symbols,
        min_days=30,  # Require at least 30 days of data
        stale_threshold_days=7,  # Backfill if data is >7 days old
    )

    if tickers_needing_backfill:
        try:
            # Import here to avoid circular dependency
            from ..tasks.agent_tasks import ingest_historical_ohlcv  # noqa: PLC0415

            logger.info(
                "auto_backfill_triggered",
                ticker_count=len(tickers_needing_backfill),
                tickers=tickers_needing_backfill,
            )

            # Trigger async backfill task (non-blocking)
            # This runs in background while we continue with current price refresh
            ingest_historical_ohlcv.delay(tickers_needing_backfill, days=252)

            logger.info(
                "auto_backfill_task_dispatched",
                ticker_count=len(tickers_needing_backfill),
                message="Historical data will be backfilled in background",
            )
        except Exception as e:
            logger.error(
                "auto_backfill_failed_to_trigger",
                error=str(e),
                error_type=type(e).__name__,
            )

    # Initialize refresh status in Redis
    redis_key = f"watchlist:refresh:{account_id or 'all'}"
    try:
        redis_client = _get_redis_client()
        redis_client.setex(
            redis_key,
            900,  # 15 minute TTL
            json.dumps(
                {
                    "status": "running",
                    "started_at": datetime.now(UTC).isoformat(),
                    "total_items": total_items,
                    "processed_items": 0,
                    "current_symbol": None,
                    "symbols": symbols,
                }
            ),
        )
    except Exception as e:
        logger.warning("Failed to initialize Redis refresh status", error=str(e))

    fetcher = price_fetcher or PriceDataFetcher(storage)
    technical_map = _load_latest_technical(storage, symbols)
    default_weights = _load_default_weights(storage)
    stale_ttl_minutes = _load_stale_ttl_minutes(storage)
    risk_budget = _load_risk_budget(storage)

    # Batch symbols to respect API rate limits
    symbol_batches = [symbols[i : i + batch_size] for i in range(0, len(symbols), batch_size)]
    total_batches = len(symbol_batches)

    logger.info(
        "watchlist_refresh_batching",
        total_symbols=len(symbols),
        batch_size=batch_size,
        total_batches=total_batches,
        delay_seconds=batch_delay_seconds,
    )

    # Fetch price data in batches with delays
    price_map: dict[str, Any] = {}
    for batch_idx, batch_symbols in enumerate(symbol_batches, start=1):
        logger.debug(
            "watchlist_refresh_batch",
            batch=batch_idx,
            total_batches=total_batches,
            batch_size=len(batch_symbols),
        )

        batch_prices = fetcher.fetch_price_data(batch_symbols)
        price_map.update(batch_prices)

        # Delay between batches (except after last batch)
        if batch_idx < total_batches and batch_delay_seconds > 0:
            time.sleep(batch_delay_seconds)

    processed = 0
    now = datetime.now(UTC)
    processed_symbols: list[str] = []
    success_list: list[str] = []
    failed_list: list[dict[str, str]] = []

    for row in items_df.iter_rows(named=True):
        symbol = row["symbol"]
        item_id = row["id"]

        # Update refresh status for current symbol
        try:
            redis_client = _get_redis_client()
            redis_value = redis_client.get(redis_key)
            status_data = json.loads(str(redis_value) if redis_value else "{}")
            status_data.update(
                {
                    "current_symbol": symbol,
                    "processed_items": processed,
                }
            )
            redis_client.setex(redis_key, 900, json.dumps(status_data))
        except Exception as e:
            logger.debug("Failed to update Redis refresh status", error=str(e))

        # Wrap per-ticker processing in try/except for error tracking
        try:
            price_data = price_map.get(symbol)
            if not price_data or price_data.price <= 0:
                logger.warning(
                    "watchlist_refresh_missing_price",
                    symbol=symbol,
                    item_id=item_id,
                )
                failed_list.append(
                    {
                        "symbol": symbol,
                        "reason": "Unable to fetch price data or invalid price",
                    }
                )
                continue

            change_pct, has_historical_data = _calculate_price_change(
                storage, symbol, price_data.price, item_id
            )

            # Queue backfill task if historical data is missing
            # Note: Using try/except to handle celery not running (dev environments)
            if not has_historical_data:
                try:
                    from ..tasks.agent_tasks import (  # noqa: PLC0415 - avoid circular dependency
                        ingest_historical_ohlcv,
                    )

                    # Queue backfill for 252 trading days (~1 year)
                    ingest_historical_ohlcv.delay([symbol], days=252)
                    logger.info(
                        "watchlist_refresh_queued_backfill",
                        symbol=symbol,
                        item_id=item_id,
                        reason="Missing day_bars data - queued historical backfill task",
                    )
                except Exception as e:
                    logger.warning(
                        "watchlist_refresh_backfill_queue_failed",
                        symbol=symbol,
                        item_id=item_id,
                        error=str(e),
                    )

            # Default to 0.0% change if no comparison data available
            if change_pct is None:
                logger.info(
                    "watchlist_refresh_defaulted_change_pct",
                    symbol=symbol,
                    item_id=item_id,
                    change_pct=0.0,
                    reason="No comparison data (first snapshot) - defaulting to 0.0%",
                )
                change_pct = 0.0

            technical_snapshot = technical_map.get(symbol, TechnicalSnapshot())
            technical_snapshot.price = price_data.price

            breakdown = calculate_watchlist_scores(
                WatchlistScoreInputs(
                    price=price_data,
                    price_change_pct=change_pct,
                    technical=technical_snapshot,
                    weights=default_weights,
                    now=now,
                    stale_ttl_minutes=stale_ttl_minutes,
                )
            )

            # Fetch fundamentals and earnings data for narrative generation
            fundamentals_data = None
            company_health_str: str | None = None
            earnings_date_obj: datetime | None = None
            earnings_days_away_val: int | None = None

            with storage.connection() as conn:
                # Fetch fundamentals (cached 24 hours)
                try:
                    fundamentals_data = fetch_fundamentals_cached(conn, symbol, ttl_days=1)
                    if fundamentals_data:
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

            # Query volume data from day_bars (latest + 20-day average)
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

            # Query previous day's SMA_5 (Note: technical_indicators uses 'ticker' not 'symbol')
            sma_5_prev = None
            with storage.connection() as conn:
                prev_date = (datetime.now(UTC) - timedelta(days=1)).date()
                sma_5_prev_query = """
                    SELECT sma_5 FROM technical_indicators
                    WHERE ticker = %s AND DATE(calculated_at) = %s
                    ORDER BY calculated_at DESC LIMIT 1
                """
                result = conn.execute(sma_5_prev_query, (symbol, prev_date)).fetchone()
                sma_5_prev = result[0] if result else None

            # Fetch news (cached 6 hours)
            news_sentiment_value: float | None = None
            recent_news_value: dict[str, Any] | None = None
            with storage.connection() as conn:
                try:
                    news_headlines = fetch_news_headlines_cached(
                        conn, symbol, max_results=10, ttl_hours=6
                    )
                    if news_headlines:
                        avg_sentiment = sum(h.sentiment_score for h in news_headlines) / len(
                            news_headlines
                        )
                        news_sentiment_value = avg_sentiment
                        recent_news_value = {
                            "headlines": [h.model_dump() for h in news_headlines[:5]]
                        }
                    else:
                        news_sentiment_value = None
                        recent_news_value = None
                except Exception as e:
                    logger.warning("news_fetch_failed", symbol=symbol, error=str(e))
                    news_sentiment_value = None
                    recent_news_value = None

            # Generate narrative intelligence
            # Classify signal based on technical indicators + fundamentals + earnings
            signal_inputs = {
                "price": price_data.price,
                "ema_20": technical_snapshot.ema_20,  # Use actual EMA_20 from indicators
                "sma_5": technical_snapshot.sma_5,  # Now available in schema (PRD #0022)
                "sma_5_prev": sma_5_prev,  # Queried from previous day
                "rsi_14": technical_snapshot.rsi_14,
                "macd": technical_snapshot.macd,
                "volume": current_volume,  # Queried from day_bars
                "volume_avg_20d": avg_volume_20d,  # Calculated 20-day average
                "company_health": company_health_str,  # Fetched from fundamentals
                "news_sentiment": news_sentiment_value,  # Fetched from news (cached 6h)
                "earnings_days_away": earnings_days_away_val,  # Calculated from earnings date
            }

            try:
                classification = classify_signal(signal_inputs)
                signal_type_str = classification.signal_type.value
                signal_strength_val = classification.strength.value
                headline = generate_headline(classification)

                # Classify trading style
                style_result = classify_trading_style(
                    symbol=symbol,
                    signal_strength=signal_strength_val,
                    signal_type=signal_type_str,
                    rsi_14=technical_snapshot.rsi_14 or 50.0,  # Default to neutral if missing
                    earnings_days_away=earnings_days_away_val,
                )

                # Calculate trade levels (entry, stop, target, position size)
                entry_price_val: float | None = None
                stop_loss_val: float | None = None
                profit_target_val: float | None = None
                position_size_val: int | None = None

                if price_data.price is not None:
                    # Calculate entry price (current price for BUY/HOLD, None for AVOID)
                    entry_price_val = calculate_entry_price(price_data.price, signal_type_str)

                    # Calculate stop loss and profit target (requires DB connection)
                    if entry_price_val is not None:
                        with storage.connection() as conn:
                            stop_loss_val = calculate_stop_loss(conn, symbol, entry_price_val)
                            profit_target_val = calculate_profit_target(
                                conn, symbol, entry_price_val
                            )

                        # Calculate position size based on risk budget
                        if stop_loss_val is not None:
                            position_size_val = calculate_position_size(
                                entry_price=entry_price_val,
                                stop_loss=stop_loss_val,
                                risk_budget=risk_budget,
                            )

                # Generate narrative texts (for fields we have data for)
                narrative_action_plan_text: str | None = None
                narrative_position_sizing_text: str | None = None
                narrative_company_health_bullets: list[str] | None = None
                narrative_special_notes_text: str | None = None

                # Generate action plan if we have trade levels
                if (
                    entry_price_val is not None
                    and stop_loss_val is not None
                    and profit_target_val is not None
                ):
                    try:
                        narrative_action_plan_text = generate_action_plan(
                            signal_type=signal_type_str,
                            entry_price=entry_price_val,
                            stop_loss=stop_loss_val,
                            profit_target=profit_target_val,
                        )
                    except Exception as action_plan_error:
                        logger.warning(
                            "action_plan_generation_failed",
                            symbol=symbol,
                            error=str(action_plan_error),
                        )

                # Generate position sizing text if we have all required data
                if (
                    position_size_val is not None
                    and entry_price_val is not None
                    and profit_target_val is not None
                    and stop_loss_val is not None
                ):
                    try:
                        narrative_position_sizing_text = generate_position_sizing_text(
                            shares=position_size_val,
                            entry_price=entry_price_val,
                            stop_loss=stop_loss_val,
                            profit_target=profit_target_val,
                        )
                    except Exception as position_sizing_error:
                        logger.warning(
                            "position_sizing_text_generation_failed",
                            symbol=symbol,
                            error=str(position_sizing_error),
                        )

                # Generate company health bullets if we have fundamentals data
                if fundamentals_data is not None:
                    try:
                        # Convert FundamentalData to dict for narrative generation
                        fundamentals_dict = {
                            "revenue_growth": fundamentals_data.revenue_growth,
                            "profit_margin": fundamentals_data.profit_margin,
                            "debt_to_equity": fundamentals_data.debt_to_equity,
                            "cash": None,  # Not available in current fundamentals model
                            "analyst_buy_pct": None,  # Will calculate from recommendation_mean
                        }

                        # Estimate analyst buy percentage from recommendation_mean
                        # recommendation_mean: 1.0-5.0 (1=strong buy, 5=sell)
                        if fundamentals_data.recommendation_mean is not None:
                            # Convert to buy percentage (1.0 → 100%, 5.0 → 0%)
                            analyst_buy_pct = (5.0 - fundamentals_data.recommendation_mean) / 4.0
                            fundamentals_dict["analyst_buy_pct"] = max(
                                0.0, min(1.0, analyst_buy_pct)
                            )

                        narrative_company_health_bullets = generate_company_health_bullets(
                            fundamentals_dict
                        )
                    except Exception as company_health_error:
                        logger.warning(
                            "company_health_bullets_generation_failed",
                            symbol=symbol,
                            error=str(company_health_error),
                        )

                # Generate special notes if we have all required data
                if company_health_str is not None:
                    try:
                        narrative_special_notes_text = generate_special_notes(
                            signal_type=signal_type_str,
                            signal_strength=signal_strength_val,
                            earnings_days_away=earnings_days_away_val,
                            company_health=company_health_str,
                        )
                    except Exception as special_notes_error:
                        logger.warning(
                            "special_notes_generation_failed",
                            symbol=symbol,
                            error=str(special_notes_error),
                        )

            except Exception as e:
                logger.warning(
                    "narrative_generation_failed",
                    symbol=symbol,
                    error=str(e),
                )
                # Use defaults if narrative generation fails
                signal_type_str = SignalType.HOLD.value
                signal_strength_val = 5
                headline = f"HOLD - {symbol}"
                style_result = {
                    "style": "Value",
                    "confidence": 5,
                    "holding_period": "Unknown",
                    "risk_level": "Medium",
                }
                # Initialize calculator values as None on failure
                entry_price_val = None
                stop_loss_val = None
                profit_target_val = None
                position_size_val = None
                # Initialize narrative texts as None on failure
                narrative_action_plan_text = None
                narrative_position_sizing_text = None
                narrative_company_health_bullets = None
                narrative_special_notes_text = None
                # Initialize fundamentals/earnings as None on failure
                company_health_str = None
                earnings_date_obj = None
                earnings_days_away_val = None

            # Calculate staleness based on market hours
            data_is_stale = is_stale(fetched_at=now, now=now)  # Just fetched, so not stale

            snapshot = WatchlistSnapshot(
                item_id=item_id,
                fetched_at=now,
                price=price_data.price,
                change_pct=change_pct,
                beta=price_data.beta,
                volatility=price_data.volatility,
                overall_score=breakdown.overall,
                technical_score=breakdown.technical.score,
                is_stale=data_is_stale,
                raw_metrics=breakdown.to_snapshot_payload(),
                # Narrative fields
                signal_type=signal_type_str,
                signal_strength=signal_strength_val,
                narrative_headline=headline,
                recommended_style=style_result["style"],
                style_confidence=style_result["confidence"],
                optimal_holding_period=style_result["holding_period"],
                risk_level=style_result["risk_level"],
                # Trade calculation fields
                entry_price=entry_price_val,
                stop_loss=stop_loss_val,
                profit_target=profit_target_val,
                position_size_shares=position_size_val,
                # Narrative text fields
                narrative_action_plan=narrative_action_plan_text,
                narrative_position_sizing=narrative_position_sizing_text,
                narrative_company_health={"bullets": narrative_company_health_bullets}
                if narrative_company_health_bullets
                else None,
                narrative_special_notes=narrative_special_notes_text,
                # Fundamental/earnings fields
                company_health=company_health_str,
                earnings_date=earnings_date_obj,
                earnings_days_away=earnings_days_away_val,
                # News/sentiment fields (PRD #0022)
                news_sentiment_score=news_sentiment_value,
                recent_news_headlines=recent_news_value,
            )

            storage.query_mgr.upsert_watchlist_snapshot(**snapshot.to_upsert_params())
            processed += 1
            processed_symbols.append(symbol)
            success_list.append(symbol)

        except Exception as e:
            # Log error and continue processing remaining tickers
            logger.warning(
                "watchlist_refresh_ticker_failed",
                symbol=symbol,
                item_id=item_id,
                error=str(e),
            )
            failed_list.append({"symbol": symbol, "reason": str(e)})

    logger.info(
        "watchlist_refresh_completed",
        processed=processed,
        symbols=processed_symbols,
        batches=total_batches,
        success_count=len(success_list),
        failed_count=len(failed_list),
    )

    # Update refresh status to completed (keep for 5 seconds for frontend polling)
    try:
        redis_client = _get_redis_client()
        redis_value = redis_client.get(redis_key)
        existing_data = json.loads(str(redis_value) if redis_value else "{}")
        completed_data = {
            "status": "completed",
            "started_at": existing_data.get("started_at"),
            "total_items": total_items,
            "processed_items": processed,
            "current_symbol": None,
            "is_refreshing": False,
        }
        redis_client.setex(redis_key, 5, json.dumps(completed_data))  # Keep for 5 seconds
    except Exception as e:
        logger.warning("Failed to update Redis refresh completion status", error=str(e))

    return {
        "processed": processed,
        "symbols": processed_symbols,
        "batches": total_batches,
        "success_count": len(success_list),
        "failed_count": len(failed_list),
        "success": success_list,
        "failed": failed_list,
    }
