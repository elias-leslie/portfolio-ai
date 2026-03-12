"""Fundamental data ingestion tasks.

Populates data for trading gaps:
- GAP-002: Valuation ratios (via reference_cache)
- GAP-004: Cash flow metrics
- GAP-006: Insider transactions
- GAP-007: Institutional holdings
- GAP-011: Short interest
- GAP-034: Yield curve (FRED)
- GAP-035: Inflation data (FRED)
- GAP-036: Fed funds rate (FRED)
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.logging_config import get_logger
from app.sources.fred import FREDSource
from app.sources.yfinance_source import YFinanceSource
from app.storage import PortfolioStorage
from app.storage.credential_loader import load_credentials_from_database

from ._fundamental_helpers import (
    insert_cash_flow,
    insert_insider_transaction,
    insert_institutional_holding,
    insert_institutional_summary,
    insert_short_interest,
)
from ._macro_helpers import fetch_and_store_indicators, fetch_and_store_yield_curve

logger = get_logger(__name__)

INDICATOR_CONFIGS = [
    ("fetch_inflation_data", "inflation_updated"),
    ("fetch_fed_funds_data", "fed_funds_updated"),
]


def ingest_fundamental_data(
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    """Ingest fundamental data for watchlist symbols.

    Fetches and stores cash flow metrics, insider transactions,
    institutional holdings, and short interest.

    Args:
        symbols: List of symbols to process (default: watchlist symbols)

    Returns:
        Dict with ingestion statistics
    """
    storage = PortfolioStorage()
    yf_source = YFinanceSource()

    if symbols is None:
        result = storage.query("SELECT DISTINCT symbol FROM watchlist WHERE is_active = TRUE")
        symbols = [row["symbol"] for row in result.iter_rows(named=True)]

    if not symbols:
        logger.info("No symbols to process for fundamental ingestion")
        return {"status": "skipped", "reason": "no_symbols"}

    stats: dict[str, Any] = {
        "symbols_processed": 0,
        "cash_flow_inserted": 0,
        "insider_transactions_inserted": 0,
        "institutional_holdings_inserted": 0,
        "short_interest_inserted": 0,
        "errors": [],
    }
    today = date.today()

    for symbol in symbols:
        _process_symbol(storage, yf_source, symbol, today, stats)

    logger.info(
        "fundamental_ingestion_complete",
        symbols_processed=stats["symbols_processed"],
        cash_flow=stats["cash_flow_inserted"],
        insiders=stats["insider_transactions_inserted"],
    )
    return stats


def _process_symbol(
    storage: PortfolioStorage,
    yf_source: YFinanceSource,
    symbol: str,
    today: date,
    stats: dict[str, Any],
) -> None:
    """Fetch and store all fundamental data for a single symbol."""
    try:
        data = yf_source.fetch_all_fundamental_data(symbol)

        if cf := data.get("cash_flow"):
            insert_cash_flow(storage, cf, today)
            stats["cash_flow_inserted"] += 1

        if insiders := data.get("insider_transactions"):
            for txn in insiders:
                insert_insider_transaction(storage, txn)
            stats["insider_transactions_inserted"] += len(insiders)

        if holders := data.get("institutional_holders"):
            for holder in holders:
                insert_institutional_holding(storage, holder)
            stats["institutional_holdings_inserted"] += len(holders)

        if summary := data.get("institutional_summary"):
            insert_institutional_summary(storage, summary, today)

        if short := data.get("short_interest"):
            insert_short_interest(storage, short, today)
            stats["short_interest_inserted"] += 1

        stats["symbols_processed"] += 1

    except Exception as e:
        logger.error("fundamental_data_failed", symbol=symbol, error=str(e), exc_info=True)
        stats["errors"].append({"symbol": symbol, "error": str(e)})


def ingest_macro_indicators() -> dict[str, Any]:
    """Ingest macro economic indicators from FRED.

    Fetches and stores yield curve (GAP-034), inflation (GAP-035),
    and Fed funds rate (GAP-036).

    Returns:
        Dict with ingestion statistics
    """
    load_credentials_from_database()
    storage = PortfolioStorage()
    fred = FREDSource()

    if not fred.is_enabled():
        logger.warning("FRED API key not configured, skipping macro ingestion")
        return {"status": "skipped", "reason": "no_api_key"}

    stats: dict[str, Any] = {
        "yield_curve_updated": False,
        "inflation_updated": False,
        "fed_funds_updated": False,
        "indicators_inserted": 0,
        "errors": [],
    }
    today = date.today()

    fetch_and_store_yield_curve(storage, fred, today, stats)
    for fetch_fn, stat_key in INDICATOR_CONFIGS:
        fetch_and_store_indicators(storage, fred, today, stats, fetch_fn, stat_key)

    logger.info(
        "macro_ingestion_complete",
        yield_curve=stats["yield_curve_updated"],
        inflation=stats["inflation_updated"],
        fed_funds=stats["fed_funds_updated"],
        indicators=stats["indicators_inserted"],
    )
    return stats
