"""Celery tasks for agent execution.

This module defines background tasks for running AI agents asynchronously.
"""

from __future__ import annotations

import datetime as dt
import uuid

from app.agents.discovery import DiscoveryAgent
from app.agents.portfolio_analyzer import PortfolioAnalyzerAgent
from app.agents.tools import AgentTools
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

        agent_tools = AgentTools(  # type: ignore[no-untyped-call]
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

        agent_tools = AgentTools(  # type: ignore[no-untyped-call]
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
