"""Per-ticker processing logic for watchlist refresh.

This module handles the per-ticker data gathering and snapshot creation
during watchlist refresh operations.

Extracted from scoring_service.py to reduce file size and improve modularity.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..logging_config import get_logger
from ..services import NewsService
from ..storage import PortfolioStorage
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
from .scoring import calculate_watchlist_scores

logger = get_logger(__name__)


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


def process_ticker_snapshot(
    storage: PortfolioStorage,
    symbol: str,
    item_id: str,
    price_data: Any,
    technical_map: dict[str, TechnicalSnapshot],
    default_weights: ScoreWeights,
    stale_ttl_minutes: int,
    risk_budget: float,
    now: datetime,
    news_service: NewsService,
) -> WatchlistSnapshot:
    """Process a single ticker and generate its watchlist snapshot.

    This function consolidates all data gathering, calculation, and narrative
    generation for one ticker into a single snapshot.

    Args:
        storage: Database storage instance
        symbol: Ticker symbol
        item_id: Watchlist item ID
        price_data: Price data object (from PriceDataFetcher)
        technical_map: Map of symbol -> TechnicalSnapshot
        default_weights: Score weights from preferences
        stale_ttl_minutes: Staleness threshold in minutes
        risk_budget: Risk budget for position sizing
        now: Current timestamp (UTC)
        news_service: NewsService instance for fetching scored news

    Returns:
        WatchlistSnapshot ready to be persisted

    Raises:
        Exception: If processing fails (caller should catch and log)
    """
    # Calculate price change
    change_pct, has_historical_data = calculate_price_change(
        storage, symbol, price_data.price, item_id
    )

    # Queue backfill task if historical data is missing
    if not has_historical_data:
        try:
            from ..tasks.data_ingestion_tasks import (  # noqa: PLC0415 - avoid circular dependency
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

    # Get technical snapshot
    technical_snapshot = technical_map.get(symbol, TechnicalSnapshot())
    technical_snapshot.price = price_data.price

    # Calculate scores
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

    # Query previous day's SMA_5
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

    # Fetch sentiment-scored news bundle
    news_sentiment_value: float | None = None
    recent_news_value: dict[str, Any] | None = None
    try:
        news_bundle = news_service.get_symbol_news(symbol, max_articles=10)
        news_sentiment_value = news_bundle.summary.score
        recent_news_value = {
            "summary": news_bundle.summary.model_dump(mode="json"),
            "articles": [article.model_dump(mode="json") for article in news_bundle.articles[:5]],
        }
    except Exception as exc:  # pragma: no cover - downstream services may fail
        logger.warning("news_fetch_failed", symbol=symbol, error=str(exc))
        news_sentiment_value = None
        recent_news_value = None

    # Generate narrative intelligence
    signal_inputs = {
        "price": price_data.price,
        "ema_20": technical_snapshot.ema_20,
        "sma_5": technical_snapshot.sma_5,
        "sma_5_prev": sma_5_prev,
        "rsi_14": technical_snapshot.rsi_14,
        "macd": technical_snapshot.macd,
        "volume": current_volume,
        "volume_avg_20d": avg_volume_20d,
        "company_health": company_health_str,
        "news_sentiment": news_sentiment_value,
        "earnings_days_away": earnings_days_away_val,
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
            rsi_14=technical_snapshot.rsi_14 or 50.0,
            earnings_days_away=earnings_days_away_val,
        )

        # Calculate trade levels
        entry_price_val: float | None = None
        stop_loss_val: float | None = None
        profit_target_val: float | None = None
        position_size_val: int | None = None

        if price_data.price is not None:
            entry_price_val = calculate_entry_price(price_data.price, signal_type_str)

            if entry_price_val is not None:
                with storage.connection() as conn:
                    stop_loss_val = calculate_stop_loss(conn, symbol, entry_price_val)
                    profit_target_val = calculate_profit_target(conn, symbol, entry_price_val)

                if stop_loss_val is not None:
                    position_size_val = calculate_position_size(
                        entry_price=entry_price_val,
                        stop_loss=stop_loss_val,
                        risk_budget=risk_budget,
                    )

        # Generate narrative texts
        narrative_action_plan_text: str | None = None
        narrative_position_sizing_text: str | None = None
        narrative_company_health_bullets: list[str] | None = None
        narrative_special_notes_text: str | None = None

        # Action plan
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

        # Position sizing text
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

        # Company health bullets
        if fundamentals_data is not None:
            try:
                fundamentals_dict = {
                    "revenue_growth": fundamentals_data.revenue_growth,
                    "profit_margin": fundamentals_data.profit_margin,
                    "debt_to_equity": fundamentals_data.debt_to_equity,
                    "cash": None,
                    "analyst_buy_pct": None,
                }

                if fundamentals_data.recommendation_mean is not None:
                    analyst_buy_pct = (5.0 - fundamentals_data.recommendation_mean) / 4.0
                    fundamentals_dict["analyst_buy_pct"] = max(0.0, min(1.0, analyst_buy_pct))

                narrative_company_health_bullets = generate_company_health_bullets(
                    fundamentals_dict
                )
            except Exception as company_health_error:
                logger.warning(
                    "company_health_bullets_generation_failed",
                    symbol=symbol,
                    error=str(company_health_error),
                )

        # Special notes
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
        entry_price_val = None
        stop_loss_val = None
        profit_target_val = None
        position_size_val = None
        narrative_action_plan_text = None
        narrative_position_sizing_text = None
        narrative_company_health_bullets = None
        narrative_special_notes_text = None
        company_health_str = None
        earnings_date_obj = None
        earnings_days_away_val = None

    # Calculate staleness
    data_is_stale = is_stale(fetched_at=now, now=now)

    # Create snapshot
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
        # News/sentiment fields
        news_sentiment_score=news_sentiment_value,
        recent_news_headlines=recent_news_value,
    )

    return snapshot
