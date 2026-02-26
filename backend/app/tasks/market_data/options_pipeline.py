"""Options positioning pipeline tasks.

Fetches and processes options market data for sentiment analysis:
put/call ratios (SPY, QQQ, IWM aggregate) and CBOE activity metrics.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any

import requests  # noqa: F401  (kept for test patches: options_pipeline.requests.get)
import yfinance as yf  # noqa: F401  (kept for test patches: options_pipeline.yf.Ticker)

from app.logging_config import get_logger
from app.storage import get_storage
from app.tasks.market_data._putcall_sources import (
    PUTCALL_EXPIRATIONS,
    PUTCALL_SYMBOLS,
    _calculate_putcall_from_finnhub,
    _calculate_putcall_from_polygon,
    _calculate_putcall_from_yfinance,
)

__all__ = [
    "PUTCALL_EXPIRATIONS",
    "PUTCALL_SYMBOLS",
    "_calculate_putcall_from_finnhub",
    "_calculate_putcall_from_polygon",
    "_calculate_putcall_from_yfinance",
    "_get_putcall_ratio_with_fallbacks",
    "fetch_options_activity_metrics",
    "fetch_putcall_ratio",
]

logger = get_logger(__name__)


def _get_putcall_ratio_with_fallbacks() -> dict[str, Any]:
    """Return put/call ratio from the first succeeding source.

    Priority: yfinance → Polygon → Finnhub.
    Raises RuntimeError when all sources fail.
    """
    result = _calculate_putcall_from_yfinance()
    if result:
        return result
    logger.info("putcall_fallback_to_polygon")
    result = _calculate_putcall_from_polygon()
    if result:
        return result
    logger.info("putcall_fallback_to_finnhub")
    result = _calculate_putcall_from_finnhub()
    if result:
        return result
    raise RuntimeError("All put/call ratio sources failed (yfinance, Polygon, Finnhub)")


def _store_putcall(today: str, put_call_ratio: float, source: str) -> None:
    """Upsert put/call ratio into fear_greed_inputs."""
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
            (today, put_call_ratio, json.dumps({"put_call_ratio": source})),
        )
        conn.commit()


def fetch_putcall_ratio(as_of_date: str | None = None) -> dict[str, Any]:
    """Fetch aggregate put/call ratio from options chains (SPY+QQQ+IWM via yfinance).

    Schedule: 14:30 UTC (market open) and 21:30 UTC (after close).
    """
    task_id = str(uuid.uuid4())
    today = dt.date.today().isoformat()
    logger.info("fetch_putcall_ratio_started", task_id=task_id, requested_date=as_of_date or today)
    try:
        data = _get_putcall_ratio_with_fallbacks()
        _store_putcall(today, data["put_call_ratio"], data["source"])
        result = {
            "task_id": task_id,
            "date": today,
            "put_call_ratio": data["put_call_ratio"],
            "total_call_volume": data["total_call_volume"],
            "total_put_volume": data["total_put_volume"],
            "symbol_ratios": {sym: round(d["ratio"], 2) for sym, d in data["symbol_ratios"].items()},
            "source": data["source"],
            "success": True,
        }
        logger.info("fetch_putcall_ratio_completed", **result)
        return result
    except Exception as e:
        logger.error("fetch_putcall_ratio_failed", task_id=task_id, error=str(e), error_type=type(e).__name__)
        return {"task_id": task_id, "date": as_of_date or today, "error": str(e), "success": False}


def _store_activity_metrics(metrics: dict[str, Any]) -> None:
    """Upsert options activity metrics into options_market_metrics."""
    storage = get_storage()
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO options_market_metrics (
                as_of_date, most_active_call_pct, near_term_pct,
                concentration_pct, sector_weights, source_timestamp
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


def fetch_options_activity_metrics() -> dict[str, Any]:
    """Fetch aggregated options activity metrics from CBOE Most Active page.

    Schedule: 21:15 UTC daily (after market close). Uses Playwright for JS rendering.
    """
    task_id = str(uuid.uuid4())
    logger.info("fetch_options_activity_started", task_id=task_id)
    try:
        storage = get_storage()
        from app.sources.cboe_most_active import get_cboe_most_active_source

        cboe_most_active = get_cboe_most_active_source(storage=storage)
        metrics = cboe_most_active.fetch_most_active_metrics()
        _store_activity_metrics(metrics)
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
        logger.info("fetch_options_activity_completed", **result)
        return result
    except Exception as e:
        logger.error("fetch_options_activity_failed", task_id=task_id, error=str(e), error_type=type(e).__name__)
        return {"task_id": task_id, "as_of_date": dt.date.today().isoformat(), "error": str(e), "success": False}
