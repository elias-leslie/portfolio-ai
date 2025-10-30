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
from app.watchlist.service import refresh_watchlist_scores as refresh_watchlist_scores_service

logger = get_logger(__name__)


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
        news_source = GoogleNewsSource()
        fred_source = FREDSource()
        price_fetcher = PriceDataFetcher(storage)
        portfolio_mgr = PortfolioManager(storage)
        analytics = PortfolioAnalytics()

        agent_tools = AgentTools(
            storage=storage,
            news_source=news_source,
            fred_source=fred_source,
            price_fetcher=price_fetcher,
            portfolio_mgr=portfolio_mgr,
            analytics=analytics,
        )

        agent = DiscoveryAgent(storage=storage, tools=agent_tools)
        result = agent.run()
        run_id = result["run_id"]

        # Update agent_runs with celery_task_id
        with storage.connection() as conn:
            conn.execute(
                """
                UPDATE agent_runs
                SET celery_task_id = ?
                WHERE id = ?
                """,
                [task_id, run_id],
            )

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
        news_source = GoogleNewsSource()
        fred_source = FREDSource()
        price_fetcher = PriceDataFetcher(storage)
        portfolio_mgr = PortfolioManager(storage)
        analytics = PortfolioAnalytics()

        agent_tools = AgentTools(
            storage=storage,
            news_source=news_source,
            fred_source=fred_source,
            price_fetcher=price_fetcher,
            portfolio_mgr=portfolio_mgr,
            analytics=analytics,
        )

        agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools)
        result = agent.run()
        run_id = result["run_id"]

        # Update agent_runs with celery_task_id
        with storage.connection() as conn:
            conn.execute(
                """
                UPDATE agent_runs
                SET celery_task_id = ?
                WHERE id = ?
                """,
                [task_id, run_id],
            )

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

            # Insert into database (replace existing data for same ticker/date)
            logger.info(
                "ingest_inserting_data",
                ingest_run_id=ingest_run_id,
                rows=len(result_df),
            )

            storage.insert_dataframe("day_bars", result_df, mode="replace")
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
            # Using UPSERT pattern (INSERT OR REPLACE)
            with storage.connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO technical_indicators (
                        ticker, date, rsi_14, macd, macd_signal, macd_histogram,
                        bb_upper, bb_middle, bb_lower,
                        sma_20, sma_50, sma_200,
                        ema_20, ema_50, ema_200,
                        atr_14, stoch_k, stoch_d,
                        calculated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?
                    )
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
    """Refresh watchlist scores for all items or a specific account."""

    task_id = self.request.id
    logger.info(
        "watchlist_refresh_task_started",
        task_id=task_id,
        account_id=account_id,
    )

    try:
        storage = get_storage()
        result = refresh_watchlist_scores_service(storage, account_id=account_id)
        result.update({"task_id": task_id})

        logger.info(
            "watchlist_refresh_task_completed",
            task_id=task_id,
            processed=result.get("processed", 0),
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
