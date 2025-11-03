"""Celery tasks for agent execution.

This module defines background tasks for running AI agents asynchronously.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from app.agents.discovery import DiscoveryAgent
from app.agents.portfolio_analyzer import PortfolioAnalyzerAgent
from app.agents.tools import AgentTools
from app.analytics.indicators import calculate_indicators
from app.analytics.paper_trading import update_paper_trades
from app.celery_app import celery_app
from app.logging_config import get_logger
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.sources.alphavantage_source import AlphaVantageSource
from app.sources.base import DatasetRequest
from app.sources.finnhub_source import FinnhubSource
from app.sources.fmp_source import FMPSource
from app.sources.fred import FREDSource
from app.sources.multi_source_fetcher import MultiSourceFetcher
from app.sources.news import GoogleNewsSource
from app.sources.polygon_source import PolygonSource
from app.sources.twelvedata_source import TwelveDataSource
from app.sources.yfinance_source import YFinanceSource
from app.storage import get_storage
from app.utils.market_hours import is_market_hours
from app.watchlist.service import refresh_watchlist_scores as refresh_watchlist_scores_service

logger = get_logger(__name__)


def _setup_agent_tools(storage: Any) -> AgentTools:
    """Initialize agent tools with all required dependencies.

    Args:
        storage: StorageFacade instance for database access

    Returns:
        Configured AgentTools instance with all sources and managers
    """
    news_source = GoogleNewsSource()
    fred_source = FREDSource()
    price_fetcher = PriceDataFetcher(storage)
    portfolio_mgr = PortfolioManager(storage)
    analytics = PortfolioAnalytics()

    return AgentTools(
        storage=storage,
        news_source=news_source,
        fred_source=fred_source,
        price_fetcher=price_fetcher,
        portfolio_mgr=portfolio_mgr,
        analytics=analytics,
    )


def _update_celery_task_id(storage: Any, task_id: str, run_id: str) -> None:
    """Update agent_runs table with Celery task ID.

    Args:
        storage: StorageFacade instance for database access
        task_id: Celery task ID
        run_id: Agent run ID
    """
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE agent_runs
            SET celery_task_id = ?
            WHERE id = ?
            """,
            [task_id, run_id],
        )
        conn.commit()


@celery_app.task(name="run_discovery_agent", bind=True)  # type: ignore[misc]
def run_discovery_agent(self) -> str:  # type: ignore[no-untyped-def]
    """Run discovery agent as a background task.

    Returns:
        Run ID of the agent execution
    """
    task_id = self.request.id
    logger.info(
        "discovery_agent_task_started",
        task_id=task_id,
    )

    try:
        storage = get_storage()

        # Initialize agent tools
        agent_tools = _setup_agent_tools(storage)

        agent = DiscoveryAgent(storage=storage, tools=agent_tools)
        result = agent.run()
        run_id = result["run_id"]

        # Update agent_runs with celery_task_id
        _update_celery_task_id(storage, task_id, run_id)

        logger.info(
            "discovery_agent_task_completed",
            task_id=task_id,
            run_id=run_id,
        )
        return run_id  # type: ignore[no-any-return]

    except Exception as e:
        logger.error(
            "discovery_agent_task_failed",
            task_id=task_id,
            error=str(e),
        )
        raise


@celery_app.task(name="run_portfolio_analyzer", bind=True)  # type: ignore[misc]
def run_portfolio_analyzer(self) -> str:  # type: ignore[no-untyped-def]
    """Run portfolio analyzer agent as a background task.

    Returns:
        Run ID of the agent execution
    """
    task_id = self.request.id
    logger.info(
        "portfolio_analyzer_task_started",
        task_id=task_id,
    )

    try:
        storage = get_storage()

        # Initialize agent tools
        agent_tools = _setup_agent_tools(storage)

        agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools)
        result = agent.run()
        run_id = result["run_id"]

        # Update agent_runs with celery_task_id
        _update_celery_task_id(storage, task_id, run_id)

        logger.info(
            "portfolio_analyzer_task_completed",
            task_id=task_id,
            run_id=run_id,
        )
        return run_id  # type: ignore[no-any-return]

    except Exception as e:
        logger.error(
            "portfolio_analyzer_task_failed",
            task_id=task_id,
            error=str(e),
        )
        raise


@celery_app.task(name="ingest_historical_ohlcv", bind=True)  # type: ignore[misc]
def ingest_historical_ohlcv(  # type: ignore[no-untyped-def]
    self, tickers: list[str], days: int = 252
) -> dict[str, int | str]:
    """Backfill historical OHLCV data using multi-source fetcher.

    Fetches historical daily bars for the specified tickers and lookback period,
    storing results in the day_bars table with source lineage tracking.

    Args:
        tickers: List of ticker symbols to fetch data for
        days: Number of trading days to backfill (default: 252 = ~1 year)

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - ingest_run_id: Unique ID for this ingestion run
        - tickers_count: Number of tickers processed
        - rows_inserted: Total rows inserted into day_bars table
        - duration_seconds: Total execution time
        - errors: Number of tickers that failed to fetch

    Example:
        >>> ingest_historical_ohlcv.delay(["AAPL", "MSFT", "GOOGL"], days=252)
        >>> # Backfills 252 days of OHLCV data for 3 tickers
    """
    task_id = self.request.id
    ingest_run_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)

    logger.info(
        "ingest_historical_ohlcv_started",
        task_id=task_id,
        ingest_run_id=ingest_run_id,
        tickers_count=len(tickers),
        days=days,
    )

    try:
        storage = get_storage()

        # Initialize all available sources
        sources = [
            YFinanceSource(),
            TwelveDataSource(),
            FMPSource(),
            PolygonSource(),
            FinnhubSource(),
            AlphaVantageSource(),
        ]

        # Create multi-source fetcher with priority-based failover
        fetcher = MultiSourceFetcher(sources, storage)

        # Calculate date range (lookback from today)
        end_date = dt.date.today()
        # Add extra days to account for weekends/holidays (252 trading days ≈ 365 calendar days)
        calendar_days = int(days * 1.5)
        start_date = end_date - dt.timedelta(days=calendar_days)

        # Create dataset request
        request = DatasetRequest(
            dataset="day",
            profile=None,
            tickers=tickers,
            start=start_date,
            end=end_date,
            timezone="UTC",
            ingest_run_id=ingest_run_id,
        )

        # Fetch data with multi-source failover
        logger.info(
            "ingest_fetching_data",
            ingest_run_id=ingest_run_id,
            start_date=str(start_date),
            end_date=str(end_date),
        )

        result_df, errors = fetcher.fetch_with_fallback(request, verbose=True)

        # Track errors
        error_count = len([e for e in errors.values() if e])

        # Insert data into day_bars table
        rows_inserted = 0
        if result_df is not None and len(result_df) > 0:
            # Ensure required columns exist
            required_cols = ["ticker", "date", "open", "high", "low", "close", "volume", "source"]
            missing_cols = [col for col in required_cols if col not in result_df.columns]
            if missing_cols:
                logger.error(
                    "ingest_missing_columns",
                    ingest_run_id=ingest_run_id,
                    missing_cols=missing_cols,
                )
                raise ValueError(f"Result DataFrame missing required columns: {missing_cols}")

            # Add vwap column if not present (optional field)
            if "vwap" not in result_df.columns:
                result_df = result_df.with_columns(
                    vwap=None,
                )

            # Add ingest_run_id column
            if "ingest_run_id" not in result_df.columns:
                result_df = result_df.with_columns(
                    ingest_run_id=ingest_run_id,
                )

            # Reorder columns to match day_bars table schema
            # Table expects: ticker, date, open, high, low, close, volume, vwap, source, ingest_run_id
            column_order = [
                "ticker",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "vwap",
                "source",
                "ingest_run_id",
            ]
            result_df = result_df.select(column_order)

            # Insert into database: Delete only the specific (ticker, date) pairs we're updating
            # to avoid wiping ALL day_bars data (which would break concurrent backfills)
            logger.info(
                "ingest_inserting_data",
                ingest_run_id=ingest_run_id,
                rows=len(result_df),
            )

            # Get unique tickers from the result DataFrame
            unique_tickers = result_df["ticker"].unique().to_list()

            # Delete only the rows for these specific tickers
            with storage.connection() as conn:
                placeholders = ", ".join(["%s"] * len(unique_tickers))
                conn.execute(
                    f"DELETE FROM day_bars WHERE ticker IN ({placeholders})",
                    unique_tickers,
                )
                conn.commit()

            # Now insert the new data (using append since we already deleted the old rows)
            storage.insert_dataframe("day_bars", result_df, mode="append")
            rows_inserted = len(result_df)

            logger.info(
                "ingest_data_inserted",
                ingest_run_id=ingest_run_id,
                rows_inserted=rows_inserted,
            )
        else:
            logger.warning(
                "ingest_no_data_fetched",
                ingest_run_id=ingest_run_id,
                errors=errors,
            )

        # Calculate duration
        end_time = dt.datetime.now(dt.UTC)
        duration = (end_time - start_time).total_seconds()

        result = {
            "task_id": task_id,
            "ingest_run_id": ingest_run_id,
            "tickers_count": len(tickers),
            "rows_inserted": rows_inserted,
            "duration_seconds": duration,
            "errors": error_count,
        }

        logger.info(
            "ingest_historical_ohlcv_completed",
            **result,
        )

        return result

    except Exception as e:
        logger.error(
            "ingest_historical_ohlcv_failed",
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


@celery_app.task(name="update_technical_indicators", bind=True)  # type: ignore[misc]
def update_technical_indicators(  # type: ignore[no-untyped-def]
    self, tickers: list[str]
) -> dict[str, int]:
    """Calculate and cache technical indicators for given tickers.

    This task calculates RSI, MACD, Bollinger Bands, moving averages (SMA/EMA),
    ATR, and Stochastic indicators using the latest 200 days of OHLCV data.
    Results are stored in the technical_indicators table for fast retrieval.

    Args:
        tickers: List of ticker symbols to calculate indicators for

    Returns:
        Dict with counts: {"success": int, "failed": int, "tickers_processed": int}

    Example:
        >>> # Run immediately
        >>> update_technical_indicators(["AAPL", "MSFT", "GOOGL"])
        {"success": 3, "failed": 0, "tickers_processed": 3}

        >>> # Schedule as background task
        >>> update_technical_indicators.delay(["AAPL", "MSFT", "GOOGL"])

    Note:
        This task can be scheduled daily at market close + 30 minutes (4:30 PM ET)
        using Celery beat for automated indicator updates.
    """
    task_id = self.request.id
    logger.info(
        "update_technical_indicators_started",
        task_id=task_id,
        num_tickers=len(tickers),
        tickers=tickers,
    )

    storage = get_storage()
    success_count = 0
    failed_count = 0

    for ticker in tickers:
        try:
            # Calculate indicators using latest data
            result = calculate_indicators(
                storage=storage,
                ticker=ticker,
                indicators=None,  # Calculate all indicators
                as_of_date=None,  # Use latest available date
            )

            # Extract indicator values from result
            indicators = result["indicators"]
            date = result["date"]

            # Prepare data for insertion
            indicator_data = {
                "ticker": ticker,
                "date": date,
                "rsi_14": indicators.get("rsi_14"),
                "macd": indicators.get("macd_12_26_9", {}).get("macd"),
                "macd_signal": indicators.get("macd_12_26_9", {}).get("signal"),
                "macd_histogram": indicators.get("macd_12_26_9", {}).get("histogram"),
                "bb_upper": indicators.get("bbands_20_2", {}).get("upper"),
                "bb_middle": indicators.get("bbands_20_2", {}).get("middle"),
                "bb_lower": indicators.get("bbands_20_2", {}).get("lower"),
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

            # Insert/update in technical_indicators table
            # Using UPSERT pattern (PostgreSQL ON CONFLICT)
            with storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO technical_indicators (
                        ticker, date, rsi_14, macd, macd_signal, macd_histogram,
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
                    ON CONFLICT (ticker, date) DO UPDATE SET
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
                        indicator_data["ticker"],
                        indicator_data["date"],
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
                conn.commit()  # Commit the upsert

            success_count += 1
            logger.info(
                "technical_indicators_calculated",
                ticker=ticker,
                date=date,
                num_indicators=len([v for v in indicators.values() if v is not None]),
            )

        except Exception as e:
            failed_count += 1
            logger.error(
                "technical_indicators_calculation_failed",
                ticker=ticker,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Continue with next ticker instead of failing entire task

    result = {
        "success": success_count,
        "failed": failed_count,
        "tickers_processed": len(tickers),
    }

    logger.info(
        "update_technical_indicators_completed",
        task_id=task_id,
        **result,
    )

    return result


@celery_app.task(name="update_paper_trades_task", bind=True)  # type: ignore[misc]
def update_paper_trades_task(  # type: ignore[no-untyped-def]
    self, max_holding_days: int = 60
) -> dict[str, int]:
    """Update all open paper trades with current prices and check for exits.

    This task fetches current prices for all open paper trades, updates returns,
    and automatically closes trades that hit target/stop or exceed max holding period.
    Should be scheduled daily at market close + 30 minutes (4:30 PM ET).

    Args:
        max_holding_days: Maximum days to hold before auto-closing (default: 60)

    Returns:
        Dict with update statistics:
        - trades_updated: Number of trades updated
        - trades_closed: Number of trades closed
        - target_hits: Number of target price hits
        - stop_hits: Number of stop loss hits
        - expired: Number of trades closed due to time limit

    Example:
        >>> # Run immediately
        >>> update_paper_trades_task(max_holding_days=60)
        {"trades_updated": 10, "trades_closed": 2, "target_hits": 1, "stop_hits": 0, "expired": 1}

        >>> # Schedule as background task (daily at 4:30 PM ET)
        >>> update_paper_trades_task.delay()

    Note:
        This task should be configured in Celery beat schedule to run daily:
        ```python
        celery_app.conf.beat_schedule = {
            'update-paper-trades-daily': {
                'task': 'update_paper_trades_task',
                'schedule': crontab(hour=16, minute=30),  # 4:30 PM ET
            },
        }
        ```
    """
    task_id = self.request.id
    logger.info(
        "update_paper_trades_task_started",
        task_id=task_id,
        max_holding_days=max_holding_days,
    )

    try:
        storage = get_storage()

        # Update all open paper trades
        stats = update_paper_trades(storage, max_holding_days=max_holding_days)

        logger.info(
            "update_paper_trades_task_completed",
            task_id=task_id,
            **stats,
        )

        return stats

    except Exception as e:
        logger.error(
            "update_paper_trades_task_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


@celery_app.task(name="refresh_watchlist_scores", bind=True)  # type: ignore[misc]
def refresh_watchlist_scores_task(self, account_id: str | None = None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Refresh watchlist scores for all items or a specific account.

    This task runs every 1 minute via Celery Beat, but respects the user's
    watchlist_refresh_minutes preference by skipping execution if not enough
    time has passed since the last refresh.

    Note: This task checks market hours for logging, but refreshes 24/7.
    """
    task_id = self.request.id
    account_id = account_id or "default"

    try:
        storage = get_storage()

        # Check user preference for refresh interval (in minutes)
        # Priority: watchlist_refresh_override -> default_refresh_minutes -> 15 (hardcoded default)
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    COALESCE(watchlist_refresh_override, default_refresh_minutes, 15) as refresh_interval,
                    watchlist_refresh_override IS NOT NULL as using_override
                FROM user_preferences
                WHERE id = %s
                """,
                [account_id],
            ).fetchone()

            if result:
                refresh_interval_minutes = result[0]
                using_override = result[1]

                if using_override:
                    logger.info(
                        "watchlist_refresh_using_override",
                        account_id=account_id,
                        refresh_interval_minutes=refresh_interval_minutes,
                    )
                else:
                    logger.info(
                        "watchlist_refresh_using_default",
                        account_id=account_id,
                        refresh_interval_minutes=refresh_interval_minutes,
                    )
            else:
                refresh_interval_minutes = 15  # Fallback if no preferences found
                logger.info(
                    "watchlist_refresh_no_preferences",
                    account_id=account_id,
                    refresh_interval_minutes=refresh_interval_minutes,
                )

            # Get last refresh time from most recent snapshot
            last_refresh_result = conn.execute(
                """
                SELECT MAX(fetched_at) as last_refresh
                FROM watchlist_snapshots ws
                JOIN watchlist_items wi ON ws.item_id = wi.id
                WHERE wi.account_id = %s
                """,
                [account_id],
            ).fetchone()

            last_refresh = (
                last_refresh_result[0] if last_refresh_result and last_refresh_result[0] else None
            )

        # Calculate time since last refresh
        now = dt.datetime.now(dt.UTC)
        if last_refresh:
            # Ensure last_refresh is timezone-aware
            if last_refresh.tzinfo is None:
                last_refresh = last_refresh.replace(tzinfo=dt.UTC)
            else:
                last_refresh = last_refresh.astimezone(dt.UTC)

            minutes_since_refresh = (now - last_refresh).total_seconds() / 60.0

            # AUTO-BACKFILL: Check for missing historical data (runs BEFORE interval skip)
            # This ensures data backfill happens independently of refresh interval
            try:
                from ..watchlist.service import detect_missing_historical_data  # noqa: PLC0415

                # Load watchlist items to get symbols
                with storage.connection() as conn:
                    items_result = conn.execute(
                        """
                        SELECT DISTINCT symbol
                        FROM watchlist_items
                        WHERE account_id = %s
                        """,
                        [account_id],
                    ).fetchall()
                    symbols = [row[0] for row in items_result]

                if symbols:
                    tickers_needing_backfill = detect_missing_historical_data(
                        storage=storage,
                        symbols=symbols,
                        min_days=30,
                        stale_threshold_days=7,
                    )

                    if tickers_needing_backfill:
                        logger.info(
                            "auto_backfill_triggered_from_task",
                            ticker_count=len(tickers_needing_backfill),
                            tickers=tickers_needing_backfill,
                        )

                        # Trigger async backfill (non-blocking)
                        ingest_historical_ohlcv.delay(tickers_needing_backfill, days=252)

                        logger.info(
                            "auto_backfill_task_dispatched_from_task",
                            ticker_count=len(tickers_needing_backfill),
                        )
            except Exception as e:
                logger.error(
                    "auto_backfill_failed_from_task",
                    error=str(e),
                    error_type=type(e).__name__,
                )

            # Skip if not enough time has passed
            if minutes_since_refresh < refresh_interval_minutes:
                logger.info(
                    "watchlist_refresh_skipped",
                    task_id=task_id,
                    account_id=account_id,
                    minutes_since_refresh=round(minutes_since_refresh, 1),
                    refresh_interval_minutes=refresh_interval_minutes,
                    reason="Not enough time elapsed since last refresh",
                )
                return {
                    "task_id": task_id,
                    "skipped": True,
                    "reason": "refresh_interval_not_met",
                    "minutes_since_refresh": round(minutes_since_refresh, 1),
                    "refresh_interval_minutes": refresh_interval_minutes,
                }

        # Proceed with refresh
        markets_open = is_market_hours()
        logger.info(
            "watchlist_refresh_task_started",
            task_id=task_id,
            account_id=account_id,
            markets_open=markets_open,
            refresh_interval_minutes=refresh_interval_minutes,
        )

        result = refresh_watchlist_scores_service(storage, account_id=account_id)
        result.update(
            {
                "task_id": task_id,
                "markets_open": markets_open,
                "refresh_interval_minutes": refresh_interval_minutes,
            }
        )

        logger.info(
            "watchlist_refresh_task_completed",
            task_id=task_id,
            processed=result.get("processed", 0),
            markets_open=markets_open,
            refresh_interval_minutes=refresh_interval_minutes,
        )
        return result

    except Exception as exc:  # pragma: no cover - safety net
        logger.error(
            "watchlist_refresh_task_failed",
            task_id=task_id,
            account_id=account_id,
            error=str(exc),
        )
        raise
