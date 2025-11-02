"""Watchlist scoring service for background refresh tasks."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
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
from .scoring import _is_stale as scoring_is_stale
from .scoring import calculate_watchlist_scores

logger = get_logger(__name__)

# Redis client for tracking refresh progress
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_redis_client: redis.Redis[str] | None = None


def _get_redis_client() -> redis.Redis[str]:
    """Get or create Redis client for progress tracking."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _load_watchlist_items(storage: DuckDBStorage, account_id: str | None) -> pl.DataFrame:
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
    """
    Load stale TTL from preferences (3x refresh interval).

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

            # Generate narrative intelligence
            # Classify signal based on technical indicators + fundamentals + earnings
            signal_inputs = {
                "price": price_data.price,
                "ema_20": technical_snapshot.ema_20,  # Use actual EMA_20 from indicators
                "sma_5": technical_snapshot.sma_20,  # Approximate with SMA_20 (no SMA_5 in schema)
                "sma_5_prev": None,  # Not available in current schema
                "rsi_14": technical_snapshot.rsi_14,
                "macd": technical_snapshot.macd,
                "volume": current_volume,  # Queried from day_bars
                "volume_avg_20d": avg_volume_20d,  # Calculated 20-day average
                "company_health": company_health_str,  # Fetched from fundamentals
                "news_sentiment": None,  # Will be added in future iteration
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


class WatchlistService:
    """Service layer for watchlist operations."""

    def __init__(self, storage: DuckDBStorage):
        """Initialize watchlist service."""
        self.storage = storage
        self.price_fetcher = PriceDataFetcher(storage)

    def get_items_with_scores(self, account_id: str) -> list[dict[str, Any]]:
        """
        Get all watchlist items for an account with their latest scores.

        Args:
            account_id: Account ID

        Returns:
            List of watchlist items with scores and alert flags
        """
        items_df = self.storage.query(
            """
            SELECT wi.id, wi.account_id, wi.symbol, wi.note,
                   wi.created_at, wi.updated_at
            FROM watchlist_items wi
            WHERE wi.account_id = ?
            ORDER BY wi.created_at DESC
            """,
            [account_id],
        )

        if items_df.is_empty():
            return []

        results: list[dict[str, Any]] = []

        for row in items_df.iter_rows(named=True):
            # Convert datetime objects to ISO strings if needed
            created_at = row["created_at"]
            if hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            updated_at = row["updated_at"]
            if hasattr(updated_at, "isoformat"):
                updated_at = updated_at.isoformat()

            item_data = {
                "id": row["id"],
                "account_id": row["account_id"],
                "symbol": row["symbol"],
                "note": row.get("note"),
                "created_at": created_at,
                "updated_at": updated_at,
                "score": None,
                "score_alert": False,
            }

            # Get latest snapshot
            snapshot_df = self.storage.query(
                """
                SELECT overall_score, technical_score, fetched_at, raw_metrics,
                       signal_type, signal_strength, narrative_headline,
                       recommended_style, style_confidence, optimal_holding_period, risk_level,
                       entry_price, stop_loss, profit_target, position_size_shares,
                       narrative_action_plan, narrative_position_sizing,
                       narrative_company_health, narrative_special_notes,
                       company_health, earnings_date, earnings_days_away
                FROM watchlist_snapshots
                WHERE item_id = ?
                ORDER BY fetched_at DESC
                LIMIT 1
                """,
                [row["id"]],
            )

            if not snapshot_df.is_empty():
                snap_row = snapshot_df.to_dicts()[0]
                raw_metrics = snap_row.get("raw_metrics", {})

                # Parse raw_metrics if it's a string (JSON)
                if isinstance(raw_metrics, str):
                    try:
                        raw_metrics = json.loads(raw_metrics)
                    except (json.JSONDecodeError, TypeError):
                        raw_metrics = {}

                # Recalculate staleness at display time using fetched_at timestamp
                fetched_at = snap_row.get("fetched_at")
                if fetched_at and isinstance(raw_metrics, dict):
                    # Ensure fetched_at is timezone-aware
                    if isinstance(fetched_at, datetime) and fetched_at.tzinfo is None:
                        fetched_at = fetched_at.replace(tzinfo=UTC)

                    # Get TTL from preferences
                    stale_ttl_minutes = _load_stale_ttl_minutes(self.storage)
                    current_time = datetime.now(UTC)

                    # Format fetched_at as ISO string for API response
                    fetched_at_iso = fetched_at.isoformat().replace("+00:00", "Z")

                    # Update stale flags AND timestamps based on snapshot fetched_at (mutate in place)
                    # BUG FIX: Use snapshot's fetched_at, not stale cached_at from price_cache
                    if "price" in raw_metrics and isinstance(raw_metrics["price"], dict):
                        raw_metrics["price"]["stale"] = scoring_is_stale(
                            fetched_at, stale_ttl_minutes, current_time
                        )
                        raw_metrics["price"]["updated_at"] = fetched_at_iso
                    if "technical" in raw_metrics and isinstance(raw_metrics["technical"], dict):
                        raw_metrics["technical"]["stale"] = scoring_is_stale(
                            fetched_at, stale_ttl_minutes, current_time
                        )
                        raw_metrics["technical"]["updated_at"] = fetched_at_iso

                # Check if >10 point change in last 7 days
                alert = self._check_score_alert(row["id"], snap_row["overall_score"])

                item_data["score"] = {
                    "price": raw_metrics.get("price", {}),
                    "technical": raw_metrics.get("technical", {}),
                    "overall": snap_row["overall_score"],
                }
                item_data["score_alert"] = alert

                # Add narrative intelligence fields
                item_data["signal_type"] = snap_row.get("signal_type")
                item_data["signal_strength"] = snap_row.get("signal_strength")
                item_data["narrative_headline"] = snap_row.get("narrative_headline")
                item_data["recommended_style"] = snap_row.get("recommended_style")
                item_data["style_confidence"] = snap_row.get("style_confidence")
                item_data["optimal_holding_period"] = snap_row.get("optimal_holding_period")
                item_data["risk_level"] = snap_row.get("risk_level")

                # Add trade calculation fields
                item_data["entry_price"] = snap_row.get("entry_price")
                item_data["stop_loss"] = snap_row.get("stop_loss")
                item_data["profit_target"] = snap_row.get("profit_target")
                item_data["position_size_shares"] = snap_row.get("position_size_shares")

                # Add narrative text fields
                item_data["narrative_action_plan"] = snap_row.get("narrative_action_plan")
                item_data["narrative_position_sizing"] = snap_row.get("narrative_position_sizing")
                item_data["narrative_company_health"] = snap_row.get("narrative_company_health")
                item_data["narrative_special_notes"] = snap_row.get("narrative_special_notes")

                # Add fundamental/earnings fields
                item_data["company_health"] = snap_row.get("company_health")
                earnings_date_value = snap_row.get("earnings_date")
                item_data["earnings_date"] = (
                    earnings_date_value.isoformat() if earnings_date_value is not None else None
                )
                item_data["earnings_days_away"] = snap_row.get("earnings_days_away")

            results.append(item_data)

        return results

    def get_item_with_score_by_id(self, item_id: str) -> dict[str, Any] | None:
        """Get a single watchlist item by ID with its latest score.

        This is an optimized version that queries for a specific item directly
        instead of fetching all items and filtering in memory.

        Args:
            item_id: Watchlist item ID

        Returns:
            Item data with score or None if not found
        """
        # Single query with JOIN for efficiency
        item_df = self.storage.query(
            """
            SELECT wi.id, wi.account_id, wi.symbol, wi.note,
                   wi.created_at, wi.updated_at
            FROM watchlist_items wi
            WHERE wi.id = ?
            """,
            [item_id],
        )

        if item_df.is_empty():
            return None

        row = item_df.to_dicts()[0]

        # Convert datetime objects to ISO strings
        created_at = row["created_at"]
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
        updated_at = row["updated_at"]
        if hasattr(updated_at, "isoformat"):
            updated_at = updated_at.isoformat()

        item_data = {
            "id": row["id"],
            "account_id": row["account_id"],
            "symbol": row["symbol"],
            "note": row.get("note"),
            "created_at": created_at,
            "updated_at": updated_at,
            "score": None,
            "score_alert": False,
        }

        # Get latest snapshot
        snapshot_df = self.storage.query(
            """
            SELECT overall_score, technical_score, fetched_at, raw_metrics,
                   signal_type, signal_strength, narrative_headline,
                   recommended_style, style_confidence, optimal_holding_period, risk_level,
                   entry_price, stop_loss, profit_target, position_size_shares,
                   narrative_action_plan, narrative_position_sizing,
                   narrative_company_health, narrative_special_notes,
                   company_health, earnings_date, earnings_days_away
            FROM watchlist_snapshots
            WHERE item_id = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            [item_id],
        )

        if not snapshot_df.is_empty():
            snap_row = snapshot_df.to_dicts()[0]
            raw_metrics = snap_row.get("raw_metrics", {})

            # Parse raw_metrics if it's a string (JSON)
            if isinstance(raw_metrics, str):
                try:
                    raw_metrics = json.loads(raw_metrics)
                except (json.JSONDecodeError, TypeError):
                    raw_metrics = {}

            # Recalculate staleness at display time
            fetched_at = snap_row.get("fetched_at")
            if fetched_at and isinstance(raw_metrics, dict):
                if isinstance(fetched_at, datetime) and fetched_at.tzinfo is None:
                    fetched_at = fetched_at.replace(tzinfo=UTC)

                stale_ttl_minutes = _load_stale_ttl_minutes(self.storage)
                current_time = datetime.now(UTC)
                fetched_at_iso = fetched_at.isoformat().replace("+00:00", "Z")

                # Update stale flags
                if "price" in raw_metrics and isinstance(raw_metrics["price"], dict):
                    raw_metrics["price"]["stale"] = scoring_is_stale(
                        fetched_at, stale_ttl_minutes, current_time
                    )
                    raw_metrics["price"]["updated_at"] = fetched_at_iso
                if "technical" in raw_metrics and isinstance(raw_metrics["technical"], dict):
                    raw_metrics["technical"]["stale"] = scoring_is_stale(
                        fetched_at, stale_ttl_minutes, current_time
                    )
                    raw_metrics["technical"]["updated_at"] = fetched_at_iso

            # Check for score alert
            alert = self._check_score_alert(item_id, snap_row["overall_score"])

            item_data["score"] = {
                "price": raw_metrics.get("price", {}),
                "technical": raw_metrics.get("technical", {}),
                "overall": snap_row["overall_score"],
            }
            item_data["score_alert"] = alert

            # Add narrative intelligence fields
            item_data["signal_type"] = snap_row.get("signal_type")
            item_data["signal_strength"] = snap_row.get("signal_strength")
            item_data["narrative_headline"] = snap_row.get("narrative_headline")
            item_data["recommended_style"] = snap_row.get("recommended_style")
            item_data["style_confidence"] = snap_row.get("style_confidence")
            item_data["optimal_holding_period"] = snap_row.get("optimal_holding_period")
            item_data["risk_level"] = snap_row.get("risk_level")

            # Add trade calculation fields
            item_data["entry_price"] = snap_row.get("entry_price")
            item_data["stop_loss"] = snap_row.get("stop_loss")
            item_data["profit_target"] = snap_row.get("profit_target")
            item_data["position_size_shares"] = snap_row.get("position_size_shares")

            # Add narrative text fields
            item_data["narrative_action_plan"] = snap_row.get("narrative_action_plan")
            item_data["narrative_position_sizing"] = snap_row.get("narrative_position_sizing")
            item_data["narrative_company_health"] = snap_row.get("narrative_company_health")
            item_data["narrative_special_notes"] = snap_row.get("narrative_special_notes")

            # Add fundamental/earnings fields
            item_data["company_health"] = snap_row.get("company_health")
            earnings_date_value = snap_row.get("earnings_date")
            item_data["earnings_date"] = (
                earnings_date_value.isoformat() if earnings_date_value is not None else None
            )
            item_data["earnings_days_away"] = snap_row.get("earnings_days_away")

        return item_data

    def _check_score_alert(self, item_id: str, current_score: float) -> bool:
        """Check if score changed >10 points in last 7 days."""
        history_df = self.storage.query(
            """
            SELECT overall_score
            FROM watchlist_snapshots
            WHERE item_id = ?
              AND fetched_at >= current_timestamp - INTERVAL '7 days'
            ORDER BY fetched_at ASC
            LIMIT 1
            """,
            [item_id],
        )

        if history_df.is_empty():
            return False

        week_ago_score = float(history_df["overall_score"][0])
        return abs(current_score - week_ago_score) > 10.0

    def refresh_scores(self, item_id: str, symbol: str) -> None:
        """
        Refresh scores for a single watchlist item.

        Args:
            item_id: Watchlist item ID
            symbol: Stock symbol

        Raises:
            ValueError: If unable to fetch price data or insufficient historical data
        """
        price_data = self.price_fetcher.fetch_price_data([symbol]).get(symbol)
        if not price_data or price_data.price <= 0:
            raise ValueError(f"Unable to fetch price data for {symbol}")

        change_pct, has_historical_data = _calculate_price_change(
            self.storage, symbol, price_data.price, item_id
        )

        # Queue backfill if missing historical data
        if not has_historical_data:
            try:
                from ..tasks.agent_tasks import (  # noqa: PLC0415 - avoid circular dependency
                    ingest_historical_ohlcv,
                )

                ingest_historical_ohlcv.delay([symbol], days=252)
                logger.info(
                    "watchlist_refresh_scores_queued_backfill",
                    symbol=symbol,
                    item_id=item_id,
                )
            except Exception as e:
                logger.warning(
                    "watchlist_refresh_scores_backfill_failed", symbol=symbol, error=str(e)
                )

        # Require some comparison data for meaningful scores
        if change_pct is None:
            raise ValueError(
                f"Insufficient historical data for {symbol} - need at least 2 days (day_bars or snapshots)"
            )

        technical_map = _load_latest_technical(self.storage, [symbol])
        technical_snapshot = technical_map.get(symbol, TechnicalSnapshot())
        technical_snapshot.price = price_data.price

        default_weights = _load_default_weights(self.storage)
        stale_ttl_minutes = _load_stale_ttl_minutes(self.storage)
        now = datetime.now(UTC)

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

        snapshot = WatchlistSnapshot(
            item_id=item_id,
            fetched_at=now,
            price=price_data.price,
            change_pct=change_pct,
            beta=price_data.beta,
            volatility=price_data.volatility,
            overall_score=breakdown.overall,
            technical_score=breakdown.technical.score,
            raw_metrics=breakdown.to_snapshot_payload(),
        )

        self.storage.query_mgr.upsert_watchlist_snapshot(**snapshot.to_upsert_params())

        logger.info("Watchlist item scores refreshed", item_id=item_id, symbol=symbol)
