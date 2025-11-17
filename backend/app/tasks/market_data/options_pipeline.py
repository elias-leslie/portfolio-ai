"""Options positioning pipeline tasks.

Fetches and processes options market data for sentiment analysis:
- Put/Call ratios from CBOE official statistics
- Options activity metrics from CBOE most active contracts
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, Any

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.sources.cboe_source import get_cboe_source
from app.storage import get_storage

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


@celery_app.task(name="fetch_putcall_ratio", bind=True)  # type: ignore[misc]
def fetch_putcall_ratio(  # type: ignore[no-untyped-def]
    self,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    """DEPRECATED: Fetch Put/Call Ratio from CBOE official data.

    DISABLED AS OF 2025-11-17: The CBOE CDN endpoint returns HTTP 403 Forbidden
    (Access Denied by CloudFront). This cannot be fixed without CBOE cooperation.

    The endpoint at https://cdn.cboe.com/data/us/options/market_statistics/daily/{date}_daily_options
    was the source for this data, but CBOE blocks automated (non-browser) requests.

    Historical behavior:
    - Fetched official CBOE put/call ratios (market sentiment indicator)
    - Data represented daily trading volume ratios (not open interest)
    - Was scheduled daily at 04:30 UTC

    Task kept for historical reference but removed from schedule.
    Code removal pending alternative data source implementation.

    Args:
        as_of_date: Date to fetch data for (YYYY-MM-DD). If None, uses today's data.

    Returns:
        Dict with error information (task will fail when executed)

    Alternatives:
        - Use VIX from yfinance as market sentiment proxy
        - Implement browser-based scraper with Playwright (resource intensive)
        - Find alternative options data API provider
    """
    task_id = self.request.id

    logger.info(
        "fetch_putcall_ratio_started",
        task_id=task_id,
        requested_date=as_of_date,
    )

    try:
        # Get storage for metrics tracking
        storage = get_storage()

        # Fetch from CBOE official source (with metrics tracking enabled)
        cboe = get_cboe_source(storage=storage)
        data = cboe.fetch_put_call_ratios()

        # Extract key values
        cboe_date = data["date"]
        # Use SPX+SPXW as primary ratio (S&P 500 specific)
        # Fall back to total if SPX not available
        put_call_ratio = data.get("spx") or data["total"]

        # Store in fear_greed_inputs table
        with storage.connection() as conn:
            # Insert or update
            conn.execute(
                """
                INSERT INTO fear_greed_inputs (as_of_date, put_call_ratio, source_map)
                VALUES (%s, %s, %s)
                ON CONFLICT (as_of_date) DO UPDATE SET
                    put_call_ratio = EXCLUDED.put_call_ratio,
                    source_map = fear_greed_inputs.source_map || EXCLUDED.source_map
                """,
                (
                    cboe_date,
                    put_call_ratio,
                    '{"put_call_ratio": "cboe_daily_statistics"}',
                ),
            )
            conn.commit()

        result = {
            "task_id": task_id,
            "date": cboe_date,
            "put_call_ratio": round(put_call_ratio, 4),
            "total_ratio": round(data["total"], 4),
            "index_ratio": round(data["index"], 4) if data.get("index") else None,
            "equity_ratio": round(data["equity"], 4) if data.get("equity") else None,
            "success": True,
        }

        logger.info(
            "fetch_putcall_ratio_completed",
            **result,
        )

        return result

    except Exception as e:
        logger.error(
            "fetch_putcall_ratio_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "task_id": task_id,
            "date": as_of_date or dt.date.today().isoformat(),
            "error": str(e),
            "success": False,
        }


@celery_app.task(name="fetch_options_activity_metrics", bind=True)  # type: ignore[misc]
def fetch_options_activity_metrics(  # type: ignore[no-untyped-def]
    self,
) -> dict[str, Any]:
    """Fetch aggregated options activity metrics from CBOE Most Active page.

    Scrapes CBOE Most Active Options page and calculates daily metrics:
    - Sentiment: % of calls vs puts in top 25
    - Time horizon: % of near-term options (≤30 days)
    - Concentration: % of volume in top 5 contracts
    - Sector distribution: % by sector

    Data source: https://www.cboe.com/us/options/market_statistics/most_active/

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - as_of_date: Date of metrics (YYYY-MM-DD)
        - metrics: Dict with all calculated metrics
        - success: Boolean indicating success

    Example:
        >>> # Manual trigger for testing
        >>> celery -A app.celery_app call app.tasks.market_data.fetch_options_activity_metrics

    Note:
        This task should be scheduled daily at 21:15 UTC (4:15 PM ET, after market close).
        Uses Playwright to render JavaScript-heavy CBOE page.
        Stores aggregated metrics (not raw contracts) for trend analysis.
    """
    task_id = self.request.id

    logger.info(
        "fetch_options_activity_started",
        task_id=task_id,
    )

    try:
        # Get storage for metrics tracking
        storage = get_storage()

        # Import here to avoid circular dependency
        from app.sources.cboe_most_active import get_cboe_most_active_source  # noqa: PLC0415

        # Fetch from CBOE Most Active source (with metrics tracking enabled)
        cboe_most_active = get_cboe_most_active_source(storage=storage)
        metrics = cboe_most_active.fetch_most_active_metrics()

        # Store in options_market_metrics table (upsert)
        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO options_market_metrics (
                    as_of_date,
                    most_active_call_pct,
                    near_term_pct,
                    concentration_pct,
                    sector_weights,
                    source_timestamp
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (as_of_date) DO UPDATE SET
                    most_active_call_pct = EXCLUDED.most_active_call_pct,
                    near_term_pct = EXCLUDED.near_term_pct,
                    concentration_pct = EXCLUDED.concentration_pct,
                    sector_weights = EXCLUDED.sector_weights,
                    source_timestamp = EXCLUDED.source_timestamp
                """,
                (
                    metrics["as_of_date"],
                    metrics["most_active_call_pct"],
                    metrics["near_term_pct"],
                    metrics["concentration_pct"],
                    json.dumps(metrics["sector_weights"]),
                    metrics["source_timestamp"],
                ),
            )
            conn.commit()

        result = {
            "task_id": task_id,
            "as_of_date": metrics["as_of_date"],
            "metrics": {
                "call_pct": metrics["most_active_call_pct"],
                "near_term_pct": metrics["near_term_pct"],
                "concentration_pct": metrics["concentration_pct"],
                "sectors": len(metrics["sector_weights"]),
            },
            "success": True,
        }

        logger.info(
            "fetch_options_activity_completed",
            **result,
        )

        return result

    except Exception as e:
        logger.error(
            "fetch_options_activity_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "task_id": task_id,
            "as_of_date": dt.date.today().isoformat(),
            "error": str(e),
            "success": False,
        }
