"""Options positioning pipeline tasks.

Fetches and processes options market data for sentiment analysis:
- Put/Call ratios from yfinance options chains (SPY, QQQ, IWM aggregate)
- Options activity metrics from CBOE most active contracts
"""

from __future__ import annotations

import datetime as dt
import json
import os
from typing import TYPE_CHECKING, Any

import requests
import yfinance as yf

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage import get_storage

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# ETFs to aggregate for market-wide put/call ratio
# SPY (S&P 500), QQQ (Nasdaq 100), IWM (Russell 2000)
PUTCALL_SYMBOLS = ["SPY", "QQQ", "IWM"]
PUTCALL_EXPIRATIONS = 5  # Number of near-term expirations to include


def _calculate_putcall_from_yfinance() -> dict[str, Any] | None:
    """Calculate put/call ratio from yfinance options chains.

    Aggregates volume across SPY, QQQ, and IWM for a broad market view.
    Uses near-term expirations (first 5) as they have most volume.

    Returns:
        Dict with put_call_ratio, symbol_ratios, total volumes, and timestamp
        None if calculation fails
    """
    try:
        total_call_vol = 0
        total_put_vol = 0
        symbol_data: dict[str, dict[str, float]] = {}

        for symbol in PUTCALL_SYMBOLS:
            try:
                yf_obj = yf.Ticker(symbol)
                expirations = yf_obj.options[:PUTCALL_EXPIRATIONS]

                sym_call_vol = 0
                sym_put_vol = 0

                for exp in expirations:
                    chain = yf_obj.option_chain(exp)
                    sym_call_vol += chain.calls["volume"].fillna(0).sum()
                    sym_put_vol += chain.puts["volume"].fillna(0).sum()

                if sym_call_vol > 0:
                    symbol_data[symbol] = {
                        "call_volume": float(sym_call_vol),
                        "put_volume": float(sym_put_vol),
                        "ratio": float(sym_put_vol / sym_call_vol),
                    }
                    total_call_vol += sym_call_vol
                    total_put_vol += sym_put_vol

                    logger.debug(
                        "putcall_symbol_calculated",
                        symbol=symbol,
                        call_vol=int(sym_call_vol),
                        put_vol=int(sym_put_vol),
                        ratio=round(float(sym_put_vol / sym_call_vol), 2),
                    )
            except Exception as e:
                logger.warning(
                    "putcall_symbol_failed",
                    symbol=symbol,
                    error=str(e),
                )

        if total_call_vol == 0:
            logger.warning("yfinance_putcall_no_volume")
            return None

        aggregate_ratio = float(total_put_vol / total_call_vol)

        return {
            "put_call_ratio": round(aggregate_ratio, 4),
            "total_call_volume": int(total_call_vol),
            "total_put_volume": int(total_put_vol),
            "symbol_ratios": symbol_data,
            "source": "yfinance_options_chain",
            "symbols": PUTCALL_SYMBOLS,
            "expirations_per_symbol": PUTCALL_EXPIRATIONS,
        }
    except Exception as e:
        logger.warning("yfinance_putcall_failed", error=str(e))
        return None


def _calculate_putcall_from_polygon() -> dict[str, Any] | None:
    """Fallback: Calculate put/call ratio from Polygon options data.

    Returns:
        Dict with put_call_ratio or None if unavailable
    """
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        logger.debug("polygon_putcall_no_api_key")
        return None

    try:
        # Get SPY options aggregates
        url = f"https://api.polygon.io/v3/snapshot/options/SPY?apiKey={api_key}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        if not results:
            logger.warning("polygon_putcall_no_data")
            return None

        total_call_vol = 0
        total_put_vol = 0

        for opt in results:
            details = opt.get("details", {})
            day = opt.get("day", {})
            volume = day.get("volume", 0)

            if details.get("contract_type") == "call":
                total_call_vol += volume
            elif details.get("contract_type") == "put":
                total_put_vol += volume

        if total_call_vol == 0:
            logger.warning("polygon_putcall_no_call_volume")
            return None

        ratio = float(total_put_vol / total_call_vol)

        logger.info(
            "polygon_putcall_calculated",
            ratio=round(ratio, 2),
            call_vol=total_call_vol,
            put_vol=total_put_vol,
        )

        return {
            "put_call_ratio": round(ratio, 4),
            "total_call_volume": total_call_vol,
            "total_put_volume": total_put_vol,
            "source": "polygon_options_snapshot",
            "symbols": ["SPY"],
        }
    except Exception as e:
        logger.warning("polygon_putcall_failed", error=str(e))
        return None


def _calculate_putcall_from_finnhub() -> dict[str, Any] | None:
    """Fallback: Calculate put/call ratio from Finnhub options data.

    Returns:
        Dict with put_call_ratio or None if unavailable
    """
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        logger.debug("finnhub_putcall_no_api_key")
        return None

    try:
        url = f"https://finnhub.io/api/v1/stock/option-chain?symbol=SPY&token={api_key}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        options_data = data.get("data", [])
        if not options_data:
            logger.warning("finnhub_putcall_no_data")
            return None

        total_call_vol = 0
        total_put_vol = 0

        for expiry in options_data:
            for opt in expiry.get("options", {}).get("CALL", []):
                total_call_vol += opt.get("volume", 0) or 0
            for opt in expiry.get("options", {}).get("PUT", []):
                total_put_vol += opt.get("volume", 0) or 0

        if total_call_vol == 0:
            logger.warning("finnhub_putcall_no_call_volume")
            return None

        ratio = float(total_put_vol / total_call_vol)

        logger.info(
            "finnhub_putcall_calculated",
            ratio=round(ratio, 2),
            call_vol=total_call_vol,
            put_vol=total_put_vol,
        )

        return {
            "put_call_ratio": round(ratio, 4),
            "total_call_volume": total_call_vol,
            "total_put_volume": total_put_vol,
            "source": "finnhub_options_chain",
            "symbols": ["SPY"],
        }
    except Exception as e:
        logger.warning("finnhub_putcall_failed", error=str(e))
        return None


def _get_putcall_ratio_with_fallbacks() -> dict[str, Any]:
    """Get put/call ratio with multi-source fallback.

    Priority order:
    1. yfinance (free, no API key, aggregate SPY+QQQ+IWM)
    2. Polygon (if API key configured)
    3. Finnhub (if API key configured)

    Returns:
        Dict with put_call_ratio and source info

    Raises:
        RuntimeError if all sources fail
    """
    # Try yfinance first (primary source)
    result = _calculate_putcall_from_yfinance()
    if result:
        return result

    # Fallback to Polygon
    logger.info("putcall_fallback_to_polygon")
    result = _calculate_putcall_from_polygon()
    if result:
        return result

    # Fallback to Finnhub
    logger.info("putcall_fallback_to_finnhub")
    result = _calculate_putcall_from_finnhub()
    if result:
        return result

    raise RuntimeError("All put/call ratio sources failed (yfinance, Polygon, Finnhub)")


@celery_app.task(
    bind=True,
    name="fetch_putcall_ratio",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def fetch_putcall_ratio(  # type: ignore[no-untyped-def]
    self,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    """Fetch Put/Call Ratio from yfinance options chains.

    Calculates aggregate put/call ratio from SPY, QQQ, and IWM options chains.
    This replaced the CBOE data source which was blocked (HTTP 403) as of 2025-11-17.

    Advantages over CBOE:
    - Real-time data (CBOE was T+1)
    - More granular (can see individual ETF ratios)
    - Always available (no API blocks)
    - SPY+QQQ+IWM aggregate is a valid proxy for market sentiment

    Args:
        as_of_date: Date to fetch data for (YYYY-MM-DD). If None, uses today.
                   Note: yfinance returns current options data regardless of date param.

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - date: Date of data (today)
        - put_call_ratio: Aggregate ratio across SPY/QQQ/IWM
        - symbol_ratios: Individual ratios per symbol
        - success: Boolean indicating success

    Schedule:
        Runs twice daily at 14:30 UTC (9:30 AM ET, market open) and
        21:30 UTC (4:30 PM ET, after market close) to capture intraday changes.
    """
    task_id = self.request.id or "unknown"
    today = dt.date.today().isoformat()

    logger.info(
        "fetch_putcall_ratio_started",
        task_id=task_id,
        requested_date=as_of_date or today,
        source="yfinance",
    )

    try:
        # Calculate put/call ratio with multi-source fallback
        data = _get_putcall_ratio_with_fallbacks()
        put_call_ratio = data["put_call_ratio"]

        # Store in fear_greed_inputs table
        storage = get_storage()
        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO fear_greed_inputs (as_of_date, put_call_ratio, source_map)
                VALUES (%s, %s, %s)
                ON CONFLICT (as_of_date) DO UPDATE SET
                    put_call_ratio = EXCLUDED.put_call_ratio,
                    source_map = fear_greed_inputs.source_map || EXCLUDED.source_map
                """,
                (
                    today,
                    put_call_ratio,
                    json.dumps({"put_call_ratio": data["source"]}),
                ),
            )
            conn.commit()

        result = {
            "task_id": task_id,
            "date": today,
            "put_call_ratio": put_call_ratio,
            "total_call_volume": data["total_call_volume"],
            "total_put_volume": data["total_put_volume"],
            "symbol_ratios": {
                sym: round(d["ratio"], 2) for sym, d in data["symbol_ratios"].items()
            },
            "source": data["source"],
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
            "date": as_of_date or today,
            "error": str(e),
            "success": False,
        }


@celery_app.task(name="fetch_options_activity_metrics", bind=True)
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
    task_id = self.request.id or "unknown"

    logger.info(
        "fetch_options_activity_started",
        task_id=task_id,
    )

    try:
        # Get storage for metrics tracking
        storage = get_storage()

        # Import here to avoid circular dependency
        from app.sources.cboe_most_active import get_cboe_most_active_source

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
