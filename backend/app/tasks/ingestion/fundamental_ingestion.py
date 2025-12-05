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

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import numpy as np

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.sources.fred import FREDSource
from app.sources.yfinance_source import YFinanceSource
from app.storage import PortfolioStorage
from app.storage.credential_loader import load_credentials_from_database

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def _to_python(value: Any) -> Any:
    """Convert numpy types to native Python types for database insertion."""
    if value is None:
        return None
    # Handle numpy numeric types
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, (np.bool_, np.ndarray)):
        return bool(value) if isinstance(value, np.bool_) else value.tolist()
    return value


@celery_app.task(bind=True, max_retries=2)
def ingest_fundamental_data(self, symbols: list[str] | None = None) -> dict:
    """Ingest fundamental data for watchlist symbols.

    Fetches and stores:
    - Cash flow metrics
    - Insider transactions
    - Institutional holdings
    - Short interest

    Args:
        symbols: List of symbols to process (default: watchlist symbols)

    Returns:
        Dict with ingestion statistics
    """
    storage = PortfolioStorage()
    yf_source = YFinanceSource()

    # Get symbols from watchlist if not provided
    if symbols is None:
        result = storage.query("SELECT DISTINCT symbol FROM watchlist WHERE is_active = TRUE")
        symbols = [row["symbol"] for row in result.iter_rows(named=True)]

    if not symbols:
        logger.info("No symbols to process for fundamental ingestion")
        return {"status": "skipped", "reason": "no_symbols"}

    stats = {
        "symbols_processed": 0,
        "cash_flow_inserted": 0,
        "insider_transactions_inserted": 0,
        "institutional_holdings_inserted": 0,
        "short_interest_inserted": 0,
        "errors": [],
    }

    today = date.today()

    for symbol in symbols:
        try:
            data = yf_source.fetch_all_fundamental_data(symbol)

            # Insert cash flow metrics
            if cf := data.get("cash_flow"):
                _insert_cash_flow(storage, cf, today)
                stats["cash_flow_inserted"] += 1

            # Insert insider transactions
            if insiders := data.get("insider_transactions"):
                for txn in insiders:
                    _insert_insider_transaction(storage, txn)
                stats["insider_transactions_inserted"] += len(insiders)

            # Insert institutional holdings
            if holders := data.get("institutional_holders"):
                for holder in holders:
                    _insert_institutional_holding(storage, holder)
                stats["institutional_holdings_inserted"] += len(holders)

            # Insert institutional summary
            if summary := data.get("institutional_summary"):
                _insert_institutional_summary(storage, summary, today)

            # Insert short interest
            if short := data.get("short_interest"):
                _insert_short_interest(storage, short, today)
                stats["short_interest_inserted"] += 1

            stats["symbols_processed"] += 1

        except Exception as e:
            logger.error(f"Failed to process fundamental data for {symbol}: {e}")
            stats["errors"].append({"symbol": symbol, "error": str(e)})

    logger.info(
        "fundamental_ingestion_complete",
        symbols_processed=stats["symbols_processed"],
        cash_flow=stats["cash_flow_inserted"],
        insiders=stats["insider_transactions_inserted"],
    )

    return stats


def _insert_cash_flow(storage: PortfolioStorage, data: dict, as_of_date: date) -> None:
    """Insert cash flow metrics."""
    query = """
        INSERT INTO cash_flow_metrics (
            symbol, as_of_date, operating_cash_flow, free_cash_flow,
            capital_expenditure, fcf_yield, cash_flow_margin,
            fcf_per_share, cash_conversion_ratio, source, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'yfinance', NOW())
        ON CONFLICT (symbol, as_of_date)
        DO UPDATE SET
            operating_cash_flow = EXCLUDED.operating_cash_flow,
            free_cash_flow = EXCLUDED.free_cash_flow,
            capital_expenditure = EXCLUDED.capital_expenditure,
            fcf_yield = EXCLUDED.fcf_yield,
            cash_flow_margin = EXCLUDED.cash_flow_margin,
            fcf_per_share = EXCLUDED.fcf_per_share,
            cash_conversion_ratio = EXCLUDED.cash_conversion_ratio,
            updated_at = NOW()
    """
    storage.execute(query, [
        data["symbol"],
        as_of_date,
        _to_python(data.get("operating_cash_flow")),
        _to_python(data.get("free_cash_flow")),
        _to_python(data.get("capital_expenditure")),
        _to_python(data.get("fcf_yield")),
        _to_python(data.get("cash_flow_margin")),
        _to_python(data.get("fcf_per_share")),
        _to_python(data.get("cash_conversion_ratio")),
    ])


def _insert_insider_transaction(storage: PortfolioStorage, data: dict) -> None:
    """Insert insider transaction."""
    query = """
        INSERT INTO insider_transactions (
            symbol, insider_name, insider_title, transaction_type,
            transaction_date, shares, value, shares_owned_after, source
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'yfinance')
        ON CONFLICT (symbol, insider_name, transaction_date, transaction_type, shares)
        DO NOTHING
    """
    txn_date = data.get("transaction_date")
    if isinstance(txn_date, str):
        txn_date = datetime.fromisoformat(txn_date).date()
    elif hasattr(txn_date, "date"):
        txn_date = txn_date.date()

    storage.execute(query, [
        data["symbol"],
        data.get("insider_name"),
        data.get("insider_title"),
        data.get("transaction_type"),
        txn_date,
        _to_python(data.get("shares")),
        _to_python(data.get("value")),
        _to_python(data.get("shares_owned_after")),
    ])


def _insert_institutional_holding(storage: PortfolioStorage, data: dict) -> None:
    """Insert institutional holding."""
    query = """
        INSERT INTO institutional_holdings (
            symbol, holder_name, shares, value, pct_held, report_date, source, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, 'yfinance', NOW())
        ON CONFLICT (symbol, holder_name, report_date)
        DO UPDATE SET
            shares = EXCLUDED.shares,
            value = EXCLUDED.value,
            pct_held = EXCLUDED.pct_held,
            updated_at = NOW()
    """
    report_date = data.get("report_date")
    if isinstance(report_date, str):
        report_date = datetime.fromisoformat(report_date).date()
    elif hasattr(report_date, "date"):
        report_date = report_date.date()

    storage.execute(query, [
        data["symbol"],
        data.get("holder_name"),
        _to_python(data.get("shares")),
        _to_python(data.get("value")),
        _to_python(data.get("pct_held")),
        report_date,
    ])


def _insert_institutional_summary(storage: PortfolioStorage, data: dict, as_of_date: date) -> None:
    """Insert institutional ownership summary."""
    query = """
        INSERT INTO institutional_ownership_summary (
            symbol, as_of_date, total_institutions, pct_held_institutions,
            pct_held_insiders, source, updated_at
        ) VALUES ($1, $2, $3, $4, $5, 'yfinance', NOW())
        ON CONFLICT (symbol, as_of_date)
        DO UPDATE SET
            total_institutions = EXCLUDED.total_institutions,
            pct_held_institutions = EXCLUDED.pct_held_institutions,
            pct_held_insiders = EXCLUDED.pct_held_insiders,
            updated_at = NOW()
    """
    storage.execute(query, [
        data["symbol"],
        as_of_date,
        _to_python(data.get("total_institutions")),
        _to_python(data.get("pct_held_institutions")),
        _to_python(data.get("pct_held_insiders")),
    ])


def _insert_short_interest(storage: PortfolioStorage, data: dict, as_of_date: date) -> None:
    """Insert short interest data."""
    query = """
        INSERT INTO short_interest (
            symbol, as_of_date, short_shares, short_ratio,
            short_percent_of_float, short_percent_of_outstanding,
            short_prior_month, source, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'yfinance', NOW())
        ON CONFLICT (symbol, as_of_date)
        DO UPDATE SET
            short_shares = EXCLUDED.short_shares,
            short_ratio = EXCLUDED.short_ratio,
            short_percent_of_float = EXCLUDED.short_percent_of_float,
            short_percent_of_outstanding = EXCLUDED.short_percent_of_outstanding,
            short_prior_month = EXCLUDED.short_prior_month,
            updated_at = NOW()
    """
    storage.execute(query, [
        data["symbol"],
        as_of_date,
        _to_python(data.get("short_shares")),
        _to_python(data.get("short_ratio")),
        _to_python(data.get("short_percent_of_float")),
        _to_python(data.get("short_percent_of_outstanding")),
        _to_python(data.get("short_prior_month")),
    ])

    # Dual-write to short_interest_summary table
    summary_query = """
        INSERT INTO short_interest_summary (
            symbol, as_of_date, shares_short, short_ratio, short_percent_of_float
        ) VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (symbol, as_of_date)
        DO UPDATE SET
            shares_short = EXCLUDED.shares_short,
            short_ratio = EXCLUDED.short_ratio,
            short_percent_of_float = EXCLUDED.short_percent_of_float,
            updated_at = NOW()
    """
    storage.execute(summary_query, [
        data["symbol"],
        as_of_date,
        _to_python(data.get("short_shares")),
        _to_python(data.get("short_ratio")),
        _to_python(data.get("short_percent_of_float")),
    ])


@celery_app.task(bind=True, max_retries=2)
def ingest_macro_indicators(self) -> dict:
    """Ingest macro economic indicators from FRED.

    Fetches and stores:
    - Yield curve data (GAP-034)
    - Inflation data (GAP-035)
    - Fed funds rate (GAP-036)

    Returns:
        Dict with ingestion statistics
    """
    # Load API keys from database into environment
    load_credentials_from_database()

    storage = PortfolioStorage()
    fred = FREDSource()

    if not fred.is_enabled():
        logger.warning("FRED API key not configured, skipping macro ingestion")
        return {"status": "skipped", "reason": "no_api_key"}

    stats = {
        "yield_curve_updated": False,
        "inflation_updated": False,
        "fed_funds_updated": False,
        "indicators_inserted": 0,
        "errors": [],
    }

    today = date.today()

    # Fetch and store yield curve data
    try:
        yield_data = fred.fetch_yield_curve()
        if yield_data:
            _insert_yield_curve(storage, yield_data, today)
            stats["yield_curve_updated"] = True
            stats["indicators_inserted"] += 5
    except Exception as e:
        stats["errors"].append({"indicator": "yield_curve", "error": str(e)})
        logger.error(f"Failed to fetch yield curve: {e}")

    # Fetch and store inflation data
    try:
        inflation_data = fred.fetch_inflation_data()
        if inflation_data:
            for indicator, value in inflation_data.items():
                if value is not None:
                    _insert_macro_indicator(storage, indicator.upper(), value, today)
                    stats["indicators_inserted"] += 1
            stats["inflation_updated"] = True
    except Exception as e:
        stats["errors"].append({"indicator": "inflation", "error": str(e)})
        logger.error(f"Failed to fetch inflation data: {e}")

    # Fetch and store Fed funds rate
    try:
        fed_data = fred.fetch_fed_funds_data()
        if fed_data:
            for indicator, value in fed_data.items():
                if value is not None:
                    _insert_macro_indicator(storage, indicator.upper(), value, today)
                    stats["indicators_inserted"] += 1
            stats["fed_funds_updated"] = True
    except Exception as e:
        stats["errors"].append({"indicator": "fed_funds", "error": str(e)})
        logger.error(f"Failed to fetch Fed funds data: {e}")

    logger.info(
        "macro_ingestion_complete",
        yield_curve=stats["yield_curve_updated"],
        inflation=stats["inflation_updated"],
        fed_funds=stats["fed_funds_updated"],
        indicators=stats["indicators_inserted"],
    )

    return stats


def _insert_yield_curve(storage: PortfolioStorage, data: dict, as_of_date: date) -> None:
    """Insert yield curve data."""
    query = """
        INSERT INTO yield_curve (
            observation_date, yield_3m, yield_2y, yield_5y, yield_10y, yield_30y,
            spread_10y_2y, spread_10y_3m, source
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'fred')
        ON CONFLICT (observation_date)
        DO UPDATE SET
            yield_3m = EXCLUDED.yield_3m,
            yield_2y = EXCLUDED.yield_2y,
            yield_5y = EXCLUDED.yield_5y,
            yield_10y = EXCLUDED.yield_10y,
            yield_30y = EXCLUDED.yield_30y,
            spread_10y_2y = EXCLUDED.spread_10y_2y,
            spread_10y_3m = EXCLUDED.spread_10y_3m
    """
    storage.execute(query, [
        as_of_date,
        _to_python(data.get("yield_3m")),
        _to_python(data.get("yield_2y")),
        _to_python(data.get("yield_5y")),
        _to_python(data.get("yield_10y")),
        _to_python(data.get("yield_30y")),
        _to_python(data.get("spread_10y_2y")),
        _to_python(data.get("spread_10y_3m")),
    ])


def _insert_macro_indicator(
    storage: PortfolioStorage,
    indicator: str,
    value: float,
    as_of_date: date,
) -> None:
    """Insert a single macro indicator."""
    series_id = FREDSource.INDICATORS.get(indicator)
    query = """
        INSERT INTO macro_indicators (indicator_name, series_id, observation_date, value, source)
        VALUES ($1, $2, $3, $4, 'fred')
        ON CONFLICT (indicator_name, observation_date)
        DO UPDATE SET value = EXCLUDED.value
    """
    storage.execute(query, [indicator, series_id, as_of_date, _to_python(value)])
